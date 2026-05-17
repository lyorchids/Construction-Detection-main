from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime

import httpx


class ViolationSender:
    """
    Responsible for sending violation images and metadata to the backend API.
    Handles retry logic for robust delivery (no authentication).
    """

    def __init__(
        self,
        api_url: str | None = None,
        max_retries: int = 3,
        timeout: int = 10,
    ) -> None:
        """
        Initialise the ViolationSender.

        Args:
            api_url (str | None): The base URL for the violation API endpoint.
                If None, uses environment variable.
            max_retries (int): Maximum number of retry attempts for requests.
            timeout (int): Timeout for HTTP requests in seconds.
        """
        if api_url is None:
            api_url = os.getenv(
                'VIOLATION_RECORD_API_URL',
                'http://127.0.0.1:8002',
            )

        self.base_url: str = api_url.rstrip('/')
        self.max_retries: int = max_retries
        self.timeout: int = timeout

        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

        logging.getLogger('httpx').setLevel(logging.WARNING)

    async def _get_client(self) -> httpx.AsyncClient:
        """
        Get an HTTP client with connection pooling.

        Returns:
            httpx.AsyncClient: Async HTTP client
        """
        async with self._client_lock:
            if self._client is None or self._client.is_closed:
                self._client = httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout),
                    limits=httpx.Limits(
                        max_keepalive_connections=5,
                        max_connections=10,
                        keepalive_expiry=30,
                    ),
                    http2=True,
                )
            return self._client

    async def close(self) -> None:
        """
        Close the HTTP client connection pool if it exists.
        """
        async with self._client_lock:
            if self._client and not self._client.is_closed:
                await self._client.aclose()
                self._client = None

    async def send_violation(
        self,
        site: str,
        stream_name: str,
        image_bytes: bytes,
        detection_time: datetime | None = None,
        warnings_json: str | None = None,
        detections_json: str | None = None,
        cone_polygon_json: str | None = None,
        pole_polygon_json: str | None = None,
        access_token: str | None = None,
    ) -> str | None:
        """
        Send a violation image and associated metadata to the backend API.

        Args:
            site (str): The site label.
            stream_name (str): The stream identifier.
            image_bytes (bytes): The image data in bytes.
            detection_time (Optional[datetime]): The time of detection.
            warnings_json (Optional[str]): JSON string of warnings.
            detections_json (Optional[str]): JSON string of detection items.
            cone_polygon_json (Optional[str]): JSON string of cone polygons.
            pole_polygon_json (Optional[str]): JSON string of pole polygons.
            access_token (Optional[str]): Optional Bearer token for auth.

        Returns:
            Optional[str]:
                The violation ID (string) if successful,
                or None if all attempts fail.

        Raises:
            RuntimeError:
                If all retry attempts are exhausted or a critical error occurs.
        """
        headers, files, data, upload_url = self._build_upload_payload(
            access_token=access_token,
            image_bytes=image_bytes,
            site=site,
            stream_name=stream_name,
            detection_time=detection_time,
            warnings_json=warnings_json,
            detections_json=detections_json,
            cone_polygon_json=cone_polygon_json,
            pole_polygon_json=pole_polygon_json,
        )

        client = await self._get_client()

        backoff_delay = 1

        for attempt in range(self.max_retries):
            try:
                resp = await client.post(
                    upload_url,
                    data=data,
                    files=files,
                    headers=headers,
                )
                resp.raise_for_status()
                return resp.json().get('violation_id')

            except httpx.ConnectTimeout:
                logging.warning(
                    f"[send_violation] Attempt {attempt+1}: "
                    'Connection timeout, retry...',
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2
                else:
                    raise RuntimeError(
                        '[send_violation] All retry attempts exhausted due to timeout',
                    )

            except httpx.HTTPStatusError as exc:
                logging.error(
                    f"[send_violation] HTTP error {exc.response.status_code}: {exc}",
                )
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2
                else:
                    raise

            except Exception as e:
                logging.error(f"[send_violation] Unexpected error: {e}")
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(backoff_delay)
                    backoff_delay *= 2
                else:
                    raise

        return None

    def _build_upload_payload(
        self,
        access_token: str | None,
        image_bytes: bytes,
        site: str,
        stream_name: str,
        detection_time: datetime | None,
        warnings_json: str | None,
        detections_json: str | None,
        cone_polygon_json: str | None,
        pole_polygon_json: str | None,
    ) -> tuple[
        dict[str, str],
        dict[str, tuple[str, bytes, str]],
        dict[str, str],
        str,
    ]:
        """
        Build headers, files, form data, and URL for upload request.

        Args:
            access_token (str | None): Optional access token for authentication.
            image_bytes (bytes): The image bytes to upload.
            site (str): The site identifier.
            stream_name (str): The stream name.
            detection_time (datetime | None): The time of detection.
            warnings_json (str | None): JSON string of warnings.
            detections_json (str | None): JSON string of detection items.
            cone_polygon_json (str | None): JSON string of cone polygons.
            pole_polygon_json (str | None): JSON string of pole polygons.

        Returns:
            tuple[
                dict[str, str],
                dict[str, tuple[str, bytes, str]],
                dict[str, str],
                str,
            ]: The headers, files, form data, and upload URL.
        """
        headers: dict[str, str] = {}
        if access_token:
            headers['Authorization'] = f"Bearer {access_token}"
        files: dict[str, tuple[str, bytes, str]] = {
            'image': ('violation.jpg', image_bytes, 'image/jpeg'),
        }
        data: dict[str, str] = {
            'site': site,
            'stream_name': stream_name,
        }
        if detection_time:
            data['detection_time'] = detection_time.isoformat()
        if warnings_json:
            data['warnings_json'] = warnings_json
        if detections_json:
            data['detections_json'] = detections_json
        if cone_polygon_json:
            data['cone_polygon_json'] = cone_polygon_json
        if pole_polygon_json:
            data['pole_polygon_json'] = pole_polygon_json

        upload_url: str = self.base_url + '/upload'
        return headers, files, data, upload_url
