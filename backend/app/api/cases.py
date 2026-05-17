from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.case import CaseCreate, CaseListResponse, CaseResponse, CaseUpdate
from app.services import case_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/cases', tags=['cases'])


def _to_response(case: object) -> CaseResponse:
    from app.models.case import Case
    c: Case = case
    return CaseResponse(
        id=c.id,
        title=c.title,
        case_type=c.case_type,
        severity=c.severity,
        scene_description=c.scene_description,
        recommended_actions=c.recommended_actions,
        process_info=c.process_info,
        images=c.images if c.images else [],
        source_record_id=c.source_record_id,
        source_filename=c.record.filename if c.record else None,
        created_at=c.created_at.isoformat() if c.created_at else '',
        updated_at=c.updated_at.isoformat() if c.updated_at else '',
    )


@router.post('', response_model=CaseResponse, status_code=201)
def create_case(data: CaseCreate, db: Session = Depends(get_db)):
    case = case_service.create_case(db, data)
    return _to_response(case)


@router.post('/from-record/{record_id}', response_model=CaseResponse, status_code=201)
def create_case_from_record(record_id: int, db: Session = Depends(get_db)):
    case = case_service.create_case_from_record(db, record_id)
    if not case:
        raise HTTPException(
            status_code=404,
            detail='Record not found or has no violations',
        )
    return _to_response(case)


@router.get('', response_model=CaseListResponse)
def list_cases(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    case_type: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    cases, total = case_service.get_cases(
        db,
        page=page,
        page_size=page_size,
        case_type=case_type,
        severity=severity,
        keyword=keyword,
    )
    items = [_to_response(c) for c in cases]
    return CaseListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get('/{case_id}', response_model=CaseResponse)
def get_case(case_id: int, db: Session = Depends(get_db)):
    case = case_service.get_case(db, case_id)
    if not case:
        raise HTTPException(status_code=404, detail='Case not found')
    return _to_response(case)


@router.put('/{case_id}', response_model=CaseResponse)
def update_case(
    case_id: int,
    data: CaseUpdate,
    db: Session = Depends(get_db),
):
    case = case_service.update_case(db, case_id, data)
    if not case:
        raise HTTPException(status_code=404, detail='Case not found')
    return _to_response(case)


@router.delete('/{case_id}')
def delete_case(case_id: int, db: Session = Depends(get_db)):
    success = case_service.delete_case(db, case_id)
    if not success:
        raise HTTPException(status_code=404, detail='Case not found')
    return {'message': 'Case deleted successfully'}
