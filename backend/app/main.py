from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from app.config import UPLOAD_IMAGE_DIR, UPLOAD_VIDEO_DIR, VIOLATION_DIR, HOST, PORT
from app.database import init_db
from app.api import upload, history, video_detect, report, image_detect, cases, models, detection_profiles

import app.models.case  # noqa: F401 — register Case model with SQLAlchemy
import app.models.detection_profile  # noqa: F401 — register DetectionProfile

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)

app = FastAPI(
    title='Construction Hazard Detection API',
    description='AI-based construction site safety hazard detection system',
    version='1.0.0',
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

app.mount('/uploads/images', StaticFiles(directory=str(UPLOAD_IMAGE_DIR)), name='upload_images')
app.mount('/uploads/videos', StaticFiles(directory=str(UPLOAD_VIDEO_DIR)), name='upload_videos')
app.mount(
    '/violations',
    StaticFiles(directory=str(VIOLATION_DIR)),
    name='violations',
)

app.include_router(upload.router)
app.include_router(image_detect.router)
app.include_router(history.router)
app.include_router(video_detect.router)
app.include_router(report.router)
app.include_router(cases.router)
app.include_router(models.router)
app.include_router(detection_profiles.router)


def seed_profiles(db):
    from app.models.detection_profile import DetectionProfile
    existing = db.scalars(
        select(DetectionProfile).limit(1)
    ).first()
    if existing:
        return 0

    from app.schemas.detection_profile import ProfileCreate
    from app.services.detection_profile_service import create_profile

    seeds = [
        ProfileCreate(
            name='PPE标准检测',
            type='image',
            description='仅PPE安全检测，启用4项常用危险规则',
            config={
                'models': {
                    'ppe': {
                        'enabled': True,
                        'threshold': 0.25,
                        'danger_rules': {
                            'detect_no_hardhat': True,
                            'detect_no_mask': True,
                            'detect_no_safety_vest': True,
                            'detect_near_machinery_or_vehicle': True,
                            'detect_in_restricted_area': True,
                            'detect_in_utility_pole_restricted_area': False,
                            'detect_machinery_close_to_pole': False,
                        },
                    },
                    'fire': {
                        'enabled': False,
                        'threshold': 0.25,
                    },
                },
            },
        ),
        ProfileCreate(
            name='全面检测',
            type='image',
            description='PPE+火情烟雾全面检测',
            config={
                'models': {
                    'ppe': {
                        'enabled': True,
                        'threshold': 0.25,
                        'danger_rules': {
                            'detect_no_hardhat': True,
                            'detect_no_mask': True,
                            'detect_no_safety_vest': True,
                            'detect_near_machinery_or_vehicle': True,
                            'detect_in_restricted_area': True,
                            'detect_in_utility_pole_restricted_area': False,
                            'detect_machinery_close_to_pole': False,
                        },
                    },
                    'fire': {
                        'enabled': True,
                        'threshold': 0.25,
                    },
                },
            },
        ),
        ProfileCreate(
            name='标准视频检测',
            type='video',
            description='PPE+火情，每10帧检测一次',
            config={
                'frame_interval': 10,
                'save_screenshots': True,
                'models': {
                    'ppe': {
                        'enabled': True,
                        'threshold': 0.25,
                        'danger_rules': {
                            'detect_no_safety_vest_or_helmet': True,
                            'detect_near_machinery_or_vehicle': True,
                            'detect_in_restricted_area': True,
                            'detect_in_utility_pole_restricted_area': False,
                            'detect_machinery_close_to_pole': False,
                        },
                    },
                    'fire': {
                        'enabled': True,
                        'threshold': 0.25,
                    },
                },
            },
        ),
        ProfileCreate(
            name='快速视频检测',
            type='video',
            description='仅PPE，每30帧检测一次，适合长视频',
            config={
                'frame_interval': 30,
                'save_screenshots': True,
                'models': {
                    'ppe': {
                        'enabled': True,
                        'threshold': 0.25,
                        'danger_rules': {
                            'detect_no_hardhat': True,
                            'detect_no_mask': True,
                            'detect_no_safety_vest': True,
                            'detect_near_machinery_or_vehicle': True,
                            'detect_in_restricted_area': True,
                            'detect_in_utility_pole_restricted_area': False,
                            'detect_machinery_close_to_pole': False,
                        },
                    },
                    'fire': {
                        'enabled': False,
                        'threshold': 0.25,
                    },
                },
            },
        ),
    ]

    for s in seeds:
        create_profile(db, s)
    return len(seeds)


@app.on_event('startup')
def on_startup():
    init_db()
    from app.database import SessionLocal
    db = SessionLocal()
    try:
        from app.services.seed_cases import seed_cases
        seeded = seed_cases(db)
        if seeded:
            logging.info(f'Seeded {seeded} cases into database')
    finally:
        db.close()

    db2 = SessionLocal()
    try:
        seeded_profiles = seed_profiles(db2)
        if seeded_profiles:
            logging.info(f'Seeded {seeded_profiles} detection profiles into database')
    finally:
        db2.close()

    logging.info('Application started')


@app.get('/health')
def health_check():
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host=HOST, port=PORT, reload=True)
