from __future__ import annotations

import json
import logging
import re
from datetime import datetime
from typing import Any, Optional

from openai import OpenAI

from app.config import AI_API_KEY, AI_BASE_URL, AI_MODEL
from app.models.detection import DetectionRecord, Violation

logger = logging.getLogger(__name__)

VIOLATION_LABELS: dict[str, str] = {
    'warning_no_hardhat': '未戴安全帽',
    'warning_no_safety_vest': '⚠ 未穿反光背心（警告）',
    'warning_close_to_machinery': '靠近作业机械',
    'warning_close_to_vehicle': '靠近施工车辆',
    'warning_people_in_controlled_area': '进入锥形桶管控区',
    'warning_people_in_utility_pole_controlled_area': '进入电线杆危险区域',
}

SEVERITY_LEVELS: dict[str, str] = {
    'warning_no_hardhat': 'high',
    'warning_no_safety_vest': 'low',
    'warning_close_to_machinery': 'medium',
    'warning_close_to_vehicle': 'medium',
    'warning_people_in_controlled_area': 'high',
    'warning_people_in_utility_pole_controlled_area': 'high',
}


class AIService:
    """AI service for generating violation reports."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self.api_key = api_key or AI_API_KEY
        self.base_url = AI_BASE_URL
        self.model = AI_MODEL
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            kwargs: dict[str, Any] = {'api_key': self.api_key}
            if self.base_url:
                kwargs['base_url'] = self.base_url
            self._client = OpenAI(**kwargs)
        return self._client

    def is_available(self) -> bool:
        """Check if AI service is available."""
        return bool(self.api_key)

    def generate_violation_report(
        self,
        records: list[DetectionRecord],
        violations: list[Violation],
    ) -> dict[str, Any]:
        """Generate AI-powered violation analysis report.

        Args:
            records: Detection records.
            violations: Violation records.

        Returns:
            AI generated report data.
        """
        if not self.is_available():
            return self._generate_fallback_report(records, violations)

        analysis_data = self._prepare_analysis_data(records, violations)

        prompt = self._build_prompt(analysis_data)

        try:
            ai_response = self._call_ai(prompt)
            return self._parse_ai_response(ai_response, analysis_data)
        except Exception as e:
            logger.error(f"AI report generation failed: {e}")
            return self._generate_fallback_report(records, violations)

    def _prepare_analysis_data(
        self,
        records: list[DetectionRecord],
        violations: list[Violation],
    ) -> dict[str, Any]:
        """Prepare violation data for AI analysis."""
        type_count: dict[str, int] = {}
        type_details: dict[str, list[dict[str, Any]]] = {}
        first_occurrence: dict[str, float] = {}

        for v in violations:
            vtype = v.violation_type
            type_count[vtype] = type_count.get(vtype, 0) + 1

            if vtype not in type_details:
                type_details[vtype] = []
                first_occurrence[vtype] = v.timestamp

            type_details[vtype].append({
                'timestamp': v.timestamp,
                'frame': v.frame_number,
                'confidence': v.confidence,
                'bbox': v.bbox,
            })

        severity_stats = {'low': 0, 'medium': 0, 'high': 0, 'critical': 0}
        for vtype, count in type_count.items():
            severity = SEVERITY_LEVELS.get(vtype, 'low')
            severity_stats[severity] = severity_stats.get(severity, 0) + count

        record = records[0] if records else None
        record_stats = {
            'total_records': len(records),
            'total_violations': len(violations),
            'total_duration': sum(r.duration for r in records) if records else 0,
            'total_objects': sum(r.total_objects for r in records) if records else 0,
        }

        return {
            'record': {
                'id': record.id if record else 0,
                'filename': record.filename if record else '',
                'file_type': record.file_type if record else '',
                'duration': record.duration if record else 0,
                'total_objects': record.total_objects if record else 0,
            } if record else {},
            'record_stats': record_stats,
            'type_count': type_count,
            'severity_stats': severity_stats,
            'type_details': type_details,
            'first_occurrence': first_occurrence,
            'generated_at': datetime.now().isoformat(),
        }

    def _build_prompt(self, data: dict[str, Any]) -> str:
        """Build AI prompt with standard report template."""
        record = data.get('record', {})
        record_stats = data['record_stats']
        type_count = data['type_count']
        severity_stats = data['severity_stats']

        filename = record.get('filename', '未知文件')
        file_type = record.get('file_type', 'video')
        duration = record.get('duration', 0)
        total_objects = record.get('total_objects', 0)
        detection_type_label = "图片" if file_type == "image" else "视频"
        duration_val = f"{duration:.1f}" if duration else "0.0"

        first_occurrence = data.get('first_occurrence', {})

        type_list = []
        for vtype, count in sorted(type_count.items(), key=lambda x: -x[1]):
            first_ts = first_occurrence.get(vtype, 0)
            first_str = f'第{first_ts:.1f}秒' if isinstance(first_ts, (int, float)) and first_ts > 0 else '首帧'
            type_list.append(f"- {VIOLATION_LABELS.get(vtype, vtype)}: {count}次（首次：{first_str}）")

        type_summary = '\n'.join(type_list)

        prompt = f"""你是一位专业的建筑施工现场安全专家。请根据以下违规检测数据生成一份标准化的AI分析报告。

