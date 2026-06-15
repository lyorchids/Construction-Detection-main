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

from app.config import VIOLATION_DIR
from app.core.annotator import draw_annotations
from app.core.danger_rules import DangerDetector
from app.core.model_registry import ModelRegistry
from app.core.violation_state import PersonStateManager
from app.database import SessionLocal
from app.services import detection_service

logger = logging.getLogger(__name__)


class VideoStreamer:
    """Stream video frames with real-time detection via WebSocket.

    Features:
    - Time-interval based detection (configurable interval in seconds)
    - Per-person violation state machine (hysteresis + cooldown)
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
        self._seen_person_violations: set[tuple[str | int, str]] = set()
        self._saved_violation_types: set[str] = set()
        self._violation_type_screenshot: dict[str, tuple[str, int]] = {}
        self.models: list[str] = ['ppe']
        self.thresholds: dict[str, float] = {}
        self.detection_interval: float = 1.0

        # State machine manager
        self._state_manager = PersonStateManager()

        # Cache for non-detection frames
        self._cached_raw: list[Any] = []
        self._cached_tracked: list[Any] = []
        self._cached_cone_polygons: list[list[list[float]]] = []
        self._cached_pole_polygons: list[list[list[float]]] = []

    def _match_violation_objects_to_tracks(
        self,
        violations_objects: list[dict],
        tracked: list,
    ) -> dict[tuple[str, int | str], dict]:
        """Match violation object bboxes to tracked persons by IoU.

        Returns {(violation_type, track_id): info_dict}.
        """
        result: dict[tuple[str, int | str], dict] = {}

        for vobj in violations_objects:
            vtype = vobj['type']
            vbbox = vobj['bbox']
            vconf = vobj.get('confidence', 0.0)

            best_iou = 0.3
            best_track: int | str | None = None

            for d in tracked:
                if d.class_id != 5:
                    continue
                iou = self._bbox_iou(vbbox, d.bbox)
                if iou > best_iou and d.track_id is not None:
                    best_iou = iou
                    best_track = d.track_id

            if best_track is None:
                best_track = -1

            key = (vtype, best_track)
            if key not in result or vconf > result[key].get('confidence', 0):
                result[key] = {'bbox': vbbox, 'confidence': vconf}

        return result

    @staticmethod
    def _bbox_iou(bbox1: list[float], bbox2: list[float]) -> float:
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])
        inter = max(0, x2 - x1) * max(0, y2 - y1)
        if inter == 0:
            return 0.0
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])
        return inter / (area1 + area2 - inter)

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
            v_no_safety_vest=violation_type_counts.get('warning_no_safety_vest', 0),
            v_close_to_machinery=violation_type_counts.get('warning_close_to_machinery', 0),
            v_close_to_vehicle=violation_type_counts.get('warning_close_to_vehicle', 0),
            v_in_controlled_area=violation_type_counts.get('warning_people_in_controlled_area', 0),
            v_in_pole_area=violation_type_counts.get('warning_people_in_utility_pole_controlled_area', 0),
        )
        db.commit()
        record_id = record.id

        pending_violations: list[tuple] = []
        detection_count = 0
        self._last_detection_time = 0.0
        self._state_manager.reset()

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
                new_violation_events: list[tuple] = []
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

                    # --- State machine based violation detection ---
                    new_violation_events = self._process_violations_with_state(
                        all_tracked, all_warnings, frame_number, timestamp,
                    )
                    unique_violations += len(new_violation_events)
                    active_track_ids: set[int] = set()
                    for d in all_tracked:
                        if d.track_id is not None:
                            active_track_ids.add(d.track_id)
                    self._state_manager.clean_stale(active_track_ids)

                    if new_violation_events:
                        for vtype, tid, bbox, conf in new_violation_events:
                            violation_type_counts[vtype] = violation_type_counts.get(vtype, 0) + 1
                            pending_violations.append((
                                vtype, bbox, conf, frame_number, timestamp,
                            ))

                            if self.save_screenshots and vtype not in self._saved_violation_types:
                                if vtype in ('warning_no_safety_vest', 'warning_no_mask', 'warning_fire', 'warning_smoke'):
                                    continue
                                filename = f"{uuid.uuid4().hex[:12]}.jpg"
                                screenshot_path = VIOLATION_DIR / filename
                                annotated = draw_annotations(frame, all_tracked, all_warnings)
                                cv2.imwrite(
                                    str(screenshot_path), annotated,
                                    [cv2.IMWRITE_JPEG_QUALITY, 85],
                                )
                                self._saved_violation_types.add(vtype)
                                self._violation_type_screenshot[vtype] = (filename, frame_number)

                # Build violation state info (every frame)
                active_counts = self._state_manager.get_active_violation_counts(timestamp)
                violation_bboxes = [
                    {'type': vtype, 'count': count}
                    for vtype, count in active_counts.items()
                ]

                # Get per-track active violations for is_violation marking
                active_viols = self._state_manager.get_active_violations(timestamp)
                violating_tracks: dict[int, list[str]] = {}
                active_vtype_set: set[str] = set()
                for av in active_viols:
                    tid = av['track_id']
                    vtype = av['type']
                    active_vtype_set.add(vtype)
                    violating_tracks.setdefault(tid, []).append(vtype)

                detections_payload = [
                    {
                        'bbox': d.bbox,
                        'confidence': d.confidence,
                        'class_id': d.class_id,
                        'class_name': d.class_name,
                        'track_id': d.track_id,
                        'is_moving': d.is_moving,
                        'source_model': d.source_model,
                        'is_violation': (
                            d.track_id in violating_tracks
                            or (d.class_name == 'Fire' and 'warning_fire' in active_vtype_set)
                            or (d.class_name == 'Smoke' and 'warning_smoke' in active_vtype_set)
                        ),
                        'violation_labels': (
                            violating_tracks.get(d.track_id, [])
                            + (['warning_fire'] if d.class_name == 'Fire' and 'warning_fire' in active_vtype_set else [])
                            + (['warning_smoke'] if d.class_name == 'Smoke' and 'warning_smoke' in active_vtype_set else [])
                        ),
                    }
                    for d in self._cached_tracked
                ]

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

            if frame_number > 0:
                for vtype, bbox, conf, fn, ts in pending_violations:
                    if vtype in ('warning_no_safety_vest', 'warning_no_mask', 'warning_fire', 'warning_smoke'):
                        continue
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

                record.total_objects = total_objects
                record.violation_count = unique_violations
                record.v_no_hardhat = violation_type_counts.get('warning_no_hardhat', 0)
                record.v_no_safety_vest = violation_type_counts.get('warning_no_safety_vest', 0)
                record.v_close_to_machinery = violation_type_counts.get('warning_close_to_machinery', 0)
                record.v_close_to_vehicle = violation_type_counts.get('warning_close_to_vehicle', 0)
                record.v_in_controlled_area = violation_type_counts.get('warning_people_in_controlled_area', 0)
                record.v_in_pole_area = violation_type_counts.get('warning_people_in_utility_pole_controlled_area', 0)
                db.commit()

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
            db.close()
            cap.release()
            self._stopped = False
            self._seen_person_violations.clear()
            self._saved_violation_types.clear()
            self._violation_type_screenshot.clear()
            self._state_manager.reset()
            self._cached_raw.clear()
            self._cached_tracked.clear()
            self._cached_cone_polygons.clear()
            self._cached_pole_polygons.clear()
            logger.info(
                f"Streaming finished: {frame_number} frames, "
                f"{detection_count} detection frames, "
                f"{unique_violations} violations"
            )

    def _process_violations_with_state(
        self,
        tracked: list,
        warnings: dict[str, Any],
        frame_number: int,
        timestamp: float,
    ) -> list[tuple[str, int | str, list[float], float]]:
        """Process violations through per-person state machines.

        Returns deduplicated violation events (with hysteresis + cooldown).
        """
        new_events: list[tuple[str, int | str, list[float], float]] = []
        now = timestamp

        for vtype, vdata in warnings.items():
            if vtype in ('warning_fire', 'warning_smoke'):
                fire_track_id = -2 if vtype == 'warning_fire' else -3
                is_active = vdata.get('count', 0) > 0
                triggered = self._state_manager.update_violation(
                    fire_track_id, vtype, is_active,
                    timestamp=now,
                )
                bbox = [0, 0, 0, 0]
                if triggered:
                    new_events.append((vtype, fire_track_id, bbox, 1.0))
                continue

            objects = vdata.get('objects', []) if isinstance(vdata, dict) else []
            if not objects:
                continue

            if vtype == 'warning_no_hardhat':
                violation_objects = [
                    {'type': vtype, 'bbox': o['bbox'], 'confidence': o.get('confidence', 0.0)}
                    for o in objects
                ]
            elif vtype == 'warning_no_mask':
                violation_objects = [
                    {'type': vtype, 'bbox': o['bbox'], 'confidence': o.get('confidence', 0.0)}
                    for o in objects
                ]
            elif vtype == 'warning_no_safety_vest':
                violation_objects = [
                    {'type': vtype, 'bbox': o['bbox'], 'confidence': o.get('confidence', 0.0)}
                    for o in objects
                ]
            elif vtype in (
                'warning_close_to_machinery', 'warning_close_to_vehicle',
                'warning_people_in_controlled_area',
                'warning_people_in_utility_pole_controlled_area',
            ):
                violation_objects = [
                    {'type': vtype, 'bbox': o['bbox'], 'confidence': o.get('confidence', 0.0)}
                    for o in objects
                ]
            else:
                continue

            matched = self._match_violation_objects_to_tracks(violation_objects, tracked)
            matched_track_ids: set[int] = set()
            for (vtype_key, track_id), info in matched.items():
                matched_track_ids.add(track_id)
                triggered = self._state_manager.update_violation(
                    track_id, vtype_key, True,
                    bbox=info['bbox'], confidence=info['confidence'],
                    timestamp=now,
                )
                if triggered:
                    new_events.append((vtype_key, track_id, info['bbox'], info['confidence']))

            # Only unmatched persons get False for this violation type
            active_track_ids = {d.track_id for d in tracked if d.track_id is not None}
            for tid in active_track_ids - matched_track_ids:
                self._state_manager.update_violation(tid, vtype, False, timestamp=now)

        # Absent violation types
        present_vtypes = set(warnings.keys())
        all_active_track_ids = {d.track_id for d in tracked if d.track_id is not None}
        self._state_manager.mark_absent_violations(
            all_active_track_ids, present_vtypes, now,
        )

        return new_events

    def _find_new_violations(
        self,
        tracked: list,
        warnings: dict[str, Any],
        frame_number: int,
        timestamp: float,
    ) -> list[tuple[str, int | str, list[float], float]]:
        """Delegates to state-machine method."""
        return self._process_violations_with_state(tracked, warnings, frame_number, timestamp)

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._stopped = True
