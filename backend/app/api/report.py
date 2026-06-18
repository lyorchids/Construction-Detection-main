from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.detection import DetectionRecord, Violation
from app.schemas.detection import ReportResponse
from app.services import detection_service, get_ai_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/report', tags=['report'])


class AISummary(BaseModel):
    total_violations: int
    risk_level: str


class AIBasicInfo(BaseModel):
    report_id: str
    report_time: str
    file_name: str
    detection_type: str
    detection_duration: float
    total_targets: int
    analysis_period: Optional[str] = None
    total_records: Optional[int] = None


class AIReportViolation(BaseModel):
    type: str
    count: int
    first_time: str
    severity: str
    description: str
    suggestion: str


class AISafetyAssessment(BaseModel):
    overall_evaluation: str
    risk_factors: list[str]
    key_findings: str


class AIReportResponse(BaseModel):
    report_title: str
    basic_info: AIBasicInfo
    summary: AISummary
    violation_details: list[AIReportViolation]
    daily_overview: Optional[dict] = None
    safety_assessment: AISafetyAssessment
    overall_suggestion: str
    expert_signature: str


class AIAnalysisRequest(BaseModel):
    record_id: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


@router.post('/generate')
def generate_report(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    try:
        from app.services import report_service
        file_path = report_service.generate_report(db, start_dt, end_dt)
        filename = file_path.split('/')[-1]
        return ReportResponse(
            report_id=0,
            filename=filename,
            file_path=file_path,
            created_at=datetime.now().isoformat(),
        )
    except Exception as e:
        logger.error(f"Report generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/ai-analysis')
def generate_ai_report(
    req: AIAnalysisRequest,
    db: Session = Depends(get_db),
) -> AIReportResponse:
    """Generate AI-powered violation analysis report."""
    ai_service = get_ai_service()
    start_dt = datetime.fromisoformat(req.start_date) if req.start_date else None
    end_dt = datetime.fromisoformat(req.end_date) if req.end_date else None

    try:
        if req.record_id:
            record = detection_service.get_record(db, req.record_id)
            if not record:
                raise HTTPException(status_code=404, detail='Record not found')
            records = [record]
            violations = detection_service.get_violations(db, req.record_id)
        else:
            records, _ = detection_service.get_records(
                db,
                page=1,
                page_size=1000,
                start_date=start_dt,
                end_date=end_dt,
            )
            record_ids = [r.id for r in records]
            if record_ids:
                all_violations = list(
                    db.execute(
                        select(Violation).where(Violation.record_id.in_(record_ids))
                    )
                    .scalars()
                    .all()
                )
            else:
                all_violations = []
            violations = all_violations

        if not records:
            raise HTTPException(status_code=404, detail='No records found')

        if not violations:
            raise HTTPException(status_code=404, detail='No violations found')

        report = ai_service.generate_violation_report(
            records, violations,
            start_date=req.start_date,
            end_date=req.end_date,
        )

        bi = report.get('basic_info', {})
        sm = report.get('summary', {})
        sa = report.get('safety_assessment', {})
        vds = report.get('violation_details', [])

        return AIReportResponse(
            report_title=report.get('report_title', '建筑施工现场安全隐患AI分析报告'),
            basic_info=AIBasicInfo(
                report_id=str(bi.get('report_id', '')),
                report_time=str(bi.get('report_time', '')),
                file_name=str(bi.get('file_name', '')),
                detection_type=str(bi.get('detection_type', 'video')),
                detection_duration=float(bi.get('detection_duration', 0)),
                total_targets=int(bi.get('total_targets', 0)),
                analysis_period=bi.get('analysis_period'),
                total_records=bi.get('total_records'),
            ),
            daily_overview=report.get('daily_overview'),
            summary=AISummary(
                total_violations=int(sm.get('total_violations', 0)),
                risk_level=str(sm.get('risk_level', 'low')),
            ),
            violation_details=[
                AIReportViolation(
                    type=str(v.get('type', '')),
                    count=int(v.get('count', 0)),
                    first_time=str(v.get('first_time', '')),
                    severity=str(v.get('severity', 'low')),
                    description=str(v.get('description', '')),
                    suggestion=str(v.get('suggestion', '')),
                )
                for v in vds
            ],
            safety_assessment=AISafetyAssessment(
                overall_evaluation=sa.get('overall_evaluation', '暂无评估'),
                risk_factors=sa.get('risk_factors', ['暂无风险因素']),
                key_findings=sa.get('key_findings', '暂无发现'),
            ),
            overall_suggestion=report.get('overall_suggestion', ''),
            expert_signature=report.get('expert_signature', 'AI安全专家'),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI report generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post('/ai-analysis/download')
def download_ai_report(
    req: AIAnalysisRequest,
    db: Session = Depends(get_db),
):
    """Download AI analysis report as Word document with violation screenshots."""
    ai_service = get_ai_service()
    start_dt = datetime.fromisoformat(req.start_date) if req.start_date else None
    end_dt = datetime.fromisoformat(req.end_date) if req.end_date else None

    try:
        if req.record_id:
            record = detection_service.get_record(db, req.record_id)
            if not record:
                raise HTTPException(status_code=404, detail='Record not found')
            records = [record]
            violations = detection_service.get_violations(db, req.record_id)
        else:
            records, _ = detection_service.get_records(
                db,
                page=1,
                page_size=1000,
                start_date=start_dt,
                end_date=end_dt,
            )
            record_ids = [r.id for r in records]
            if record_ids:
                all_violations = list(
                    db.execute(
                        select(Violation).where(Violation.record_id.in_(record_ids))
                    )
                    .scalars()
                    .all()
                )
            else:
                all_violations = []
            violations = all_violations

        if not records:
            raise HTTPException(status_code=404, detail='No records found')

        if not violations:
            raise HTTPException(status_code=404, detail='No violations found')

        report = ai_service.generate_violation_report(
            records, violations,
            start_date=req.start_date,
            end_date=req.end_date,
        )

        from app.services import report_service as rs
        file_path = rs.generate_ai_report_docx(records[0], violations, report)
        filename = Path(file_path).name

        return FileResponse(
            str(file_path),
            filename=filename,
            media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"AI report download failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/download/{filename}')
def download_report(filename: str):
    from app.config import REPORT_DIR
    file_path = REPORT_DIR / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail='Report not found')
    return FileResponse(
        str(file_path),
        filename=filename,
        media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    )