## 一、检测基本信息
- 文件名: {filename}
- 检测类型: {detection_type_label}
- 检测时长: {duration_val}秒
- 检测目标总数: {total_objects}
- 违规总数: {record_stats['total_violations']}

## 二、违规详情（按类型分组）
{type_summary}

## 三、严重程度分类
- 轻微: {severity_stats.get('low', 0)}次
- 一般: {severity_stats.get('medium', 0)}次
- 严重: {severity_stats.get('high', 0)}次
- 极其严重: {severity_stats.get('critical', 0)}次

请生成以下JSON格式的报告（不要包含任何其他内容）：
{{
  "report_title": "建筑施工现场安全隐患AI分析报告",
  "basic_info": {{
    "report_id": "自动生成8位UUID",
    "report_time": "当前时间YYYY-MM-DD HH:mm:ss",
    "file_name": "{filename}",
    "detection_type": "{file_type}",
    "detection_duration": {duration if duration else 0},
    "total_targets": {total_objects}
  }},
  "summary": {{
    "total_violations": {record_stats['total_violations']},
    "risk_level": "low/medium/high/critical之一",
    "violation_rate": "百分比如30%"
  }},
  "violation_details": [
    {{
      "type": "违规类型",
      "count": 数字,
      "first_time": "首次发现时间如第10秒",
      "severity": "low/medium/high/critical",
      "description": "30字以内描述",
      "suggestion": "40字以内整改建议"
    }}
  ],
  "safety_assessment": {{
    "ppe_compliance": "百分比如85%",
    "proximity_compliance": "百分比如90%",
    "restricted_area_compliance": "百分比如95%"
  }},
  "overall_suggestion": "60字以内总体整改建议",
  "expert_signature": "AI安全专家"
}}
  ],
  "safety_assessment": {{
    "ppe_compliance": "百分比如85%",
    "proximity_compliance": "百分比如90%",
    "restricted_area_compliance": "百分比如95%"
  }},
  "overall_suggestion": "60字以内总体整改建议",
  "expert_signature": "AI安全专家"
}}

