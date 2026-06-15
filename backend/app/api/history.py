from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.detection import PaginatedResponse, RecordResponse, StatsResponse, ViolationResponse
from app.services import detection_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1', tags=['history'])


@router.get('/stats', response_model=StatsResponse)
def get_stats(db: Session = Depends(get_db)):
    stats = detection_service.get_stats(db)
    return stats


@router.get('/records', response_model=PaginatedResponse)
def get_records(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=1000),
    file_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    start_dt = datetime.fromisoformat(start_date) if start_date else None
    end_dt = datetime.fromisoformat(end_date) if end_date else None

    records, total = detection_service.get_records(
        db,
        page=page,
        page_size=page_size,
        file_type=file_type,
        start_date=start_dt,
        end_date=end_dt,
    )

    items = [
        RecordResponse(
            id=r.id,
            filename=r.filename,
            file_type=r.file_type,
            file_path=r.file_path,
            detect_time=r.detect_time.isoformat(),
            total_objects=r.total_objects,
            violation_count=r.violation_count,
            duration=r.duration,
            v_no_hardhat=r.v_no_hardhat,
            v_no_safety_vest=r.v_no_safety_vest,
            v_close_to_machinery=r.v_close_to_machinery,
            v_close_to_vehicle=r.v_close_to_vehicle,
            v_in_controlled_area=r.v_in_controlled_area,
            v_in_pole_area=r.v_in_pole_area,
        )
        for r in records
    ]

    return PaginatedResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get('/records/{record_id}', response_model=RecordResponse)
def get_record(record_id: int, db: Session = Depends(get_db)):
    record = detection_service.get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail='Record not found')

    return RecordResponse(
        id=record.id,
        filename=record.filename,
        file_type=record.file_type,
        file_path=record.file_path,
        detect_time=record.detect_time.isoformat(),
        total_objects=record.total_objects,
        violation_count=record.violation_count,
        duration=record.duration,
        v_no_hardhat=record.v_no_hardhat,
        v_no_safety_vest=record.v_no_safety_vest,
        v_close_to_machinery=record.v_close_to_machinery,
        v_close_to_vehicle=record.v_close_to_vehicle,
        v_in_controlled_area=record.v_in_controlled_area,
        v_in_pole_area=record.v_in_pole_area,
    )


@router.get('/records/{record_id}/violations', response_model=list[ViolationResponse])
def get_violations(record_id: int, db: Session = Depends(get_db)):
    record = detection_service.get_record(db, record_id)
    if not record:
        raise HTTPException(status_code=404, detail='Record not found')

    violations = detection_service.get_violations(db, record_id)
    return [
        ViolationResponse(
            id=v.id,
            record_id=v.record_id,
            violation_type=v.violation_type,
            frame_number=v.frame_number,
            timestamp=v.timestamp,
            bbox=v.bbox,
            confidence=v.confidence,
            screenshot_path=v.screenshot_path,
            created_at=v.created_at.isoformat(),
        )
        for v in violations
    ]


@router.delete('/records/{record_id}')
def delete_record(record_id: int, db: Session = Depends(get_db)):
    success = detection_service.delete_record(db, record_id)
    if not success:
        raise HTTPException(status_code=404, detail='Record not found')
    return {'message': 'Record deleted successfully'}
