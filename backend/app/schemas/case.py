from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class CaseCreate(BaseModel):
    title: str
    case_type: str
    severity: str
    scene_description: str = ''
    recommended_actions: str = ''
    process_info: str = ''
    images: list[str] = []
    source_record_id: Optional[int] = None


class CaseUpdate(BaseModel):
    title: Optional[str] = None
    case_type: Optional[str] = None
    severity: Optional[str] = None
    scene_description: Optional[str] = None
    recommended_actions: Optional[str] = None
    process_info: Optional[str] = None
    images: Optional[list[str]] = None


class CaseResponse(BaseModel):
    id: int
    title: str
    case_type: str
    severity: str
    scene_description: str
    recommended_actions: str
    process_info: str
    images: list[str]
    source_record_id: Optional[int] = None
    source_filename: Optional[str] = None
    created_at: str
    updated_at: str


class CaseListResponse(BaseModel):
    items: list[CaseResponse]
    total: int
    page: int
    page_size: int
