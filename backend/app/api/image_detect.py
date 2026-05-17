from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import BASE_DIR, VIOLATION_DIR
from app.core.annotator import draw_annotations
from app.core.danger_rules import DangerDetector
from app.core.detector import YOLODetector
from app.database import get_db
from app.services import detection_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/image', tags=['image-detect'])

_detector: YOLODetector | None = None
_danger: DangerDetector | None = None


def get_detector() -> tuple[YOLODetector, DangerDetector]:
    global _detector, _danger
    if _detector is None:
        from app.config import MODEL_PATH, DEVICE
        _detector = YOLODetector(str(MODEL_PATH), device=DEVICE)
        _danger = DangerDetector()
    assert _detector is not None and _danger is not None
    return _detector, _danger


class ImageDetectRequest(BaseModel):
    file_path: str


class DetectionItem(BaseModel):
    bbox: list[float]
    confidence: float
    class_id: int
    class_name: str


class ViolationItem(BaseModel):
    type: str
    count: int


class ImageDetectResponse(BaseModel):
    image: str
    detections: list[DetectionItem]
    violations: list[ViolationItem]
    total_objects: int
    record_id: int


@router.post('/detect', response_model=ImageDetectResponse)
def detect_image(req: ImageDetectRequest, db: Session = Depends(get_db)):
    """Run hazard detection on an uploaded image."""
    detector, danger = get_detector()

    full_path = str(BASE_DIR / req.file_path.lstrip('/'))
    frame = cv2.imread(full_path)
    if frame is None:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read image: {full_path}",
        )

    detections_result = detector.detect_image(frame)

    datas = [[*d.bbox, d.confidence, d.class_id] for d in detections_result]
    warnings, warnings_only, _, _ = danger.detect_danger(datas)

    # 统计各违规类型数量
    vtype_counts: dict[str, int] = {}
    for vtype, vdata in warnings.items():
        if isinstance(vdata, dict):
            vtype_counts[vtype] = int(vdata.get('count', 0))

    # violation_count = 实际违规（不含 warning_no_safety_vest）之和
    violation_count = (
        vtype_counts.get('warning_no_hardhat', 0)
        + vtype_counts.get('warning_close_to_machinery', 0)
        + vtype_counts.get('warning_close_to_vehicle', 0)
        + vtype_counts.get('warning_people_in_controlled_area', 0)
        + vtype_counts.get('warning_people_in_utility_pole_controlled_area', 0)
    )

    record = detection_service.create_record(
        db,
        filename=Path(req.file_path).name,
        file_type='image',
        file_path=req.file_path,
        total_objects=len(detections_result),
        violation_count=violation_count,
        v_no_hardhat=vtype_counts.get('warning_no_hardhat', 0),
        v_no_safety_vest=vtype_counts.get('warning_no_safety_vest', 0),
        v_close_to_machinery=vtype_counts.get('warning_close_to_machinery', 0),
        v_close_to_vehicle=vtype_counts.get('warning_close_to_vehicle', 0),
        v_in_controlled_area=vtype_counts.get('warning_people_in_controlled_area', 0),
        v_in_pole_area=vtype_counts.get('warning_people_in_utility_pole_controlled_area', 0),
    )

    # 只在实际违规（不含警告）时截图
    real_warnings = {k: v for k, v in warnings.items() if k != 'warning_no_safety_vest'}

    if real_warnings:
        filename = f"{uuid.uuid4().hex[:12]}_frame0.jpg"
        screenshot_path = VIOLATION_DIR / filename
        annotated = draw_annotations(frame, detections_result, warnings)
        cv2.imwrite(str(screenshot_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])

        for vtype, vdata in warnings.items():  # type: ignore[union-item]
            if vtype == 'warning_no_safety_vest':
                continue
            if not isinstance(vdata, dict):
                continue
            vdata_dict: dict[str, Any] = vdata
            objects = vdata_dict.get('objects', [])
            if not isinstance(objects, list):
                continue
            for obj in objects:
                if not isinstance(obj, dict):
                    continue
                detection_service.create_violation(
                    db,
                    record_id=record.id,
                    violation_type=vtype,
                    bbox=obj.get('bbox', []),
                    confidence=obj.get('confidence', 0.0),
                    screenshot_path=f'/violations/{filename}',
                )

    db.commit()

    violation_bboxes = []
    for vtype, vdata in warnings.items():  # type: ignore[union-item]
        if vtype == 'warning_no_safety_vest':
            continue
        if not isinstance(vdata, dict):
            continue
        count = vdata.get('count', 0)
        if isinstance(count, int):
            violation_bboxes.append(ViolationItem(type=vtype, count=count))

    detections_payload = [
        DetectionItem(
            bbox=d.bbox,
            confidence=d.confidence,
            class_id=d.class_id,
            class_name=d.class_name,
        )
        for d in detections_result
    ]

    annotated = draw_annotations(frame, detections_result, warnings)
    _, buffer = cv2.imencode('.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])
    frame_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

    return ImageDetectResponse(
        image=frame_b64,
        detections=detections_payload,
        violations=violation_bboxes,
        total_objects=len(detections_result),
        record_id=record.id,
    )