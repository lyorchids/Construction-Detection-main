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
    'warning_no_mask': '未佩戴口罩',
    'warning_no_safety_vest': '未穿反光背心',
    'warning_people_in_controlled_area': '进入锥形桶管控区',
    'detect_machinery_close_to_pole': '机械靠近电线杆',
    'warning_fire': '检测到火焰',
    'warning_smoke': '检测到烟雾',
}

SEVERITY_LEVELS: dict[str, str] = {
    'warning_no_hardhat': 'high',
    'warning_no_mask': 'low',
    'warning_no_safety_vest': 'low',
    'warning_people_in_controlled_area': 'high',
    'detect_machinery_close_to_pole': 'high',
    'warning_fire': 'critical',
    'warning_smoke': 'high',
}

VIOLATION_DESCRIPTIONS: dict[str, str] = {
    'warning_no_hardhat': '施工人员在作业过程中未佩戴安全帽，存在头部受到坠落物撞击的严重风险',
    'warning_no_mask': '施工人员未佩戴口罩，在粉尘环境下易吸入有害颗粒物，危害呼吸健康',
    'warning_no_safety_vest': '施工人员未穿反光背心，在机械作业区域容易被操作人员忽视，存在碰撞风险',
    'warning_people_in_controlled_area': '人员闯入锥形桶管控区域，存在被施工机械碰撞或误伤的风险',
    'detect_machinery_close_to_pole': '施工机械靠近电线杆作业，存在碰撞杆体或触碰高压线的严重风险',
    'warning_fire': '检测到明火，可能引发火灾或爆炸事故，严重危及现场人员和设备安全',
    'warning_smoke': '检测到烟雾，存在火灾隐患，需立即排查烟雾来源，防止火势蔓延',
}

