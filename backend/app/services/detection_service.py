from __future__ import annotations

import logging
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from app.config import VIOLATION_DIR
from app.models.detection import DetectionRecord, Violation
from app.models.violation_count import ViolationCount

logger = logging.getLogger(__name__)


def get_stats(db: Session) -> dict:
    now = datetime.now()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    total_records = db.scalar(select(func.count(DetectionRecord.id))) or 0
    total_violations = db.scalar(
        select(func.sum(DetectionRecord.violation_count))
    ) or 0

    today_records = db.scalar(
        select(func.count(DetectionRecord.id)).where(
            DetectionRecord.detect_time >= today_start
        )
    ) or 0
    today_violations = db.scalar(
        select(func.sum(DetectionRecord.violation_count)).where(
            DetectionRecord.detect_time >= today_start
        )
    ) or 0

    violation_by_type: dict[str, int] = {}
    violations = db.scalars(select(Violation)).all()
    for v in violations:
        violation_by_type[v.violation_type] = (
            violation_by_type.get(v.violation_type, 0) + 1
        )

    violation_by_type_detail: dict[str, int] = {}
    vc_rows = db.execute(
        select(ViolationCount.violation_type, func.sum(ViolationCount.count))
        .group_by(ViolationCount.violation_type)
    ).all()
    for row in vc_rows:
        violation_by_type_detail[row[0]] = int(row[1])

    last_7_days = []
    for i in range(6, -1, -1):
        d = today_start - timedelta(days=i)
        d_end = d + timedelta(days=1) - timedelta(seconds=1)
        day_records = db.scalars(
            select(DetectionRecord).where(
                DetectionRecord.detect_time >= d,
                DetectionRecord.detect_time <= d_end,
            )
        ).all()
        last_7_days.append({
            'date': d.strftime('%m-%d'),
            'count': sum(r.violation_count for r in day_records),
        })

    return {
        'total_records': total_records,
        'total_violations': total_violations,
        'today_records': today_records,
        'today_violations': today_violations,
        'violation_by_type': violation_by_type,
        'violation_by_type_detail': violation_by_type_detail,
        'last_7_days': last_7_days,
    }


def create_record(
    db: Session,
    filename: str,
    file_type: str,
    file_path: str,
    total_objects: int = 0,
    violation_count: int = 0,
    duration: float = 0.0,
    violation_counts: dict[str, int] | None = None,
) -> DetectionRecord:
    record = DetectionRecord(
        filename=filename,
        file_type=file_type,
        file_path=file_path,
        detect_time=datetime.now(),
        total_objects=total_objects,
        violation_count=violation_count,
        duration=duration,
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    if violation_counts:
        for vtype, count in violation_counts.items():
            if count > 0:
                db.add(ViolationCount(
                    record_id=record.id,
                    violation_type=vtype,
                    count=count,
                ))
        db.commit()

    return record


def set_violation_counts(db: Session, record_id: int, counts: dict[str, int]) -> None:
    """Replace all ViolationCount rows for a record with new counts."""
    existing = db.scalars(
        select(ViolationCount).where(ViolationCount.record_id == record_id)
    ).all()
    for vc in existing:
        db.delete(vc)
    for vtype, count in counts.items():
        if count > 0:
            db.add(ViolationCount(
                record_id=record_id,
                violation_type=vtype,
                count=count,
            ))
    db.commit()


def create_violation(
    db: Session,
    record_id: int,
    violation_type: str,
    bbox: list[float],
    confidence: float,
    frame_number: int = 0,
    timestamp: float = 0.0,
    screenshot_path: str = '',
) -> Violation:
    violation = Violation(
        record_id=record_id,
        violation_type=violation_type,
        bbox=bbox,
        confidence=confidence,
        frame_number=frame_number,
        timestamp=timestamp,
        screenshot_path=screenshot_path,
        created_at=datetime.now(),
    )
    db.add(violation)
    db.commit()
    db.refresh(violation)
    return violation


def get_records(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    file_type: str | None = None,
    start_date: datetime | None = None,
    end_date: datetime | None = None,
) -> tuple[list[DetectionRecord], int]:
    query = select(DetectionRecord).options(selectinload(DetectionRecord.violation_counts))

    if file_type:
        query = query.where(DetectionRecord.file_type == file_type)
    if start_date:
        query = query.where(DetectionRecord.detect_time >= start_date)
    if end_date:
        query = query.where(DetectionRecord.detect_time <= end_date)

    count_query = select(func.count(DetectionRecord.id))
    if file_type:
        count_query = count_query.where(DetectionRecord.file_type == file_type)
    if start_date:
        count_query = count_query.where(DetectionRecord.detect_time >= start_date)
    if end_date:
        count_query = count_query.where(DetectionRecord.detect_time <= end_date)

    total = db.scalar(count_query) or 0

    query = query.order_by(DetectionRecord.detect_time.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)

    records = list(db.scalars(query).all())

    return records, total


def get_record(db: Session, record_id: int) -> DetectionRecord | None:
    return db.get(DetectionRecord, record_id)


def get_violations(
    db: Session,
    record_id: int,
) -> list[Violation]:
    query = (
        select(Violation)
        .where(Violation.record_id == record_id)
        .order_by(Violation.created_at)
    )
    return list(db.scalars(query).all())


def delete_record(db: Session, record_id: int) -> bool:
    record = db.get(DetectionRecord, record_id)
    if not record:
        return False

    # Collect screenshot file paths before deletion
    screenshot_files: list[Path] = []
    for violation in record.violations:
        sp = violation.screenshot_path
        if sp:
            filename = sp.lstrip('/violations/')
            if filename:
                screenshot_files.append(VIOLATION_DIR / filename)

    db.delete(record)
    db.commit()

    # Delete screenshot files (best-effort, after DB commit)
    for fp in screenshot_files:
        try:
            if fp.exists():
                fp.unlink()
                logger.info(f"Deleted screenshot: {fp}")
        except Exception as e:
            logger.error(f"Failed to delete screenshot {fp}: {e}")

    return True


def get_records_by_date_range(
    db: Session,
    start_date: datetime,
    end_date: datetime,
) -> list[DetectionRecord]:
    query = (
        select(DetectionRecord)
        .where(
            DetectionRecord.detect_time >= start_date,
            DetectionRecord.detect_time <= end_date,
        )
        .order_by(DetectionRecord.detect_time)
    )
    return list(db.scalars(query).all())
