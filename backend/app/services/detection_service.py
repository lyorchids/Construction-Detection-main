from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.detection import DetectionRecord, Violation


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

    # 新增：按 DetectionRecord 新字段统计各违规类型数量
    v_stats: dict[str, int] = {
        'no_hardhat': db.scalar(
            select(func.sum(DetectionRecord.v_no_hardhat))
        ) or 0,
        'no_safety_vest': db.scalar(
            select(func.sum(DetectionRecord.v_no_safety_vest))
        ) or 0,
        'close_to_machinery': db.scalar(
            select(func.sum(DetectionRecord.v_close_to_machinery))
        ) or 0,
        'close_to_vehicle': db.scalar(
            select(func.sum(DetectionRecord.v_close_to_vehicle))
        ) or 0,
        'in_controlled_area': db.scalar(
            select(func.sum(DetectionRecord.v_in_controlled_area))
        ) or 0,
        'in_pole_area': db.scalar(
            select(func.sum(DetectionRecord.v_in_pole_area))
        ) or 0,
    }

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
        'violation_by_type_detail': v_stats,
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
    v_no_hardhat: int = 0,
    v_no_safety_vest: int = 0,
    v_close_to_machinery: int = 0,
    v_close_to_vehicle: int = 0,
    v_in_controlled_area: int = 0,
    v_in_pole_area: int = 0,
) -> DetectionRecord:
    record = DetectionRecord(
        filename=filename,
        file_type=file_type,
        file_path=file_path,
        total_objects=total_objects,
        violation_count=violation_count,
        duration=duration,
        v_no_hardhat=v_no_hardhat,
        v_no_safety_vest=v_no_safety_vest,
        v_close_to_machinery=v_close_to_machinery,
        v_close_to_vehicle=v_close_to_vehicle,
        v_in_controlled_area=v_in_controlled_area,
        v_in_pole_area=v_in_pole_area,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


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
    query = select(DetectionRecord)

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
    db.delete(record)
    db.commit()
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
