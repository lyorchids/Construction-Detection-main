from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from pathlib import Path
from typing import Any

import cv2
from fastapi import WebSocket

from app.config import UPLOAD_VIDEO_DIR, VIOLATION_DIR
from app.core.annotator import draw_annotations
from app.core.danger_rules import DangerDetector
from app.core.model_registry import ModelRegistry
from sqlalchemy import update as sql_update

from app.database import SessionLocal
from app.models.detection import DetectionRecord
from app.services import detection_service

logger = logging.getLogger(__name__)


class VideoStreamer:
    """Stream video frames with real-time detection via WebSocket.

    Features:
    - Time-interval based detection (configurable interval in seconds)
    - Direct violation counting from DangerDetector (max concurrent per type)
    - Ultralytics built-in ByteTrack for person tracking
    """

    def __init__(
        self,
        registry: ModelRegistry,
    ) -> None:
        self.danger_detector = DangerDetector()
        self.registry = registry
        self.save_screenshots = True
        self._paused = False
        self._stopped = False
        self._saved_violation_types: set[str] = set()
        self._violation_type_screenshot: dict[str, tuple[str, int]] = {}
        self.models: list[str] = ['ppe']
        self.thresholds: dict[str, float] = {}
        self.detection_interval: float = 0.5

        # Cache for non-detection frames
        self._cached_raw: list[Any] = []
        self._cached_tracked: list[Any] = []
        self._cached_cone_polygons: list[list[list[float]]] = []
        self._cached_pole_polygons: list[list[list[float]]] = []
        self._cached_warnings: dict[str, Any] = {}

    async def stream(
        self,
        video_path: str,
        websocket: WebSocket,
    ) -> None:
        """Stream video with detection to WebSocket client."""
        normalized_path = str(Path(video_path))
        logger.info(f"Attempting to open video: {normalized_path}")

        cap = cv2.VideoCapture(normalized_path)
        if not cap.isOpened():
            logger.error(f"Failed to open video: {normalized_path}")
            await websocket.send_json({
                'type': 'error',
                'message': f'Failed to open video file: {normalized_path}',
            })
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        duration = total_frames / fps if fps > 0 else 0

        logger.info(
            f"Video info: {width}x{height}, {fps}fps, "
            f"{total_frames} frames, {duration:.1f}s"
        )

        await websocket.send_json({
            'type': 'info',
            'fps': fps,
            'total_frames': total_frames,
            'duration': duration,
        })

        frame_number = 0
        frame_start = time.time()
        start_time = time.time()
        total_objects = 0
        unique_violations = 0
        violation_type_counts: dict[str, int] = {}
        db = SessionLocal()

        video_filename = Path(normalized_path).name
        record = detection_service.create_record(
            db,
            filename=video_filename,
            file_type='video',
            file_path=normalized_path,
            total_objects=0,
            violation_count=0,
            duration=duration,
            v_no_hardhat=violation_type_counts.get('warning_no_hardhat', 0),
            v_no_mask=violation_type_counts.get('warning_no_mask', 0),
            v_no_safety_vest=violation_type_counts.get('warning_no_safety_vest', 0),
            v_in_controlled_area=violation_type_counts.get('warning_people_in_controlled_area', 0),
            v_in_pole_area=violation_type_counts.get('warning_people_in_utility_pole_controlled_area', 0),
            v_fire=violation_type_counts.get('warning_fire', 0),
            v_smoke=violation_type_counts.get('warning_smoke', 0),
        )
        db.commit()
        record_id = record.id

        pending_violations: list[tuple] = []
        detection_count = 0
        self._last_detection_time = 0.0

        try:
            while not self._stopped:
                if self._paused:
                    await asyncio.sleep(0.1)
                    continue

                ret, frame = cap.read()
                if not ret:
                    break

                frame_number += 1
                timestamp = frame_number / fps

                # --- Time-based detection gate ---
                now = time.time()
                should_detect = (now - self._last_detection_time) >= self.detection_interval

                all_warnings: dict[str, Any] = {}
                cone_polygons: list[list[list[float]]] = []
                pole_polygons: list[list[list[float]]] = []

                if should_detect:
                    detection_count += 1
                    self._last_detection_time = now

                    all_raw_detections: list[Any] = []
                    all_tracked: list[Any] = []

                    for model_key in self.models:
                        try:
                            detector = self.registry.get_model(model_key)
                        except ValueError:
                            continue

                        cfg = self.registry.get_config(model_key)
                        conf_threshold = self.thresholds.get(model_key, 0.25)

                        raw, tracked = detector.detect_frame(frame, conf_threshold=conf_threshold)

                        cls_to_name: dict[int, str] = {}
                        for k, v in cfg.get('classes', {}).items():
                            cls_to_name[int(k)] = str(v)

                        for r in raw:
                            r.source_model = model_key
                        for t in tracked:
                            t.source_model = model_key

                        all_raw_detections.extend(raw)
                        all_tracked.extend(tracked)

                        if cfg.get('danger_rules', False):
                            datas = [
                                [*d.bbox, d.confidence, d.class_id]
                                for d in raw
                            ]
                            if datas:
                                warnings, warnings_only, cpolys, ppolys = self.danger_detector.detect_danger(datas)
                                cone_polygons.extend(cpolys)
                                pole_polygons.extend(ppolys)
                                for k, v in warnings.items():
                                    if k not in all_warnings:
                                        all_warnings[k] = v
                                    else:
                                        c = v.get('count', 0)
                                        all_warnings[k]['count'] = all_warnings[k].get('count', 0) + c
                                for k, v in warnings_only.items():
                                    if k not in all_warnings:
                                        all_warnings[k] = v
                                    else:
                                        c = v.get('count', 0)
                                        all_warnings[k]['count'] = all_warnings[k].get('count', 0) + c
                        else:
                            violation_map = cfg.get('violation_types', {})
                            for r in raw:
                                class_name = cls_to_name.get(r.class_id, '')
                                if class_name in violation_map:
                                    vtype = violation_map[class_name]
                                    if vtype not in all_warnings:
                                        all_warnings[vtype] = {'count': 0}
                                    all_warnings[vtype]['count'] += 1

                    total_objects += len(all_raw_detections)

                    # Cache results for non-detection frames
                    self._cached_raw = all_raw_detections
                    self._cached_tracked = all_tracked
                    if cone_polygons:
                        self._cached_cone_polygons = cone_polygons
                    if pole_polygons:
                        self._cached_pole_polygons = pole_polygons

                    # --- Direct violation counting (no state machine) ---
                    self._cached_warnings = all_warnings
                    for vtype, vdata in all_warnings.items():
                        if not isinstance(vdata, dict):
                            continue
                        count = vdata.get('count', 0)
                        if count <= 0:
                            continue

                        # Track max count per violation type across frames
                        if count > violation_type_counts.get(vtype, 0):
                            violation_type_counts[vtype] = count

                        # Save first occurrence as pending violation record
                        if not any(p[0] == vtype for p in pending_violations):
                            objects = vdata.get('objects', [])
                            if objects:
                                obj = objects[0]
                                pending_violations.append((
                                    vtype, obj['bbox'], obj.get('confidence', 0.0),
                                    frame_number, timestamp,
                                ))
                            else:
                                pending_violations.append((
                                    vtype, [0, 0, 0, 0], 1.0,
                                    frame_number, timestamp,
                                ))

                    # Fallback: ensure no-mask/fire/smoke are counted from raw detections
                    ppe_mask = len([d for d in all_raw_detections if d.source_model == 'ppe' and d.class_id == 3])
                    fire_cnt = len([d for d in all_raw_detections if d.source_model == 'fire' and d.class_id == 0])
                    smoke_cnt = len([d for d in all_raw_detections if d.source_model == 'fire' and d.class_id == 1])
                    for vtype, cnt in [('warning_no_mask', ppe_mask), ('warning_fire', fire_cnt), ('warning_smoke', smoke_cnt)]:
                        if cnt:
                            violation_type_counts[vtype] = max(violation_type_counts.get(vtype, 0), cnt)
                            if not any(p[0] == vtype for p in pending_violations):
                                pending_violations.append((vtype, [0, 0, 0, 0], 1.0, frame_number, timestamp))

                    # Batch screenshot: one per detection frame covering all present types
                    if self.save_screenshots:
                        types_needing_screenshot = [
                            vtype for vtype in all_warnings
                            if isinstance(all_warnings[vtype], dict)
                            and all_warnings[vtype].get('count', 0) > 0
                            and vtype not in self._saved_violation_types
                        ]
                        if types_needing_screenshot:
                            try:
                                filename = f"{uuid.uuid4().hex[:12]}.jpg"
                                screenshot_path = VIOLATION_DIR / filename
                                annotated = draw_annotations(frame, [], all_warnings)
                                success = cv2.imwrite(
                                    str(screenshot_path), annotated,
                                    [cv2.IMWRITE_JPEG_QUALITY, 85],
                                )
                                if success:
                                    for vtype in types_needing_screenshot:
                                        self._saved_violation_types.add(vtype)
                                        self._violation_type_screenshot[vtype] = (filename, frame_number)
                                else:
                                    logger.error(f"Failed to save screenshot: {screenshot_path}")
                            except Exception:
                                logger.exception("Error saving batch screenshot")

                    unique_violations = len(pending_violations)

                # Violation markers only on detection frames
                if should_detect:
                    violation_bboxes = [
                        {'type': vtype, 'count': count}
                        for vtype, count in violation_type_counts.items()
                        if count > 0
                    ]
                    warning_obj_bboxes: dict[str, list[list[float]]] = {}
                    for vtype, vdata in self._cached_warnings.items():
                        if not isinstance(vdata, dict):
                            continue
                        bboxes = [obj['bbox'] for obj in vdata.get('objects', [])]
                        if bboxes:
                            warning_obj_bboxes[vtype] = bboxes
                    vtype_set = set(violation_type_counts.keys())
                else:
                    violation_bboxes = []
                    vtype_set: set[str] = set()
                    warning_obj_bboxes: dict[str, list[list[float]]] = {}
                detections_payload = []
                for d in self._cached_tracked:
                    labels: list[str] = []
                    if d.class_id == 2 and 'warning_no_hardhat' in vtype_set:
                        labels.append('warning_no_hardhat')
                    if d.class_id == 3 and 'warning_no_mask' in vtype_set:
                        labels.append('warning_no_mask')
                    if d.class_id == 4 and 'warning_no_safety_vest' in vtype_set:
                        labels.append('warning_no_safety_vest')
                    if d.class_name == 'Fire' and 'warning_fire' in vtype_set:
                        labels.append('warning_fire')
                    if d.class_name == 'Smoke' and 'warning_smoke' in vtype_set:
                        labels.append('warning_smoke')
                    if d.class_id == 5:
                        cx = (d.bbox[0] + d.bbox[2]) / 2.0
                        cy = (d.bbox[1] + d.bbox[3]) / 2.0
                        for vtype in ('warning_people_in_controlled_area', 'warning_people_in_utility_pole_controlled_area'):
                            if vtype not in vtype_set:
                                continue
                            for wbbox in warning_obj_bboxes.get(vtype, []):
                                if wbbox[0] <= cx <= wbbox[2] and wbbox[1] <= cy <= wbbox[3]:
                                    labels.append(vtype)
                                    break
                    detections_payload.append({
                        'bbox': d.bbox,
                        'confidence': d.confidence,
                        'class_id': d.class_id,
                        'class_name': d.class_name,
                        'track_id': d.track_id,
                        'is_moving': d.is_moving,
                        'source_model': d.source_model,
                        'is_violation': len(labels) > 0,
                        'violation_labels': labels,
                    })

                _, buffer = cv2.imencode(
                    '.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80],
                )
                frame_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

                frame_data = {
                    'type': 'frame',
                    'frame_number': frame_number,
                    'timestamp': round(timestamp, 2),
                    'image': frame_b64,
                    'detections': detections_payload,
                    'violations': violation_bboxes,
                    'cone_polygons': self._cached_cone_polygons,
                    'pole_polygons': self._cached_pole_polygons,
                }

                await websocket.send_json(frame_data)

                # Throttle to real-time playback speed
                elapsed = time.time() - frame_start
                sleep_time = (1.0 / fps) - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                frame_start = time.time()

            if frame_number > 0:
                await websocket.send_json({
                    'type': 'complete',
                    'record_id': record_id,
                    'total_objects': total_objects,
                    'total_violations': unique_violations,
                    'detection_frames': detection_count,
                })

        except Exception as e:
            logger.error(f"Streaming error: {e}")
            try:
                await websocket.send_json({
                    'type': 'error',
                    'message': str(e),
                })
            except Exception:
                pass
        finally:
            # Always persist record to DB, even if streaming error occurred
            try:
                if frame_number > 0:
                    # 1) Save record counts first (independent from violations)
                    try:
                        db.execute(
                            sql_update(DetectionRecord)
                            .where(DetectionRecord.id == record_id)
                            .values(
                                total_objects=total_objects,
                                violation_count=unique_violations,
                                v_no_hardhat=violation_type_counts.get('warning_no_hardhat', 0),
                                v_no_mask=violation_type_counts.get('warning_no_mask', 0),
                                v_no_safety_vest=violation_type_counts.get('warning_no_safety_vest', 0),
                                v_in_controlled_area=violation_type_counts.get('warning_people_in_controlled_area', 0),
                                v_in_pole_area=violation_type_counts.get('warning_people_in_utility_pole_controlled_area', 0),
                                v_fire=violation_type_counts.get('warning_fire', 0),
                                v_smoke=violation_type_counts.get('warning_smoke', 0),
                            ),
                        )
                        db.commit()
                    except Exception as e2:
                        logger.error(f"Failed to update record counts: {e2}")
                        db.rollback()

                    # 2) Save violation records (best-effort, each independently)
                    for vtype, bbox, conf, fn, ts in pending_violations:
                        try:
                            screenshot = self._violation_type_screenshot.get(vtype)
                            screenshot_path = f'/violations/{screenshot[0]}' if screenshot else ''
                            detection_service.create_violation(
                                db,
                                record_id=record_id,
                                violation_type=vtype,
                                bbox=bbox,
                                confidence=conf,
                                frame_number=fn,
                                timestamp=ts,
                                screenshot_path=screenshot_path,
                            )
                        except Exception as e2:
                            logger.error(f"Failed to save violation {vtype}: {e2}")
                            db.rollback()
            except Exception as e2:
                logger.error(f"Failed to save final record: {e2}")
                db.rollback()

            db.close()
            cap.release()

            # Delete original video file after detection completes
            video_file = Path(normalized_path)
            if video_file.exists() and str(video_file).startswith(str(UPLOAD_VIDEO_DIR)):
                try:
                    video_file.unlink()
                    logger.info(f"Deleted original video: {video_file}")
                except Exception as e:
                    logger.error(f"Failed to delete video {video_file}: {e}")

            self._stopped = False
            self._saved_violation_types.clear()
            self._violation_type_screenshot.clear()
            self._cached_raw.clear()
            self._cached_tracked.clear()
            self._cached_cone_polygons.clear()
            self._cached_pole_polygons.clear()
            logger.info(
                f"Streaming finished: {frame_number} frames, "
                f"{detection_count} detection frames, "
                f"{unique_violations} violations"
            )

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._stopped = True
