from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import DEVICE
from app.core.danger_rules import DangerDetector
from app.core.detector import YOLODetector
from app.core.model_registry import ModelRegistry
from app.core.streamer import VideoStreamer

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/ws/video', tags=['video-detect'])

_detector: YOLODetector | None = None
_danger_detector: DangerDetector | None = None
_registry: ModelRegistry | None = None


def get_detectors() -> tuple[YOLODetector, DangerDetector]:
    global _detector, _danger_detector
    if _detector is None:
        from app.config import MODEL_PATH, DEVICE
        _detector = YOLODetector(str(MODEL_PATH), device=DEVICE)
        _danger_detector = DangerDetector()
    assert _detector is not None and _danger_detector is not None
    return _detector, _danger_detector


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


@router.websocket('/detect/{file_path:path}')
async def websocket_detect(websocket: WebSocket, file_path: str):
    """WebSocket endpoint for real-time video detection.

    Args:
        websocket: WebSocket connection.
        file_path: URL-encoded path to the video file.
    """
    await websocket.accept()

    import urllib.parse
    from app.config import BASE_DIR

    decoded_path = urllib.parse.unquote(file_path)

    if decoded_path.startswith('/uploads/'):
        decoded_path = str(BASE_DIR / decoded_path.lstrip('/'))

    registry = get_registry()

    streamer = VideoStreamer(registry)
    is_streaming = False

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get('action')

            if action == 'start':
                models = data.get('models', ['ppe'])
                thresholds = data.get('thresholds', {})
                danger_rules_raw = data.get('danger_rules')
                every_frame = data.get('every_frame', False)
                detection_interval = data.get('detection_interval', 1.0)
                save_screenshots = data.get('save_screenshots', True)

                detection_items: dict[str, bool] | None = None
                if danger_rules_raw and isinstance(danger_rules_raw, dict):
                    detection_items = {
                        'detect_no_hardhat': danger_rules_raw.get('detect_no_hardhat', True),
                        'detect_no_mask': danger_rules_raw.get('detect_no_mask', True),
                        'detect_no_safety_vest': danger_rules_raw.get('detect_no_safety_vest', True),
                        'detect_near_machinery_or_vehicle': danger_rules_raw.get('detect_near_machinery_or_vehicle', True),
                        'detect_in_restricted_area': danger_rules_raw.get('detect_in_restricted_area', True),
                        'detect_in_utility_pole_restricted_area': danger_rules_raw.get('detect_in_utility_pole_restricted_area', False),
                        'detect_machinery_close_to_pole': danger_rules_raw.get('detect_machinery_close_to_pole', False),
                    }

                danger_detector = DangerDetector(
                    detection_items=detection_items if detection_items else None,
                )
                streamer.danger_detector = danger_detector
                streamer.models = models
                streamer.thresholds = thresholds
                streamer.detection_interval = 0.0 if every_frame else max(0.5, float(detection_interval))
                streamer.save_screenshots = bool(save_screenshots)
                is_streaming = True
                await streamer.stream(decoded_path, websocket)
                is_streaming = False
            elif action == 'pause':
                if is_streaming:
                    streamer.pause()
                    await websocket.send_json({'type': 'paused'})
                else:
                    await websocket.send_json({'type': 'error', 'message': 'No active stream to pause'})
            elif action == 'resume':
                if is_streaming:
                    streamer.resume()
                    await websocket.send_json({'type': 'resumed'})
                else:
                    await websocket.send_json({'type': 'error', 'message': 'No active stream to resume'})
            elif action == 'stop':
                streamer.stop()
                is_streaming = False
                await websocket.send_json({'type': 'stopped'})
                break
    except WebSocketDisconnect:
        logger.info('WebSocket client disconnected')
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        streamer.stop()
