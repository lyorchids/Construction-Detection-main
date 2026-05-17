from __future__ import annotations

import argparse
import asyncio
import gc
import logging
import os
from pathlib import Path

import cv2
import numpy as np
from dotenv import load_dotenv
from sahi import AutoDetectionModel
from sahi.predict import get_sliced_prediction
from ultralytics import YOLO

# Load environment variables for configuration
load_dotenv()


class LiveStreamDetector:
    """
    A class to perform live stream detection and tracking
    using YOLO with SAHI (local inference only).
    """

    def __init__(
        self,
        model_key: str = 'yolo26n',
        output_folder: str | None = None,
        use_ultralytics: bool = True,
        movement_thr: float = 40.0,
        fps: int = 1,
        max_id_keep: int = 10,
    ) -> None:
        """Initialise the LiveStreamDetector with specified configuration.

        Args:
            model_key: YOLO model identifier.
            output_folder: Optional directory for saving outputs.
            use_ultralytics: Use Ultralytics engine (else SAHI slicing).
            movement_thr: Pixel movement threshold (centroid distance).
            fps: Target FPS (reserved for future time-based logic).
            max_id_keep: Frames to retain inactive track IDs.
        """
        self.model_key = model_key
        self.output_folder = output_folder
        self.use_ultralytics = use_ultralytics

        # Models (local inference path)
        if self.use_ultralytics:
            self.ultralytics_model = YOLO(
                f"models/pt/best_{self.model_key}.pt",
            )
        else:
            self.model = AutoDetectionModel.from_pretrained(
                'yolo26',
                model_path=str(
                    Path('models/pt') /
                    f"best_{self.model_key}.pt",
                ),
                device='cuda:0',
            )

        self._logger = logging.getLogger(__name__)

        # Tracking state stores
        self.prev_centers: dict[int, tuple[float, float]] = {}
        self.prev_centers_last_seen: dict[int, int] = {}
        self.movement_thr = movement_thr
        self.movement_thr_sq = movement_thr * movement_thr
        self.frame_count = 0
        self.max_id_keep = max_id_keep

    async def _detect_local(self, frame: np.ndarray) -> list[list[float]]:
        """Perform object detection using local YOLO models.

        This method runs inference locally using either Ultralytics YOLO or
        SAHI AutoDetectionModel, depending on the configuration.

        Args:
            frame: Input image frame as numpy array for detection.

        Returns:
            List of detection results, where each detection is represented as
            [x1, y1, x2, y2, confidence, class_id].
        """
        if self.use_ultralytics:
            result = self.ultralytics_model(frame)
            boxes = result[0].boxes
            return [
                [
                    *map(float, boxes.xyxy[i].tolist()),
                    float(boxes.conf[i].item()),
                    int(boxes.cls[i].item()),
                ]
                for i in range(len(boxes))
            ]
        else:
            result = get_sliced_prediction(
                frame, self.model,
                slice_height=376, slice_width=376,
                overlap_height_ratio=0.3, overlap_width_ratio=0.3,
            )
            return [
                [
                    *map(int, obj.bbox.to_voc_bbox()),
                    float(obj.score.value),
                    int(obj.category.id),
                ]
                for obj in result.object_prediction_list
            ]

    async def generate_detections(
        self, frame: np.ndarray,
    ) -> tuple[list[list[float]], list[list[float]]]:
        """Generate object detections with tracking information.

        This is the main detection method that coordinates local inference,
        applies object tracking, and manages frame counting.

        Args:
            frame: Input image frame as numpy array for detection.

        Returns:
            Tuple containing:
                - List of raw detection results
                  [x1, y1, x2, y2, confidence, class_id]
                - List of tracked detection results
                  [x1, y1, x2, y2, confidence, class_id, track_id, is_moving]
        """
        self.frame_count += 1

        # Batch process detection results to improve efficiency
        results = self.ultralytics_model.track(
            frame, persist=True, verbose=False,
        )
        boxes = results[0].boxes

        if len(boxes) == 0:
            self._cleanup_prev_centers()
            return [], []

        ids = results[0].boxes.id if results[0].boxes.id is not None else [
            -1,
        ] * len(boxes)

        # Batch calculate all bounding box data
        xyxy_batch = boxes.xyxy.tolist()
        conf_batch = boxes.conf.tolist()
        cls_batch = boxes.cls.tolist()

        datas = []
        tracked = []

        for i in range(len(boxes)):
            xyxy = xyxy_batch[i]
            conf = float(conf_batch[i])
            cls = int(cls_batch[i])
            tid = (
                int(ids[i]) if ids is not None and ids[i] is not None
                else -1
            )

            # Calculate centre point and movement status
            cx, cy = (xyxy[0] + xyxy[2]) * 0.5, (xyxy[1] + xyxy[3]) * 0.5
            is_moving = 0

            if tid != -1:
                prev_c = self.prev_centers.get(tid)
                if prev_c:
                    distance_sq = (
                        (cx - prev_c[0]) ** 2 + (cy - prev_c[1]) ** 2
                    )
                    is_moving = (
                        1 if distance_sq > self.movement_thr_sq else 0
                    )

                self.prev_centers[tid] = (cx, cy)
                self.prev_centers_last_seen[tid] = self.frame_count

            datas.append(xyxy + [conf, cls])
            tracked.append(xyxy + [conf, cls, tid, is_moving])
        self._cleanup_prev_centers()
        return datas, tracked

    def _cleanup_prev_centers(self) -> None:
        """Clean up tracking data for inactive object IDs.

        This method removes tracking information for objects that haven't been
        seen for more than max_id_keep frames to prevent memory leaks and
        maintain tracking performance.
        """
        if self.frame_count % 10 == 0:
            current_frame = self.frame_count
            expired_ids = [
                tid for tid, last_seen in self.prev_centers_last_seen.items()
                if current_frame - last_seen > self.max_id_keep
            ]
            for tid in expired_ids:
                self.prev_centers.pop(tid, None)
                self.prev_centers_last_seen.pop(tid, None)

    async def run_detection(self, stream_url: str) -> None:
        """Run continuous object detection on a video stream.

        This method opens a video stream, performs real-time object detection
        with tracking, and displays the results in a window. The detection
        loop continues until the user presses 'q' to quit.

        Args:
            stream_url: URL or path to the video stream source.

        Raises:
            ValueError: If the stream cannot be opened.
        """
        cap = cv2.VideoCapture(stream_url)
        if not cap.isOpened():
            raise ValueError('Failed to open stream.')
        try:
            while True:
                ret, frame = cap.read()
                if not ret:
                    await asyncio.sleep(1)
                    continue
                datas, tracked = await self.generate_detections(frame)
                disp = frame.copy()
                for d in tracked:
                    x1, y1, x2, y2, _, _, tid, mov = d
                    cv2.rectangle(
                        disp, (int(x1), int(y1)),
                        (int(x2), int(y2)), (0, 255, 0), 2,
                    )
                    cv2.putText(
                        disp, f"ID{tid} M{mov}", (int(x1), int(y1)-5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1,
                    )
                cv2.imshow('Stream', disp)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
        finally:
            cap.release()
            cv2.destroyAllWindows()

    async def close(self) -> None:
        """Clean up resources."""
        pass

    def remove_overlapping_labels(self, datas):
        """
        Removes overlapping labels for Hardhat and Safety Vest categories.

        Args:
            datas (list): A list of detection data in YOLO format.

        Returns:
            list: A list of detection data with overlapping labels removed.
        """
        hardhat_indices = [
            i for i, d in enumerate(
                datas,
            ) if d[5] == 0
        ]
        no_hardhat_indices = [i for i, d in enumerate(datas) if d[5] == 2]
        safety_vest_indices = [i for i, d in enumerate(datas) if d[5] == 7]
        no_safety_vest_indices = [i for i, d in enumerate(datas) if d[5] == 4]

        to_remove = set()
        for hardhat_index in hardhat_indices:
            for no_hardhat_index in no_hardhat_indices:
                overlap = self.overlap_percentage(
                    datas[hardhat_index][:4], datas[no_hardhat_index][:4],
                )
                if overlap > 0.8:
                    to_remove.add(no_hardhat_index)

        for safety_vest_index in safety_vest_indices:
            for no_safety_vest_index in no_safety_vest_indices:
                overlap = self.overlap_percentage(
                    datas[safety_vest_index][:4],
                    datas[no_safety_vest_index][:4],
                )
                if overlap > 0.8:
                    to_remove.add(no_safety_vest_index)

        for index in sorted(to_remove, reverse=True):
            datas.pop(index)

        gc.collect()
        return datas

    def overlap_percentage(self, bbox1, bbox2):
        """
        Calculates the percentage of overlap between two bounding boxes.

        Args:
            bbox1 (list): The first bounding box [x1, y1, x2, y2].
            bbox2 (list): The second bounding box [x1, y1, x2, y2].

        Returns:
            float: The percentage of overlap between the two bounding boxes.
        """
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        intersection_area = max(0, x2 - x1 + 1) * max(0, y2 - y1 + 1)
        bbox1_area = (bbox1[2] - bbox1[0] + 1) * (bbox1[3] - bbox1[1] + 1)
        bbox2_area = (bbox2[2] - bbox2[0] + 1) * (bbox2[3] - bbox2[1] + 1)

        overlap_percentage = intersection_area / float(
            bbox1_area + bbox2_area - intersection_area,
        )
        gc.collect()

        return overlap_percentage

    def is_contained(self, inner_bbox, outer_bbox):
        """
        Determines if one bounding box is completely contained within another.

        Args:
            inner_bbox (list): The inner bounding box [x1, y1, x2, y2].
            outer_bbox (list): The outer bounding box [x1, y1, x2, y2].

        Returns:
            bool: Checks if inner box is fully within outer bounding box.
        """
        return (
            inner_bbox[0] >= outer_bbox[0]
            and inner_bbox[2] <= outer_bbox[2]
            and inner_bbox[1] >= outer_bbox[1]
            and inner_bbox[3] <= outer_bbox[3]
        )

    def remove_completely_contained_labels(self, datas):
        """
        Removes labels fully contained in Hardhat/Safety Vest categories.

        Args:
            datas (list): A list of detection data in YOLO format.

        Returns:
            list: Detection data with fully contained labels removed.
        """
        hardhat_indices = [
            i
            for i, d in enumerate(
                datas,
            )
            if d[5] == 0
        ]

        no_hardhat_indices = [i for i, d in enumerate(datas) if d[5] == 2]

        safety_vest_indices = [i for i, d in enumerate(datas) if d[5] == 7]

        no_safety_vest_indices = [i for i, d in enumerate(datas) if d[5] == 4]

        to_remove = set()
        for hardhat_index in hardhat_indices:
            for no_hardhat_index in no_hardhat_indices:
                if self.is_contained(
                    datas[no_hardhat_index][:4],
                    datas[hardhat_index][:4],
                ):
                    to_remove.add(no_hardhat_index)
                elif self.is_contained(
                    datas[hardhat_index][:4],
                    datas[no_hardhat_index][:4],
                ):
                    to_remove.add(hardhat_index)

        for safety_vest_index in safety_vest_indices:
            for no_safety_vest_index in no_safety_vest_indices:
                if self.is_contained(
                    datas[no_safety_vest_index][:4],
                    datas[safety_vest_index][:4],
                ):
                    to_remove.add(no_safety_vest_index)
                elif self.is_contained(
                    datas[safety_vest_index][:4],
                    datas[no_safety_vest_index][:4],
                ):
                    to_remove.add(safety_vest_index)

        for index in sorted(to_remove, reverse=True):
            datas.pop(index)

        return datas


async def main() -> None:
    """Main execution block for command-line interface."""
    parser = argparse.ArgumentParser(
        description='Live stream detection (local inference only)',
    )
    parser.add_argument(
        '--url', type=str, required=True,
        help='Stream URL or video file path',
    )
    parser.add_argument(
        '--model_key', type=str,
        default='yolo26n', help='YOLO model identifier key',
    )
    parser.add_argument(
        '--use_ultralytics', action='store_true',
        help='Use Ultralytics YOLO for local inference',
    )
    args = parser.parse_args()

    detector = LiveStreamDetector(
        model_key=args.model_key,
        use_ultralytics=args.use_ultralytics,
    )

    await detector.run_detection(args.url)

if __name__ == '__main__':
    asyncio.run(main())
