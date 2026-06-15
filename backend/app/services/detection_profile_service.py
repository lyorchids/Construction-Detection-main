from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.detection_profile import DetectionProfile
from app.schemas.detection_profile import ProfileCreate, ProfileUpdate


def list_profiles(
    db: Session,
    type_filter: str | None = None,
) -> list[DetectionProfile]:
    query = select(DetectionProfile).order_by(DetectionProfile.updated_at.desc())
    if type_filter:
        query = query.where(DetectionProfile.type == type_filter)
    return list(db.scalars(query).all())


def get_profile(db: Session, profile_id: int) -> DetectionProfile | None:
    return db.get(DetectionProfile, profile_id)


def create_profile(db: Session, data: ProfileCreate) -> DetectionProfile:
    profile = DetectionProfile(
        name=data.name,
        type=data.type,
        description=data.description,
        config=data.config,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def update_profile(
    db: Session,
    profile_id: int,
    data: ProfileUpdate,
) -> DetectionProfile | None:
    profile = db.get(DetectionProfile, profile_id)
    if not profile:
        return None
    if data.name is not None:
        profile.name = data.name
    if data.description is not None:
        profile.description = data.description
    if data.config is not None:
        profile.config = data.config
    db.commit()
    db.refresh(profile)
    return profile


def delete_profile(db: Session, profile_id: int) -> bool:
    profile = db.get(DetectionProfile, profile_id)
    if not profile:
        return False
    db.delete(profile)
    db.commit()
    return True
