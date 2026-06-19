from __future__ import annotations

from pydantic import BaseModel


class UploadResponse(BaseModel):
    file_id: int
    filename: str
    file_type: str
    file_path: str


class RecordResponse(BaseModel):
    id: int
    filename: str
    file_type: str
    file_path: str
    detect_time: str
    total_objects: int
    violation_count: int
    duration: float
    violations: dict[str, int] = {}


class ViolationResponse(BaseModel):
    id: int
    record_id: int
    violation_type: str
    frame_number: int
    timestamp: float
    bbox: list[float]
    confidence: float
    screenshot_path: str
    created_at: str


class PaginatedResponse(BaseModel):
    items: list[RecordResponse]
    total: int
    page: int
    page_size: int


class ReportResponse(BaseModel):
    report_id: int
    filename: str
    file_path: str
    created_at: str


class StatsDayItem(BaseModel):
    date: str
    count: int


class StatsResponse(BaseModel):
    total_records: int
    total_violations: int
    today_records: int
    today_violations: int
    violation_by_type: dict[str, int]
    last_7_days: list[StatsDayItem]
