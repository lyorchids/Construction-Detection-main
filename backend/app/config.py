from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

MODEL_PATH: Path = BASE_DIR / os.getenv('MODEL_PATH', 'models/yolo26l.pt')
DEVICE: str = os.getenv('DEVICE', 'cuda:0')

AI_PROVIDER: str = os.getenv('AI_PROVIDER', 'deepseek')
AI_API_KEY: str = os.getenv('AI_API_KEY', '')
AI_BASE_URL: str = os.getenv('AI_BASE_URL', 'https://api.deepseek.com/v1')
AI_MODEL: str = os.getenv('AI_MODEL', 'deepseek-chat')
DATABASE_URL: str = os.getenv(
    'DATABASE_URL',
    'sqlite:///./data/detections.db',
)
UPLOAD_IMAGE_DIR: Path = BASE_DIR / 'uploads' / 'images'
UPLOAD_VIDEO_DIR: Path = BASE_DIR / 'uploads' / 'videos'
VIOLATION_DIR: Path = BASE_DIR / os.getenv('VIOLATION_DIR', 'violations')
REPORT_DIR: Path = BASE_DIR / os.getenv('REPORT_DIR', 'reports')
HOST: str = os.getenv('HOST', '0.0.0.0')
PORT: int = int(os.getenv('PORT', '8000'))

for directory in [UPLOAD_IMAGE_DIR, UPLOAD_VIDEO_DIR, VIOLATION_DIR, REPORT_DIR]:
    directory.mkdir(parents=True, exist_ok=True)
