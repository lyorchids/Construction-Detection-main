from __future__ import annotations

import logging
import warnings
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

warnings.filterwarnings('ignore', message='__floordiv__ is deprecated')

logger = logging.getLogger(__name__)

CLASS_NAMES: dict[int, str] = {
    0: 'Hardhat',
    1: 'Mask',
    2: 'NO-Hardhat',
    3: 'NO-Mask',
    4: 'NO-Safety Vest',
    5: 'Person',
    6: 'Safety Cone',
    7: 'Safety Vest',
    8: 'Machinery',
    9: 'Utility Pole',
    10: 'Vehicle',
}


@dataclass
class DetectionResult:
    bbox: list[float]
    confidence: float
    class_id: int
    class_name: str
    track_id: int | None = None
    is_moving: bool = False


def _nms_deduplicate(
    detections: list[DetectionResult],
    iou_threshold: float = 0.5,
) -> list[DetectionResult]:
    """Remove duplicate detections by class-wise NMS.

    Groups detections by class_id, then for each group removes
    boxes with IoU > threshold, keeping the highest confidence.

    Args:
        detections: List of detection results.
        iou_threshold: IoU threshold for deduplication.

    Returns:
        Deduplicated list of DetectionResult.
    """
    if not detections:
        return []

    by_class: dict[int, list[DetectionResult]] = {}
    for d in detections:
        by_class.setdefault(d.class_id, []).append(d)

    result: list[DetectionResult] = []

    for cls_id, items in by_class.items():
        items.sort(key=lambda x: x.confidence, reverse=True)
        keep: list[DetectionResult] = []

        while items:
            best = items.pop(0)
            keep.append(best)
            items = [
                d for d in items
                if _iou(best.bbox, d.bbox) <= iou_threshold
            ]

        result.extend(keep)

    return result


def _iou(box1: list[float], box2: list[float]) -> float:
    """Calculate IoU between two bounding boxes."""
    x1 = max(box1[0], box2[0])
    y1 = max(box1[1], box2[1])
    x2 = min(box1[2], box2[2])
    y2 = min(box1[3], box2[3])

    inter_area = max(0, x2 - x1) * max(0, y2 - y1)
    area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
    area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
    union_area = area1 + area2 - inter_area

    return inter_area / union_area if union_area > 0 else 0.0


