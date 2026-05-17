from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np

from app.core.detector import CLASS_NAMES, YOLODetector

MODEL_PATH = Path(__file__).resolve().parent/ 'models' / 'yolo26l.pt'


def test_detector_init() -> None:
    """Test detector initialisation."""
    if not MODEL_PATH.exists():
        print(f"SKIP: Model not found at {MODEL_PATH}")
        print("Place your model file at backend/models/best.pt")
        return

    detector = YOLODetector(str(MODEL_PATH))
    print(f"OK: Detector initialised with {len(CLASS_NAMES)} classes")
    detector.close()


def test_detect_image() -> None:
    """Test detection on a dummy image."""
    if not MODEL_PATH.exists():
        print("SKIP: Model not found")
        return

    detector = YOLODetector(str(MODEL_PATH))

    dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
    detections = detector.detect_image(dummy_image)
    print(f"OK: Detected {len(detections)} objects on dummy image")

    detector.close()


def test_detect_frame() -> None:
    """Test detection with tracking on a dummy frame."""
    if not MODEL_PATH.exists():
        print("SKIP: Model not found")
        return

    detector = YOLODetector(str(MODEL_PATH))

    dummy_frame = np.zeros((640, 640, 3), dtype=np.uint8)
    raw, tracked = detector.detect_frame(dummy_frame)
    print(f"OK: Raw={len(raw)}, Tracked={len(tracked)}")

    detector.close()


if __name__ == '__main__':
    print("=== YOLODetector Tests ===\n")
    test_detector_init()
    test_detect_image()
    test_detect_frame()
    print("\n=== All tests completed ===")
