from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import MODEL_PATH, DEVICE, BASE_DIR
from app.core.danger_rules import DangerDetector
from app.core.detector import YOLODetector
from app.core.streamer import VideoStreamer

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/ws/video', tags=['video-detect'])

_detector: YOLODetector | None = None
_danger_detector: DangerDetector | None = None


def get_detectors() -> tuple[YOLODetector, DangerDetector]:
    global _detector, _danger_detector

    if _detector is None:
        _detector = YOLODetector(str(MODEL_PATH), device=DEVICE)
        _danger_detector = DangerDetector()

    assert _detector is not None and _danger_detector is not None
    return _detector, _danger_detector


@router.websocket('/detect/{file_path:path}')
async def websocket_detect(websocket: WebSocket, file_path: str):
    """WebSocket endpoint for real-time video detection.

    Args:
        websocket: WebSocket connection.
        file_path: URL-encoded path to the video file.
    """
    await websocket.accept()

    import urllib.parse
    decoded_path = urllib.parse.unquote(file_path)

    if decoded_path.startswith('/uploads/'):
        decoded_path = str(BASE_DIR / decoded_path.lstrip('/'))

    logger.info(f"WebSocket connection opened for: {decoded_path}")

    detector, danger_detector = get_detectors()
    streamer = VideoStreamer(detector, danger_detector)
    is_streaming = False

    try:
        while True:
            data = await websocket.receive_json()
            action = data.get('action')

            if action == 'start':
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