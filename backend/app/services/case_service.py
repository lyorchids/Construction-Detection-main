from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.case import Case
from app.models.detection import DetectionRecord, Violation
from app.models.violation_count import ViolationCount
from app.schemas.case import CaseCreate, CaseUpdate

CASE_TYPE_MAP: dict[str, str] = {
    'warning_no_hardhat': 'no_hardhat',
    'warning_no_mask': 'other',
    'warning_no_safety_vest': 'other',
    'warning_people_in_controlled_area': 'dangerous_operation',
    'detect_machinery_close_to_pole': 'dangerous_operation',
    'warning_fire': 'dangerous_operation',
    'warning_smoke': 'dangerous_operation',
}

CASE_TYPE_LABELS: dict[str, str] = {
    'no_hardhat': '未戴头盔',
    'dangerous_operation': '危险操作',
    'other': '其他',
}

SEVERITY_MAP: dict[str, str] = {
    'warning_no_hardhat': 'high',
    'warning_no_mask': 'low',
    'warning_no_safety_vest': 'low',
    'warning_people_in_controlled_area': 'high',
    'detect_machinery_close_to_pole': 'high',
    'warning_fire': 'critical',
    'warning_smoke': 'high',
}

DEFAULT_ACTIONS: dict[str, str] = {
    'no_hardhat': (
        '1. 立即要求该工人停止作业并正确佩戴安全帽\n'
        '2. 对工人进行现场安全教育，强调佩戴安全帽的重要性\n'
        '3. 通知班组长加强监督，确保所有进入施工区域人员佩戴安全帽\n'
        '4. 将该案例纳入安全培训材料，全员通报'
    ),
    'dangerous_operation': (
        '1. 立即发出警告，要求人员与机械设备保持安全距离\n'
        '2. 在机械设备周围设置明显的安全警示线和警示标志\n'
        '3. 对相关操作人员进行安全交底\n'
        '4. 加强现场巡查，及时发现并制止危险行为'
    ),
    'other': (
        '1. 立即制止违规行为，消除安全隐患\n'
        '2. 对相关人员进行安全教育\n'
        '3. 完善现场安全管理措施\n'
        '4. 持续跟踪整改情况直至闭环'
    ),
}


def _map_case_type(violations: list[Violation]) -> str:
    for v in violations:
        mapped = CASE_TYPE_MAP.get(v.violation_type)
        if mapped:
            return mapped
    return 'other'


def _map_severity(violations: list[Violation]) -> str:
    levels = {'low': 0, 'medium': 1, 'high': 2, 'critical': 3}
    max_level = 'low'
    for v in violations:
        mapped = SEVERITY_MAP.get(v.violation_type, 'low')
        if levels.get(mapped, 0) > levels.get(max_level, 0):
            max_level = mapped
    return max_level


def _build_description(record: DetectionRecord, violations: list[Violation]) -> str:
    type_counts: dict[str, int] = {}
    for v in violations:
        type_counts[v.violation_type] = type_counts.get(v.violation_type, 0) + 1

    lines = [f'在"{record.filename}"的检测中，发现以下安全隐患：']
    labels = {
        'warning_no_hardhat': '未佩戴安全帽',
        'warning_no_mask': '未佩戴口罩',
        'warning_no_safety_vest': '未穿反光背心',
        'warning_people_in_controlled_area': '进入锥形桶管控区',
        'detect_machinery_close_to_pole': '机械靠近电线杆',
        'warning_fire': '检测到火焰',
        'warning_smoke': '检测到烟雾',
    }
    for vtype, count in type_counts.items():
        label = labels.get(vtype, vtype)
        lines.append(f'- {label}：{count}次')
    lines.append(f'共检测到{record.total_objects}个目标，违规{record.violation_count}次。')
    return '\n'.join(lines)


def _build_actions(case_type: str) -> str:
    return DEFAULT_ACTIONS.get(case_type, DEFAULT_ACTIONS['other'])


def create_case(db: Session, data: CaseCreate) -> Case:
    now = datetime.now()
    case = Case(
        title=data.title,
        case_type=data.case_type,
        severity=data.severity,
        scene_description=data.scene_description,
        recommended_actions=data.recommended_actions,
        process_info=data.process_info,
        images=data.images,
        source_record_id=data.source_record_id,
        created_at=now,
        updated_at=now,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def create_case_from_record(db: Session, record_id: int) -> Case | None:
    record = db.get(DetectionRecord, record_id)
    if not record:
        return None

    violations = list(
        db.scalars(
            select(Violation).where(Violation.record_id == record_id)
        ).all()
    )

    # Fallback: use violation_counts if violations table is empty
    if not violations:
        vc_rows = db.scalars(
            select(ViolationCount).where(ViolationCount.record_id == record_id)
        ).all()
        if not vc_rows:
            return None
        violations = [
            Violation(
                record_id=record_id,
                violation_type=vc.violation_type,
                bbox=[],
                confidence=0.0,
                screenshot_path='',
            )
            for vc in vc_rows
            for _ in range(vc.count)
        ]

    case_type = _map_case_type(violations)
    severity = _map_severity(violations)
    case_type_label = CASE_TYPE_LABELS.get(case_type, '其他')
    title = f'{case_type_label}违规案例'

    images = list({v.screenshot_path for v in violations if v.screenshot_path})
    description = _build_description(record, violations)
    actions = _build_actions(case_type)
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M')

    process = (
        f'检测时间：{now_str}\n'
        f'已记录违规信息，现场管理人员需跟进处理。'
    )

    now_dt = datetime.now()
    case = Case(
        title=title,
        case_type=case_type,
        severity=severity,
        scene_description=description,
        recommended_actions=actions,
        process_info=process,
        images=images,
        source_record_id=record_id,
        created_at=now_dt,
        updated_at=now_dt,
    )
    db.add(case)
    db.commit()
    db.refresh(case)
    return case


def get_case(db: Session, case_id: int) -> Case | None:
    return db.get(Case, case_id)


def get_cases(
    db: Session,
    page: int = 1,
    page_size: int = 20,
    case_type: str | None = None,
    severity: str | None = None,
    keyword: str | None = None,
) -> tuple[list[Case], int]:
    query = select(Case)

    if case_type:
        query = query.where(Case.case_type == case_type)
    if severity:
        query = query.where(Case.severity == severity)
    if keyword:
        like = f'%{keyword}%'
        query = query.where(
            (Case.title.like(like)) | (Case.scene_description.like(like))
        )

    count_query = select(func.count(Case.id))
    if case_type:
        count_query = count_query.where(Case.case_type == case_type)
    if severity:
        count_query = count_query.where(Case.severity == severity)
    if keyword:
        like = f'%{keyword}%'
        count_query = count_query.where(
            (Case.title.like(like)) | (Case.scene_description.like(like))
        )

    total = db.scalar(count_query) or 0

    query = query.order_by(Case.created_at.desc())
    query = query.offset((page - 1) * page_size).limit(page_size)
    cases = list(db.scalars(query).all())

    return cases, total


def update_case(db: Session, case_id: int, data: CaseUpdate) -> Case | None:
    case = db.get(Case, case_id)
    if not case:
        return None

    update_data: dict[str, Any] = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(case, key, value)

    db.commit()
    db.refresh(case)
    return case


def delete_case(db: Session, case_id: int) -> bool:
    case = db.get(Case, case_id)
    if not case:
        return False
    db.delete(case)
    db.commit()
    return True
