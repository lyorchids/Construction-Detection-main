from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, field_validator


class ProfileCreate(BaseModel):
    name: str
    type: str
    description: str = ''
    config: dict

    @field_validator('type')
    @classmethod
    def validate_type(cls, v: str) -> str:
        if v not in ('image', 'video'):
            raise ValueError("type must be 'image' or 'video'")
        return v


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[dict] = None


class ProfileResponse(BaseModel):
    id: int
    name: str
    type: str
    description: str
    config: dict
    created_at: datetime
    updated_at: datetime

    model_config = {'from_attributes': True}