VIOLATION_SUGGESTIONS: dict[str, str] = {
    'warning_no_hardhat': '立即要求所有进入施工现场人员正确佩戴安全帽，安全帽须系好下颏带，并加强岗前安全抽查',
    'warning_no_mask': '督促施工人员在粉尘区域规范佩戴口罩，配备符合国家标准的防尘口罩，定期更换滤芯',
    'warning_no_safety_vest': '要求施工人员在机械作业区、车辆通行区等危险区域必须穿戴反光背心，未穿戴者禁止进入',
    'warning_people_in_controlled_area': '加强管控区围挡和警示标识设置，安排专人值守巡视，严禁无关人员进入作业区域',
    'detect_machinery_close_to_pole': '在电线杆周围设置防撞设施和限高警示标志，机械作业时安排专人指挥监护，确保安全距离',
    'warning_fire': '立即组织人员排查火源，切断可能火源，配备足够数量的合规灭火器材，必要时启动消防应急预案并疏散人员',
    'warning_smoke': '立即排查烟雾来源，重点检查电气线路老化、易燃物堆放等情况，消除火灾隐患，配备烟雾报警装置',
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
            kwargs: dict[str, Any] = {
                'api_key': self.api_key,
                'timeout': 30,
                'max_retries': 1,
            }
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
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Generate violation analysis report with fixed templates + AI analysis.

        Fixed violation details (description/suggestion) are generated from templates.
        AI is only used for safety assessment and overall suggestions.

        Args:
            records: Detection records.
            violations: Violation records.
            start_date: Optional start date for date-range analysis.
            end_date: Optional end date for date-range analysis.

        Returns:
            Report data with violation_details + safety_assessment.
        """
        is_date_range = bool(start_date or end_date)
        data = self._prepare_analysis_data(records, violations)
        violation_details = self._generate_violation_details(data, is_date_range)
        report = self._build_base_report(data, violation_details, is_date_range, start_date, end_date)

        if self.is_available():
            try:
                if is_date_range:
                    prompt = self._build_date_range_prompt(data, start_date, end_date)
                else:
                    prompt = self._build_prompt(data)
                ai_response = self._call_ai(prompt)
                ai_analysis = self._parse_ai_response(ai_response)
                report['safety_assessment'] = ai_analysis.get('safety_assessment', report['safety_assessment'])
                report['overall_suggestion'] = ai_analysis.get('overall_suggestion', report['overall_suggestion'])
                report['expert_signature'] = ai_analysis.get('expert_signature', report['expert_signature'])
            except Exception as e:
                logger.error(f"AI analysis failed, using fallback: {e}")

        return report

    def _prepare_analysis_data(
        self,
        records: list[DetectionRecord],
        violations: list[Violation],
    ) -> dict[str, Any]:
        """Prepare violation data for AI analysis."""
        record_map: dict[int, DetectionRecord] = {r.id: r for r in records}
        type_count: dict[str, int] = {}
        type_details: dict[str, list[dict[str, Any]]] = {}
        first_occurrence: dict[str, float] = {}
        first_date_by_type: dict[str, str] = {}
        daily_counts: dict[str, dict] = {}
        record_breakdown_map: dict[int, dict] = {}

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

            record = record_map.get(v.record_id)
            if record:
                date_str = record.detect_time.strftime('%Y-%m-%d')
                time_str = record.detect_time.strftime('%H:%M:%S')

                daily_counts.setdefault(date_str, {'total': 0})
                daily_counts[date_str]['total'] += 1
                daily_counts[date_str][vtype] = daily_counts[date_str].get(vtype, 0) + 1

                if vtype not in first_date_by_type or date_str < first_date_by_type[vtype]:
                    first_date_by_type[vtype] = date_str

                if v.record_id not in record_breakdown_map:
                    record_breakdown_map[v.record_id] = {
                        'filename': record.filename,
                        'detect_time': f'{date_str} {time_str}',
                        'date': date_str,
                        'time': time_str,
                        'violation_count': 0,
                        'type_counts': {},
                    }
                record_breakdown_map[v.record_id]['violation_count'] += 1
                record_breakdown_map[v.record_id]['type_counts'][vtype] = \
                    record_breakdown_map[v.record_id]['type_counts'].get(vtype, 0) + 1

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

        sorted_dates = sorted(daily_counts.keys())
        daily_trend: str = 'stable'
        if len(sorted_dates) >= 2:
            first_day = daily_counts[sorted_dates[0]]['total']
            last_day = daily_counts[sorted_dates[-1]]['total']
            if last_day > first_day * 1.2:
                daily_trend = 'increasing'
            elif last_day < first_day * 0.8:
                daily_trend = 'decreasing'

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
            'first_date_by_type': first_date_by_type,
            'daily_counts': daily_counts,
            'record_date_breakdown': list(record_breakdown_map.values()),
            'daily_trend': daily_trend,
            'generated_at': datetime.now().isoformat(),
        }

    def _build_prompt(self, data: dict[str, Any]) -> str:
        """Build AI prompt — AI only evaluates, no template filling."""
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

        prompt = f"""你是一位经验丰富的建筑施工现场安全专家。请根据以下检测数据，从专业角度进行深入分析和评估。

## 检测基本信息
- 文件名: {filename}
- 检测类型: {detection_type_label}
- 检测时长: {duration_val}秒
- 检测目标总数: {total_objects}
- 违规总数: {record_stats['total_violations']}

## 违规统计
{type_summary}

## 严重程度分布
- 轻微: {severity_stats.get('low', 0)}次
- 一般: {severity_stats.get('medium', 0)}次
- 严重: {severity_stats.get('high', 0)}次
- 极其严重: {severity_stats.get('critical', 0)}次

请结合以上数据，以建筑工地安全管理的实际场景进行深入分析：
1. 详细分析各类违规的具体表现、风险程度以及对现场安全的实际影响
2. 指出管理漏洞和制度缺陷，结合工地实际情况分析违规产生的根本原因
3. 给出可落地、分优先级的整改措施

仅输出以下JSON格式（不要包含其他任何文字）：

{{
  "safety_assessment": {{
    "overall_evaluation": "对整个工地安全状况的详细综合评价，分析各违规类型的具体表现、风险程度和管理漏洞，200字以内",
    "risk_factors": ["列出3-5个主要风险因素，详细说明每个风险的来源和影响，每个50字以内"],
    "key_findings": "数据分析后的核心发现和趋势判断，指出最突出的问题及其根本原因，以及改进方向，150字以内"
  }},
  "overall_suggestion": "针对本次检测发现的突出问题给出具体、分步骤的整改措施，结合建筑工地实际场景，按照优先级排序，250字以内",
  "expert_signature": "AI安全专家"
}}"""
        return prompt

    def _build_date_range_prompt(
        self,
        data: dict[str, Any],
        start_date: str | None,
        end_date: str | None,
    ) -> str:
        """Build AI prompt for date-range analysis."""
        record_stats = data['record_stats']
        type_count = data['type_count']
        severity_stats = data['severity_stats']
        daily_counts = data.get('daily_counts', {})
        first_date_by_type = data.get('first_date_by_type', {})

        start_str = start_date or '最早记录'
        end_str = end_date or '最晚记录'

        daily_lines = []
        for date_str in sorted(daily_counts.keys()):
            day = daily_counts[date_str]
            type_parts = []
            for vtype, count in sorted(day.items()):
                if vtype == 'total':
                    continue
                type_parts.append(f"{VIOLATION_LABELS.get(vtype, vtype)}{count}次")
            type_str = '，'.join(type_parts) if type_parts else '无具体类型'
            daily_lines.append(f"- {date_str}: 共{day['total']}次（{type_str}）")
        daily_summary = '\n'.join(daily_lines) if daily_lines else '  无违规记录'

        first_date_lines = []
        for vtype in sorted(type_count.keys(), key=lambda x: -type_count[x]):
            label = VIOLATION_LABELS.get(vtype, vtype)
            fd = first_date_by_type.get(vtype, '未知')
            first_date_lines.append(f"- {label}: {fd} 首次出现")
        first_date_summary = '\n'.join(first_date_lines) if first_date_lines else '  无违规记录'

        prompt = f"""你是一位经验丰富的建筑施工现场安全专家。请根据 {start_str} 至 {end_str} 时段内的检测数据，从时间维度深入分析违规情况。

## 分析时段
- 日期范围: {start_str} ~ {end_str}
- 涉及检测记录: {record_stats['total_records']} 条
- 违规总数: {record_stats['total_violations']}

## 每日违规分布
{daily_summary}

## 各违规类型首次出现日期
{first_date_summary}

## 严重程度分布
- 轻微: {severity_stats.get('low', 0)}次
- 一般: {severity_stats.get('medium', 0)}次
- 严重: {severity_stats.get('high', 0)}次
- 极其严重: {severity_stats.get('critical', 0)}次

请结合以上数据，从时间维度进行深入分析：
1. 详细分析每天的违规分布差异，指出哪些日期的违规特别突出，说明原因
2. 分析违规数量的整体变化趋势（上升/下降/波动），并分析可能的背后原因
3. 指出哪些违规类型在不同日期反复出现，说明整改措施未能有效落实
4. 从时间管理角度分析是否存在安全管理的盲区时段或薄弱环节

仅输出以下JSON格式（不要包含其他任何文字）：

{{
  "safety_assessment": {{
    "overall_evaluation": "对整个时段的安全状况详细综合评估，重点分析时间分布特征、变化趋势和反复违规问题，200字以内",
    "risk_factors": ["列出3-5个与时间/频次/反复性相关的风险因素，详细说明每个风险的表现和根源，每个50字以内"],
    "key_findings": "基于时间分布的深入核心发现，指出违规高发时段、反复出现的顽疾问题及其原因，150字以内"
  }},
  "overall_suggestion": "针对时间分布特征和反复违规问题给出具体、分步骤的整改建议，如加强特定时段巡查频次、建立反复违规追责机制等，按照优先级排序，250字以内",
  "expert_signature": "AI安全专家"
}}"""
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

    def _parse_ai_response(self, ai_response: str) -> dict[str, Any]:
        """Parse AI response — returns only safety_assessment + overall_suggestion.

        Returns:
            Dict with keys: safety_assessment (dict), overall_suggestion (str),
                            expert_signature (str).
        """
        try:
            ai_response = re.sub(r'```[a-z]*\n?', '', ai_response).strip()
            report = json.loads(ai_response)
            sa = report.get('safety_assessment', {})
            return {
                'safety_assessment': {
                    'overall_evaluation': sa.get('overall_evaluation', 'AI分析暂不可用'),
                    'risk_factors': sa.get('risk_factors', ['无法获取风险因素']),
                    'key_findings': sa.get('key_findings', 'AI分析暂不可用'),
                },
                'overall_suggestion': report.get('overall_suggestion', '请检查AI服务配置'),
                'expert_signature': report.get('expert_signature', 'AI安全专家'),
            }
        except Exception as e:
            logger.error(f"Failed to parse AI response: {e}")
            return {
                'safety_assessment': {
                    'overall_evaluation': 'AI分析暂不可用',
                    'risk_factors': ['AI服务响应异常'],
                    'key_findings': '无法获取AI分析结果',
                },
                'overall_suggestion': 'AI分析服务异常，请稍后重试',
                'expert_signature': 'AI安全专家',
            }

    def _generate_violation_details(
        self,
        data: dict[str, Any],
        is_date_range: bool = False,
    ) -> list[dict[str, Any]]:
        """Generate violation details from fixed templates."""
        type_count = data['type_count']
        first_occurrence = data.get('first_occurrence', {})
        first_date_by_type = data.get('first_date_by_type', {})
        details = []

        for vtype, count in sorted(type_count.items(), key=lambda x: -x[1]):
            if is_date_range:
                first_str = first_date_by_type.get(vtype, '未知')
            else:
                first_ts = first_occurrence.get(vtype, 0)
                try:
                    first_val = float(first_ts)
                except (TypeError, ValueError):
                    first_val = 0.0
                first_str = f'第{first_val:.1f}秒' if first_val > 0 else '首帧'
            details.append({
                'type': VIOLATION_LABELS.get(vtype, vtype),
                'count': count,
                'first_time': first_str,
                'severity': SEVERITY_LEVELS.get(vtype, 'medium'),
                'description': VIOLATION_DESCRIPTIONS.get(vtype, f'{VIOLATION_LABELS.get(vtype, vtype)}违规'),
                'suggestion': VIOLATION_SUGGESTIONS.get(vtype, '加强安全管理'),
            })

        return details

    def _build_base_report(
        self,
        data: dict[str, Any],
        violation_details: list[dict[str, Any]],
        is_date_range: bool = False,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Build base report with fixed fields + non-AI content."""
        import uuid
        from datetime import datetime

        record = data.get('record', {})
        type_count = data['type_count']
        severity_stats = data['severity_stats']
        record_stats = data.get('record_stats', {})
        daily_counts = data.get('daily_counts', {})
        daily_trend = data.get('daily_trend', 'stable')
        record_date_breakdown = data.get('record_date_breakdown', [])

        total_violations = sum(type_count.values())
        total_targets = float(record.get('total_objects', 0) or 0)

        risk_level = 'low'
        if severity_stats.get('high', 0) > 0:
            risk_level = 'high'
        elif severity_stats.get('medium', 0) > 0:
            risk_level = 'medium'

        type_labels = []
        for vtype, count in sorted(type_count.items(), key=lambda x: -x[1]):
            type_labels.append(f"{VIOLATION_LABELS.get(vtype, vtype)} {count}次")

        area_total = type_count.get('warning_people_in_controlled_area', 0)

        if is_date_range:
            start_str = start_date or '最早记录'
            end_str = end_date or '最晚记录'
            basic_info = {
                'analysis_period': f'{start_str} ~ {end_str}',
                'total_records': record_stats.get('total_records', 0),
                'report_id': uuid.uuid4().hex[:8].upper(),
                'report_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_name': f'{start_str} 至 {end_str} 时段分析',
                'detection_type': '时段分析',
                'detection_duration': record_stats.get('total_duration', 0),
                'total_targets': int(record_stats.get('total_objects', 0) or 0),
            }
        else:
            basic_info = {
                'report_id': uuid.uuid4().hex[:8].upper(),
                'report_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'file_name': record.get('filename', '未知'),
                'detection_type': record.get('file_type', 'video'),
                'detection_duration': record.get('duration', 0),
                'total_targets': int(total_targets),
            }

        return {
            'report_title': '建筑施工现场安全隐患AI分析报告',
            'basic_info': basic_info,
            'summary': {
                'total_violations': total_violations,
                'risk_level': risk_level,
            },
            'violation_details': violation_details,
            'daily_overview': {
                'dates': sorted(daily_counts.keys()),
                'daily_counts': daily_counts,
                'trend': daily_trend,
                'record_breakdown': record_date_breakdown,
            } if is_date_range else None,
            'safety_assessment': {
                'overall_evaluation': f'本次检测共发现{total_violations}次违规，涉及{len(type_count)}类问题（{"，".join(type_labels)}），现场安全管理需重点关注和整改。',
                'risk_factors': ['AI分析暂不可用，请启用AI服务获取专业风险分析'],
                'key_findings': f'违规分布：{", ".join(type_labels)}。建议针对突出问题立即整改。',
            },
            'overall_suggestion': '建议加强现场安全管理，定期进行安全培训，重点关注劳保用品佩戴和管控区域管理',
            'expert_signature': 'AI安全专家（离线模式）',
        }

    def _generate_fallback_report(
        self,
        records: list[DetectionRecord],
        violations: list[Violation],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Generate fallback report without AI."""
        is_date_range = bool(start_date or end_date)
        data = self._prepare_analysis_data(records, violations)
        violation_details = self._generate_violation_details(data, is_date_range)
        return self._build_base_report(data, violation_details, is_date_range, start_date, end_date)


_ai_service: AIService | None = None


def get_ai_service() -> AIService:
    global _ai_service
    if _ai_service is None:
        _ai_service = AIService()
    return _ai_service