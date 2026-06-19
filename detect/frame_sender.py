from __future__ import annotations

import json
import logging
import os

import numpy as np
from dotenv import load_dotenv

from examples.streaming_web.backend.redis_service import DELIMITER
from src.net.net_client import NetClient
from src.utils import Utils

# Load environment variables from .env file
load_dotenv()


class BackendFrameSender:
    """
    A class to send frames and metadata to a backend server via HTTP or
    WebSocket (no authentication).

    Attributes:
        base_url (str): The base URL of the backend API.
        max_retries (int):
            Maximum number of retries for HTTP requests.
        timeout (int):
            Timeout in seconds for HTTP requests.
        reconnect_backoff (float):
            Backoff multiplier for reconnection attempts.
    """

    def __init__(
        self,
        api_url: str | None = None,
        max_retries: int = 3,
        timeout: int = 10,
        reconnect_backoff: float = 1.5,
        ws_heartbeat: int = 30,
        ws_send_timeout: float = 10.0,
        ws_recv_timeout: float = 15.0,
        ws_connect_attempts: int = 3,
    ) -> None:
        """
        Initialise the BackendFrameSender.

        Args:
            api_url: The base URL of the backend API.
            max_retries: Maximum number of retries for HTTP requests.
            timeout: Timeout in seconds for HTTP requests.
            reconnect_backoff: Backoff multiplier for reconnection attempts.
            ws_heartbeat: Heartbeat interval for WebSocket connections.
            ws_send_timeout: Send timeout for WebSocket connections.
            ws_recv_timeout: Receive timeout for WebSocket connections.
            ws_connect_attempts: Number of connection attempts for WebSocket.
        """
        if api_url is None:
            api_url = os.getenv('STREAMING_API_URL', 'http://127.0.0.1:8800')
        self.base_url: str = api_url.rstrip('/')

        self.max_retries: int = max_retries
        self.timeout: int = timeout
        self.reconnect_backoff: float = reconnect_backoff

        logging.getLogger('httpx').setLevel(logging.WARNING)

        self.ws_heartbeat: int = ws_heartbeat
        self.ws_send_timeout: float = ws_send_timeout
        self.ws_recv_timeout: float = ws_recv_timeout
        self.ws_connect_attempts: int = ws_connect_attempts

        self._net = NetClient(
            self.base_url,
            timeout=self.timeout,
            reconnect_backoff=self.reconnect_backoff,
            ws_heartbeat=self.ws_heartbeat,
            ws_send_timeout=self.ws_send_timeout,
            ws_recv_timeout=self.ws_recv_timeout,
            ws_connect_attempts=self.ws_connect_attempts,
        )

    async def send_optimized_frame(
        self: BackendFrameSender,
        frame: np.ndarray,
        site: str,
        stream_name: str,
        encoding_format: str = 'jpeg',
        jpeg_quality: int = 85,
        use_websocket: bool = True,
        warnings_json: str = '',
        cone_polygons_json: str = '',
        _unused_pole_polygons_json: str = '',
        detection_items_json: str = '',
    ) -> dict:
        """
        Send frame with optimized encoding to backend service.

        Args:
            frame (np.ndarray): Frame to send
            site (str): Site identifier
            stream_name (str): Stream identifier
            encoding_format (str): Image encoding format ('jpeg' or 'png')
            jpeg_quality (int): JPEG quality (1-100) when using JPEG format
            use_websocket (bool): Whether to use WebSocket instead of HTTP
            warnings_json (str): JSON string of warnings
            cone_polygons_json (str): JSON string of cone polygons
            _unused_pole_polygons_json (str): JSON string of pole polygons
            detection_items_json (str): JSON string of detection items

        Returns:
            dict: Response from backend
        """
        try:
            if encoding_format.lower() == 'jpeg':
                encoded_frame = Utils.encode_frame(frame, 'jpeg', jpeg_quality)
            else:
                encoded_frame = Utils.encode_frame(frame, 'png')

            if not encoded_frame:
                logging.error('Failed to encode frame')
                return {'success': False, 'error': 'Failed to encode frame'}

            height, width = frame.shape[:2]

            if use_websocket:
                ws_result = await self.send_frame_ws(
                    site=site,
                    stream_name=stream_name,
                    frame_bytes=encoded_frame,
                    warnings_json=warnings_json,
                    cone_polygons_json=cone_polygons_json,
                    _unused_pole_polygons_json=_unused_pole_polygons_json,
                    detection_items_json=detection_items_json,
                    width=width,
                    height=height,
                )
                if (
                    isinstance(ws_result, dict)
                    and ws_result.get('status') != 'error'
                ):
                    return ws_result
                logging.debug(
                    'WS failed after retries, fallback to HTTP: %s', ws_result,
                )
                return await self.send_frame(
                    site=site,
                    stream_name=stream_name,
                    frame_bytes=encoded_frame,
                    warnings_json=warnings_json,
                    cone_polygons_json=cone_polygons_json,
                    _unused_pole_polygons_json=_unused_pole_polygons_json,
                    detection_items_json=detection_items_json,
                    width=width,
                    height=height,
                )
            else:
                return await self.send_frame(
                    site=site,
                    stream_name=stream_name,
                    frame_bytes=encoded_frame,
                    warnings_json=warnings_json,
                    cone_polygons_json=cone_polygons_json,
                    _unused_pole_polygons_json=_unused_pole_polygons_json,
                    detection_items_json=detection_items_json,
                    width=width,
                    height=height,
                )

        except Exception as e:
            logging.error('Error sending optimized frame: %s', e)
            return {'success': False, 'error': str(e)}

    async def send_frame(
        self: BackendFrameSender,
        site: str,
        stream_name: str,
        frame_bytes: bytes,
        warnings_json: str = '',
        cone_polygons_json: str = '',
        _unused_pole_polygons_json: str = '',
        detection_items_json: str = '',
        width: int = 0,
        height: int = 0,
    ) -> dict:
        """
        Send a frame and metadata to the backend via HTTP POST.

        Args:
            site (str): The site/label name.
            stream_name (str): The stream key or camera identifier.
            frame_bytes (bytes): The raw image bytes to upload.
            warnings_json (str, optional):
                JSON string of warnings. Defaults to ''.
            cone_polygons_json (str, optional):
                JSON string of cone polygons. Defaults to ''.
            _unused_pole_polygons_json (str, optional):
                JSON string of pole polygons. Defaults to ''.
            detection_items_json (str, optional):
                JSON string of detection items. Defaults to ''.
            width (int, optional): Frame width. Defaults to 0.
            height (int, optional): Frame height. Defaults to 0.

        Returns:
            dict: The JSON response from the backend.

        Raises:
            RuntimeError: If all retry attempts are exhausted.
            httpx.HTTPStatusError: For non-401 HTTP errors.
            Exception: For other unexpected errors.
    """
        files: dict[str, tuple[str, bytes, str]] = {
            'file': (
                'frame.jpg',
                frame_bytes,
                'image/jpeg',
            ),
        }
        data: dict[str, str | int] = {
            'label': site,
            'key': stream_name,
            'warnings_json': warnings_json,
            'cone_polygons_json': cone_polygons_json,
            '_unused_pole_polygons_json': _unused_pole_polygons_json,
            'detection_items_json': detection_items_json,
            'width': width,
            'height': height,
        }

        return await self._net.http_post(
            '/frames',
            data=data,
            files=files,
            max_retries=self.max_retries,
        )

    async def send_frame_ws(
        self: BackendFrameSender,
        site: str,
        stream_name: str,
        frame_bytes: bytes,
        warnings_json: str = '',
        cone_polygons_json: str = '',
        _unused_pole_polygons_json: str = '',
        detection_items_json: str = '',
        width: int = 0,
        height: int = 0,
        ws_headers: dict[str, str] | None = None,
    ) -> dict:
        """
        Send a frame and metadata to the backend via WebSocket.
        Automatically reconnects if the connection is lost.

        Args:
            site (str): The site/label name.
            stream_name (str): The stream key or camera identifier.
            frame_bytes (bytes): The raw image bytes to upload.
            warnings_json (str, optional):
                JSON string of warnings. Defaults to ''.
            cone_polygons_json (str, optional):
            JSON string of cone polygons. Defaults to ''.
            _unused_pole_polygons_json (str, optional):
                JSON string of pole polygons. Defaults to ''.
            detection_items_json (str, optional):
                JSON string of detection items. Defaults to ''.
            width (int, optional): Frame width. Defaults to 0.
            height (int, optional): Frame height. Defaults to 0.

        Returns:
            dict: The JSON response from the backend.
        """
        header: dict[str, str | int] = {
            'label': site,
            'key': stream_name,
            'warnings_json': warnings_json,
            'cone_polygons_json': cone_polygons_json,
            '_unused_pole_polygons_json': _unused_pole_polygons_json,
            'detection_items_json': detection_items_json,
            'width': width,
            'height': height,
        }
        header_bytes: bytes = json.dumps(header).encode('utf-8')
        message: bytes = header_bytes + DELIMITER + frame_bytes

        max_attempts = 5
        for attempt in range(1, max_attempts + 1):
            data = await self._net.ws_send_and_receive(
                '/ws/frames',
                message,
                headers=ws_headers,
            )
            if data is not None:
                return data if isinstance(data, dict) else {'status': 'ok'}
            delay = min(self.reconnect_backoff * attempt, 30.0)
            import asyncio as _asyncio
            await _asyncio.sleep(delay)
        return {
            'status': 'error',
            'message': (
                f'WebSocket send failed after {max_attempts} attempts'
            ),
        }

    async def close(self: BackendFrameSender) -> None:
        """
        Close the WebSocket and aiohttp session to prevent resource leaks
        and thread issues.
        """
        try:
            await self._net.close()
        except Exception as e:
            logging.error('Error closing NetClient: %s', e)