请直接返回JSON，不要任何其他解释文字。"""
        return prompt

    def _call_ai(self, prompt: str) -> str:
        """Call AI API to generate report using OpenAI client."""
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {'role': 'user', 'content': prompt}
            ],
            temperature=0.7,
            max_tokens=2048,
        )

        content = response.choices[0].message.content
        return content if content is not None else ''

    def _parse_ai_response(
        self,
        ai_response: str,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Parse AI response to structured report."""
        try:
            ai_response = re.sub(r'```[a-z]*\n?', '', ai_response).strip()

            report = json.loads(ai_response)
            return report
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            return self._generate_fallback_report_from_data(data)

    def _generate_fallback_report(
        self,
        records: list[DetectionRecord],
        violations: list[Violation],
    ) -> dict[str, Any]:
        """Generate fallback report without AI."""
        type_count: dict[str, int] = {}
        for v in violations:
            type_count[v.violation_type] = type_count.get(v.violation_type, 0) + 1

        data = self._prepare_analysis_data(records, violations)
        return self._generate_fallback_report_from_data(data)

    def _generate_fallback_report_from_data(
        self,
        data: dict[str, Any],
    ) -> dict[str, Any]:
        """Generate fallback report from analysis data with standard format."""
        import uuid
        from datetime import datetime

        record = data.get('record', {})
        type_count = data['type_count']
        severity_stats = data['severity_stats']
        first_occurrence = data.get('first_occurrence', {})

        total_violations = sum(type_count.values())
        total_targets = float(record.get('total_objects', 0) or 0)
        violation_rate = f"{(total_violations / total_targets * 100):.0f}%" if total_targets > 0 else "0%"

        risk_level = 'low'
        if severity_stats.get('high', 0) > 0:
            risk_level = 'high'
        elif severity_stats.get('medium', 0) > 0:
            risk_level = 'medium'

        violations_details = []
        for vtype, count in type_count.items():
            first_time = first_occurrence.get(vtype, 0)
            try:
                first_val = float(first_time)
            except (TypeError, ValueError):
                first_val = 0.0
            if first_val > 0:
                first_str = f'第{first_val:.1f}秒'
            else:
                first_str = '首帧'
            violations_details.append({
                'type': VIOLATION_LABELS.get(vtype, vtype),
                'count': count,
                'first_time': first_str,
                'severity': SEVERITY_LEVELS.get(vtype, 'medium'),
                'description': f'{VIOLATION_LABELS.get(vtype, vtype)}违规{count}次',
                'suggestion': self._get_suggestion(vtype),
            })

        ppe_total = type_count.get('warning_no_hardhat', 0)
        proximity_total = type_count.get('warning_close_to_machinery', 0) + type_count.get('warning_close_to_vehicle', 0)
        area_total = type_count.get('warning_people_in_controlled_area', 0) + type_count.get('warning_people_in_utility_pole_controlled_area', 0)

        ppe_rate = max(0, 100 - (ppe_total / total_targets * 100)) if total_targets > 0 else 100
        proximity_rate = max(0, 100 - (proximity_total / total_targets * 100)) if total_targets > 0 else 100
        area_rate = max(0, 100 - (area_total / total_targets * 100)) if total_targets > 0 else 100

        return {
            'report_title': '建筑施工现场安全隐患AI分析报告',
            'basic_info': {
                'report_id': uuid.uuid4().hex[:8].upper(),
                'report_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_name': record.get('filename', '未知'),
                'detection_type': record.get('file_type', 'video'),
                'detection_duration': record.get('duration', 0),
                'total_targets': total_targets,
            },
            'summary': {
                'total_violations': total_violations,
                'risk_level': risk_level,
                'violation_rate': violation_rate,
            },
            'violation_details': violations_details,
            'safety_assessment': {
                'ppe_compliance': f'{ppe_rate:.0f}%',
                'proximity_compliance': f'{proximity_rate:.0f}%',
                'restricted_area_compliance': f'{area_rate:.0f}%',
            },
            'overall_suggestion': '建议加强现场安全管理，定期进行安全培训',
            'expert_signature': 'AI安全专家',
        }

    def _get_suggestion(self, violation_type: str) -> str:
        """Get suggestion for violation type."""
        suggestions: dict[str, str] = {
            'warning_no_hardhat': '督促施工人员佩戴安全帽',
            'warning_no_mask': '督促施工人员佩戴口罩',
            'warning_no_safety_vest': '督促穿戴反光背心',
            'warning_close_to_machinery': '设置机械作业警示区',
            'warning_close_to_vehicle': '设置车辆行驶警示区',
            'warning_people_in_controlled_area': '加强管控区管理',
            'warning_people_in_utility_pole_controlled_area': '设置电线杆警示区',
        }
        return suggestions.get(violation_type, '加强安全管理')


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service