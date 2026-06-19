from __future__ import annotations

import base64
import logging
import uuid
from pathlib import Path
from typing import Any

import cv2
import numpy as np
from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import BASE_DIR, VIOLATION_DIR, DEVICE
from app.core.annotator import draw_annotations
from app.core.danger_rules import DangerDetector
from app.core.detector import YOLODetector
from app.core.model_registry import ModelRegistry
from app.database import get_db
from app.services import detection_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/image', tags=['image-detect'])

_detector: YOLODetector | None = None
_danger: DangerDetector | None = None
_registry: ModelRegistry | None = None


def get_detector() -> tuple[YOLODetector, DangerDetector]:
    global _detector, _danger
    if _detector is None:
        from app.config import MODEL_PATH, DEVICE
        _detector = YOLODetector(str(MODEL_PATH), device=DEVICE)
        _danger = DangerDetector()
    assert _detector is not None and _danger is not None
    return _detector, _danger


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


class ImageDetectRequest(BaseModel):
    file_path: str
    models: list[str] = ['ppe']
    thresholds: dict[str, float] = {}
    danger_rules: Optional[dict[str, bool]] = None
    save_annotated: bool = True


class DetectionItem(BaseModel):
    bbox: list[float]
    confidence: float
    class_id: int
    class_name: str
    source_model: str = ''
    is_violation: bool = False
    violation_labels: list[str] = []


class ViolationItem(BaseModel):
    type: str
    count: int


class ImageDetectResponse(BaseModel):
    image: str
    detections: list[DetectionItem]
    violations: list[ViolationItem]
    cone_polygons: list[list[list[float]]] = []
    total_objects: int
    record_id: int


