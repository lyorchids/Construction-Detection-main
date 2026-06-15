from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.detection_profile import (
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
)
from app.services.detection_profile_service import (
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/profiles', tags=['detection-profiles'])


@router.get('', response_model=list[ProfileResponse])
def list_all_profiles(
    type: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    return list_profiles(db, type_filter=type)


@router.post('', response_model=ProfileResponse, status_code=201)
def create_new_profile(data: ProfileCreate, db: Session = Depends(get_db)):
    try:
        return create_profile(db, data)
    except Exception as e:
        if 'UNIQUE constraint' in str(e):
            raise HTTPException(status_code=400, detail=f"Profile name '{data.name}' already exists")
        raise HTTPException(status_code=500, detail=str(e))


@router.get('/{profile_id}', response_model=ProfileResponse)
def get_one_profile(profile_id: int, db: Session = Depends(get_db)):
    profile = get_profile(db, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail='Profile not found')
    return profile


@router.put('/{profile_id}', response_model=ProfileResponse)
def update_one_profile(
    profile_id: int,
    data: ProfileUpdate,
    db: Session = Depends(get_db),
):
    profile = update_profile(db, profile_id, data)
    if not profile:
        raise HTTPException(status_code=404, detail='Profile not found')
    return profile


@router.delete('/{profile_id}')
def delete_one_profile(profile_id: int, db: Session = Depends(get_db)):
    if not delete_profile(db, profile_id):
        raise HTTPException(status_code=404, detail='Profile not found')
    return {'message': 'Profile deleted'}
