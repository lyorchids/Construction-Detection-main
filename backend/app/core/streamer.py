from __future__ import annotations

import asyncio
import base64
import logging
import time
import uuid
from pathlib import Path
from typing import Any, Optional

import cv2
from fastapi import WebSocket

from app.config import MODEL_PATH, VIOLATION_DIR
from app.core.annotator import draw_annotations
from app.core.danger_rules import DangerDetector
from app.core.detector import YOLODetector
from app.database import SessionLocal
from app.services import detection_service

logger = logging.getLogger(__name__)


class VideoStreamer:
    """Stream video frames with real-time detection via WebSocket."""

    def __init__(
        self,
        detector: YOLODetector,
        danger_detector: DangerDetector,
        target_fps: int = 30,
    ) -> None:
        self.detector = detector
        self.danger_detector = danger_detector
        self.target_fps = target_fps
        self.frame_interval = 1.0 / target_fps
        self._paused = False
        self._stopped = False
        self._seen_person_violations: set[tuple[str | int, str]] = set()
        self._saved_violation_types: set[str] = set()
        self._violation_type_screenshot: dict[str, tuple[str, int]] = {}

    async def stream(
        self,
        video_path: str,
        websocket: WebSocket,
    ) -> None:
        """Stream video with detection to WebSocket client.

        Args:
            video_path: Path to the video file.
            websocket: WebSocket connection to send frames to.
        """
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
        current_frame_violation_types: set[str] = set()

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
                current_frame_violation_types.clear()

                raw_detections, tracked = self.detector.detect_frame(frame)
                total_objects += len(raw_detections)

                datas = [
                    [
                        *d.bbox,
                        d.confidence,
                        d.class_id,
                    ]
                    for d in raw_detections
                ]

                warnings, warnings_only, _, _ = self.danger_detector.detect_danger(datas)

                violation_bboxes = [
                    {'type': vtype, 'count': vdata.get('count', 0)}
                    for vtype, vdata in warnings.items()
                ]

                new_violations = self._find_new_violations(
                    tracked, warnings, frame_number, timestamp,
                )
                unique_violations += len(new_violations)

                if new_violations:
                    for vtype, tid, bbox, conf in new_violations:
                        violation_type_counts[vtype] = violation_type_counts.get(vtype, 0) + 1
                        pending_violations.append((
                            vtype, bbox, conf, frame_number, timestamp,
                        ))
                        current_frame_violation_types.add(vtype)

                        if vtype not in self._saved_violation_types:
                            if vtype == 'warning_no_safety_vest':
                                continue
                            filename = f"{uuid.uuid4().hex[:12]}.jpg"
                            screenshot_path = VIOLATION_DIR / filename
                            annotated = draw_annotations(frame, tracked, warnings)
                            cv2.imwrite(
                                str(screenshot_path), annotated,
                                [cv2.IMWRITE_JPEG_QUALITY, 85],
                            )
                            self._saved_violation_types.add(vtype)
                            self._violation_type_screenshot[vtype] = (filename, frame_number)

                detections_payload = [
                    {
                        'bbox': d.bbox,
                        'confidence': d.confidence,
                        'class_id': d.class_id,
                        'class_name': d.class_name,
                        'track_id': d.track_id,
                        'is_moving': d.is_moving,
                    }
                    for d in tracked
                ]

                annotated = draw_annotations(frame, tracked, warnings)
                _, buffer = cv2.imencode(
                    '.jpg', annotated, [cv2.IMWRITE_JPEG_QUALITY, 80],
                )
                frame_b64 = base64.b64encode(buffer.tobytes()).decode('utf-8')

                frame_data = {
                    'type': 'frame',
                    'frame_number': frame_number,
                    'timestamp': round(timestamp, 2),
                    'image': frame_b64,
                    'detections': detections_payload,
                    'violations': violation_bboxes,
                }

                await websocket.send_json(frame_data)

                elapsed = time.time() - start_time
                expected = frame_number * self.frame_interval
                sleep_time = expected - elapsed
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)

            if frame_number > 0:
                for vtype, bbox, conf, fn, ts in pending_violations:
                    if vtype == 'warning_no_safety_vest':
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
                db.commit()

                await websocket.send_json({
                    'type': 'complete',
                    'record_id': record_id,
                    'total_objects': total_objects,
                    'total_violations': unique_violations,
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
            logger.info(f"Streaming finished: {frame_number} frames")

    def _find_new_violations(
        self,
        tracked: list,
        warnings: dict[str, Any],
        frame_number: int,
        timestamp: float,
    ) -> list[tuple[str, int | str, list[float], float]]:
        """Find new violations by tracking person IDs.

        Returns list of (violation_type, track_id, bbox, confidence).
        """
        if not warnings:
            return []

        new_violations: list[tuple[str, int | str, list[float], float]] = []

        for vtype in warnings:
            if vtype == 'warning_no_hardhat':
                for d in tracked:
                    if d.class_id == 2:
                        tid = d.track_id if d.track_id is not None else f'unknown_{frame_number}'
                        key = (tid, vtype)
                        if key not in self._seen_person_violations:
                            self._seen_person_violations.add(key)
                            new_violations.append(
                                (vtype, tid, d.bbox, d.confidence),
                            )

            elif vtype == 'warning_no_safety_vest':
                for d in tracked:
                    if d.class_id == 4:
                        tid = d.track_id if d.track_id is not None else f'unknown_{frame_number}'
                        key = (tid, vtype)
                        if key not in self._seen_person_violations:
                            self._seen_person_violations.add(key)
                            new_violations.append(
                                (vtype, tid, d.bbox, d.confidence),
                            )

            elif vtype in (
                'warning_close_to_machinery',
                'warning_close_to_vehicle',
            ):
                for d in tracked:
                    if d.class_id == 5:
                        tid = d.track_id if d.track_id is not None else f'unknown_{frame_number}'
                        key = (tid, vtype)
                        if key not in self._seen_person_violations:
                            self._seen_person_violations.add(key)
                            new_violations.append(
                                (vtype, tid, d.bbox, d.confidence),
                            )

            elif vtype in (
                'warning_people_in_controlled_area',
                'warning_people_in_utility_pole_controlled_area',
            ):
                for d in tracked:
                    if d.class_id == 5:
                        tid = d.track_id if d.track_id is not None else f'unknown_{frame_number}'
                        key = (tid, vtype)
                        if key not in self._seen_person_violations:
                            self._seen_person_violations.add(key)
                            new_violations.append(
                                (vtype, tid, d.bbox, d.confidence),
                            )

        return new_violations

    def pause(self) -> None:
        self._paused = True

    def resume(self) -> None:
        self._paused = False

    def stop(self) -> None:
        self._stopped = True