def _merge_violations(
    violations: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: dict[str, int] = {}
    for v in violations:
        vtype = v.get('type', '')
        count = v.get('count', 1)
        merged[vtype] = merged.get(vtype, 0) + count
    return [{'type': k, 'count': v} for k, v in merged.items()]


def _get_detection_violation_labels(
    d: DetectionItem,
    vtype_counts: dict[str, int],
    warning_centers: dict[str, list[tuple[float, float]]],
    image_width: int = 640,
) -> list[str]:
    match_threshold = image_width * 0.08  # 8% of image width
    """Return ALL violation types that match this detection."""
    labels: list[str] = []
    cn = d.class_name
    if cn == 'NO-Hardhat' and vtype_counts.get('warning_no_hardhat', 0) > 0:
        labels.append('warning_no_hardhat')
    if cn == 'NO-Mask' and vtype_counts.get('warning_no_mask', 0) > 0:
        labels.append('warning_no_mask')
    if cn == 'NO-Safety Vest' and vtype_counts.get('warning_no_safety_vest', 0) > 0:
        labels.append('warning_no_safety_vest')
    if cn == 'Fire' and vtype_counts.get('warning_fire', 0) > 0:
        labels.append('warning_fire')
    if cn == 'Smoke' and vtype_counts.get('warning_smoke', 0) > 0:
        labels.append('warning_smoke')
    if cn == 'Person':
        cx = (d.bbox[0] + d.bbox[2]) / 2.0
        cy = (d.bbox[1] + d.bbox[3]) / 2.0
        for vtype, centers in warning_centers.items():
            for wcx, wcy in centers:
                dist = ((cx - wcx) ** 2 + (cy - wcy) ** 2) ** 0.5
                if dist < match_threshold and vtype not in labels:
                    labels.append(vtype)
    return labels


@router.post('/detect', response_model=ImageDetectResponse)
def detect_image(req: ImageDetectRequest, db: Session = Depends(get_db)):
    """Run hazard detection on an uploaded image using selected models."""
    registry = get_registry()

    full_path = str(BASE_DIR / req.file_path.lstrip('/'))
    frame = cv2.imread(full_path)
    if frame is None:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to read image: {full_path}",
        )
    img_height, img_width = frame.shape[:2]

    # Build DangerDetector with custom detection_items
    danger = DangerDetector(
        detection_items=req.danger_rules if req.danger_rules else None,
    )

    all_detections: list[DetectionItem] = []
    all_violations: list[dict[str, Any]] = []
    all_cone_polygons: list[list[list[float]]] = []
    all_warnings_raw: dict[str, dict[str, Any]] = {}

    models_to_run = req.models or ['ppe']
    thresholds = req.thresholds or {}

    for model_key in models_to_run:
        try:
            detector = registry.get_model(model_key)
        except ValueError:
            logger.warning(f"Unknown model key '{model_key}', skipping")
            continue

        cfg = registry.get_config(model_key)
        conf_threshold = thresholds.get(model_key, 0.25)

        results = detector.detect_image(frame, conf_threshold=conf_threshold)

        for r in results:
            r.source_model = model_key

        cls_to_name: dict[int, str] = {}
        for k, v in cfg.get('classes', {}).items():
            cls_to_name[int(k)] = str(v)

        if cfg.get('danger_rules', False):
            datas = [[*r.bbox, r.confidence, r.class_id] for r in results]
            warnings, warnings_only, cpolys = danger.detect_danger(datas)
            all_cone_polygons.extend(cpolys)
            for k, v in warnings.items():
                if isinstance(v, dict):
                    all_violations.append({
                        'type': k,
                        'count': int(v.get('count', 0)),
                    })
                    all_warnings_raw[k] = v
            for k, v in warnings_only.items():
                if isinstance(v, dict):
                    all_violations.append({
                        'type': k,
                        'count': int(v.get('count', 0)),
                    })
                    all_warnings_raw[k] = v
        else:
            violation_map = cfg.get('violation_types', {})
            fire_count = 0
            smoke_count = 0
            for r in results:
                class_name = cls_to_name.get(r.class_id, '')
                if class_name in violation_map:
                    vtype = violation_map[class_name]
                    if vtype == 'warning_fire':
                        fire_count += 1
                    elif vtype == 'warning_smoke':
                        smoke_count += 1
            if fire_count > 0:
                all_violations.append({
                    'type': 'warning_fire',
                    'count': fire_count,
                })
            if smoke_count > 0:
                all_violations.append({
                    'type': 'warning_smoke',
                    'count': smoke_count,
                })

        for r in results:
            all_detections.append(
                DetectionItem(
                    bbox=r.bbox,
                    confidence=r.confidence,
                    class_id=r.class_id,
                    class_name=cls_to_name.get(r.class_id, f'Unknown({r.class_id})'),
                    source_model=model_key,
                ),
            )

    merged_violations = _merge_violations(all_violations)
    vtype_counts: dict[str, int] = {
        v['type']: v['count'] for v in merged_violations
    }

    # Mark is_violation on each detection based on warnings
    warning_objects_centers: dict[str, list[tuple[float, float]]] = {}
    for vtype, vdata in all_warnings_raw.items():
        if not isinstance(vdata, dict):
            continue
        for obj in vdata.get('objects', []):
            bbox = obj['bbox']
            cx = (bbox[0] + bbox[2]) / 2.0
            cy = (bbox[1] + bbox[3]) / 2.0
            warning_objects_centers.setdefault(vtype, []).append((cx, cy))
    for d in all_detections:
        labels = _get_detection_violation_labels(d, vtype_counts, warning_objects_centers, img_width)
        if labels:
            d.is_violation = True
            d.violation_labels = labels

    ppe_detections = [d for d in all_detections if d.source_model == 'ppe']
    violation_count = sum(1 for v in vtype_counts.values() if v > 0)

    record = detection_service.create_record(
        db,
        filename=Path(req.file_path).name,
        file_type='image',
        file_path=req.file_path,
        total_objects=len(all_detections),
        violation_count=violation_count,
        violation_counts=vtype_counts,
    )

    # Only save violation screenshot for PPE-related violations
    if vtype_counts:
        filename = f"{uuid.uuid4().hex[:12]}_frame0.jpg"
        screenshot_path = VIOLATION_DIR / filename
        annotated = draw_annotations(frame, [], all_warnings_raw, all_cone_polygons)
        cv2.imwrite(str(screenshot_path), annotated, [cv2.IMWRITE_JPEG_QUALITY, 85])

        for vtype, vdata in vtype_counts.items():
            if vdata > 0:
                detection_service.create_violation(
                    db,
                    record_id=record.id,
                    violation_type=vtype,
                    bbox=[],
                    confidence=0.0,
                    screenshot_path=f'/violations/{filename}',
                )

    db.commit()

    return ImageDetectResponse(
        image=base64.b64encode(
            cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes(),
        ).decode('utf-8'),
        detections=all_detections,
        violations=[ViolationItem(**v) for v in merged_violations],
        cone_polygons=all_cone_polygons,
        total_objects=len(all_detections),
        record_id=record.id,
    )
