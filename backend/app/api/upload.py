from __future__ import annotations

import logging
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException, UploadFile

from app.config import UPLOAD_IMAGE_DIR, UPLOAD_VIDEO_DIR
from app.schemas.detection import UploadResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/upload', tags=['upload'])

ALLOWED_IMAGES = {'.jpg', '.jpeg', '.png', '.bmp', '.webp'}
ALLOWED_VIDEOS = {'.mp4', '.avi', '.mov', '.mkv', '.flv'}
MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB
MAX_VIDEO_SIZE = 200 * 1024 * 1024  # 200MB


def _validate_file(filename: str, file_size: int, is_image: bool) -> None:
    ext = Path(filename).suffix.lower()
    allowed = ALLOWED_IMAGES if is_image else ALLOWED_VIDEOS
    max_size = MAX_IMAGE_SIZE if is_image else MAX_VIDEO_SIZE

    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Allowed: {allowed}",
        )

    if file_size > max_size:
        limit_mb = max_size / (1024 * 1024)
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {limit_mb:.0f}MB",
        )


@router.post('/image', response_model=UploadResponse)
async def upload_image(file: UploadFile):
    """Upload an image file for hazard detection."""
    content = await file.read()
    file_size = len(content)

    _validate_file(file.filename, file_size, is_image=True)

    ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_IMAGE_DIR / unique_name

    file_path.write_bytes(content)
    logger.info(f"Image uploaded: {file.filename} -> {unique_name}")

    return UploadResponse(
        file_id=0,
        filename=file.filename,
        file_type='image',
        file_path=f'/uploads/images/{unique_name}',
    )


@router.post('/video', response_model=UploadResponse)
async def upload_video(file: UploadFile):
    """Upload a video file for hazard detection."""
    content = await file.read()
    file_size = len(content)

    _validate_file(file.filename, file_size, is_image=False)

    ext = Path(file.filename).suffix.lower()
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOAD_VIDEO_DIR / unique_name

    file_path.write_bytes(content)
    logger.info(f"Video uploaded: {file.filename} -> {unique_name}")

    return UploadResponse(
        file_id=0,
        filename=file.filename,
        file_type='video',
        file_path=f'/uploads/videos/{unique_name}',
    )