class YOLODetector:
    """YOLO-based object detector for construction hazard detection."""

    def __init__(
        self,
        model_path: str,
        device: str = 'cpu',
        movement_thr: float = 40.0,
        max_id_keep: int = 10,
    ) -> None:
        """Initialise the YOLO detector.

        Args:
            model_path: Path to the YOLO model file (.pt or .onnx).
            device: Device to run inference on ('cpu' or 'cuda:0').
            movement_thr: Pixel movement threshold for tracking.
            max_id_keep: Frames to retain inactive track IDs.
        """
        self.model_path = model_path
        self.device = device
        self.movement_thr = movement_thr
        self.movement_thr_sq = movement_thr * movement_thr
        self.max_id_keep = max_id_keep

        self.model = self._load_model()

        self.prev_centers: dict[int, tuple[float, float]] = {}
        self.prev_centers_last_seen: dict[int, int] = {}
        self.frame_count = 0

    def _load_model(self) -> YOLO:
        """Load YOLO model from .pt or .onnx file.

        Returns:
            Loaded YOLO model instance.

        Raises:
            FileNotFoundError: If model file does not exist.
        """
        model_file = Path(self.model_path)
        if not model_file.exists():
            raise FileNotFoundError(
                f"Model file not found: {self.model_path}",
            )

        logger.info(f"Loading model from {self.model_path}")
        model = YOLO(str(model_file))

        if self.device == 'cuda:0':
            model.to('cuda')

        logger.info(f"Model loaded successfully on {self.device}")
        return model

    def detect_image(
        self,
        image: np.ndarray,
    ) -> list[DetectionResult]:
        """Run detection on a single image.

        Args:
            image: Input image as numpy array (BGR format).

        Returns:
            List of DetectionResult objects.
        """
        results = self.model(image, verbose=False)
        boxes = results[0].boxes

        if len(boxes) == 0:
            return []

        xyxy_batch = boxes.xyxy.tolist()
        conf_batch = boxes.conf.tolist()
        cls_batch = boxes.cls.tolist()

        detections: list[DetectionResult] = []
        for i in range(len(boxes)):
            bbox = [float(x) for x in xyxy_batch[i]]
            conf = float(conf_batch[i])
            cls_id = int(cls_batch[i])
            class_name = CLASS_NAMES.get(cls_id, f'Unknown({cls_id})')

            detections.append(
                DetectionResult(
                    bbox=bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=class_name,
                ),
            )

        return _nms_deduplicate(detections)

    def detect_image_with_tracking(
        self,
        image: np.ndarray,
    ) -> tuple[list[DetectionResult], list[DetectionResult]]:
        """Run detection on a single image (for image detection endpoint).

        Args:
            image: Input image as numpy array (BGR format).

        Returns:
            Tuple of (raw_detections, tracked_detections).
        """
        self.frame_count += 1

        results = self.model(image, verbose=False)
        boxes = results[0].boxes

        if len(boxes) == 0:
            return [], []

        xyxy_batch = boxes.xyxy.tolist()
        conf_batch = boxes.conf.tolist()
        cls_batch = boxes.cls.tolist()

        raw_detections: list[DetectionResult] = []
        tracked_detections: list[DetectionResult] = []

        for i in range(len(boxes)):
            bbox = [float(x) for x in xyxy_batch[i]]
            conf = float(conf_batch[i])
            cls_id = int(cls_batch[i])
            class_name = CLASS_NAMES.get(cls_id, f'Unknown({cls_id})')

            raw_detections.append(
                DetectionResult(
                    bbox=bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=class_name,
                ),
            )

            tracked_detections.append(
                DetectionResult(
                    bbox=bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=class_name,
                ),
            )

        raw_detections = _nms_deduplicate(raw_detections)
        tracked_detections = _nms_deduplicate(tracked_detections)

        return raw_detections, tracked_detections

    def detect_frame(
        self,
        frame: np.ndarray,
    ) -> tuple[list[DetectionResult], list[DetectionResult]]:
        """Run detection with tracking on a single frame.

        Args:
            frame: Input frame as numpy array (BGR format).

        Returns:
            Tuple of (raw_detections, tracked_detections).
        """
        self.frame_count += 1

        results = self.model.track(
            frame, persist=True, verbose=False,
        )
        boxes = results[0].boxes

        if len(boxes) == 0:
            self._cleanup_prev_centers()
            return [], []

        ids = (
            results[0].boxes.id
            if results[0].boxes.id is not None
            else [-1] * len(boxes)
        )

        xyxy_batch = boxes.xyxy.tolist()
        conf_batch = boxes.conf.tolist()
        cls_batch = boxes.cls.tolist()

        raw_detections: list[DetectionResult] = []
        tracked_detections: list[DetectionResult] = []

        for i in range(len(boxes)):
            bbox = [float(x) for x in xyxy_batch[i]]
            conf = float(conf_batch[i])
            cls_id = int(cls_batch[i])
            class_name = CLASS_NAMES.get(cls_id, f'Unknown({cls_id})')
            track_id = (
                int(ids[i])
                if ids is not None and ids[i] is not None
                else -1
            )

            cx = (bbox[0] + bbox[2]) * 0.5
            cy = (bbox[1] + bbox[3]) * 0.5
            is_moving = False

            if track_id != -1:
                prev_c = self.prev_centers.get(track_id)
                if prev_c:
                    distance_sq = (
                        (cx - prev_c[0]) ** 2 + (cy - prev_c[1]) ** 2
                    )
                    is_moving = distance_sq > self.movement_thr_sq

                self.prev_centers[track_id] = (cx, cy)
                self.prev_centers_last_seen[track_id] = self.frame_count

            raw_detections.append(
                DetectionResult(
                    bbox=bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=class_name,
                ),
            )

            tracked_detections.append(
                DetectionResult(
                    bbox=bbox,
                    confidence=conf,
                    class_id=cls_id,
                    class_name=class_name,
                    track_id=track_id if track_id != -1 else None,
                    is_moving=is_moving,
                ),
            )

        self._cleanup_prev_centers()

        raw_detections = _nms_deduplicate(raw_detections)
        tracked_detections = _nms_deduplicate(tracked_detections)

        return raw_detections, tracked_detections

    def _cleanup_prev_centers(self) -> None:
        """Remove tracking info for objects not seen recently."""
        if self.frame_count % 10 == 0:
            current_frame = self.frame_count
            expired_ids = [
                tid
                for tid, last_seen in self.prev_centers_last_seen.items()
                if current_frame - last_seen > self.max_id_keep
            ]
            for tid in expired_ids:
                self.prev_centers.pop(tid, None)
                self.prev_centers_last_seen.pop(tid, None)

    def close(self) -> None:
        """Release resources."""
        import gc
        gc.collect()
        logger.info('YOLODetector resources released')
