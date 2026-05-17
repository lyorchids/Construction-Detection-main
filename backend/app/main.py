from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import UPLOAD_IMAGE_DIR, UPLOAD_VIDEO_DIR, VIOLATION_DIR, HOST, PORT
from app.database import init_db
from app.api import upload, history, video_detect, report, image_detect, cases

import app.models.case  # noqa: F401 — register Case model with SQLAlchemy

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
    logging.info('Application started')


@app.get('/health')
def health_check():
    return {'status': 'ok'}


if __name__ == '__main__':
    import uvicorn
    uvicorn.run('app.main:app', host=HOST, port=PORT, reload=True)
