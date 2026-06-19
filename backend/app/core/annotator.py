from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from PIL import ImageDraw
from PIL import ImageFont
from typing import Any

logger = logging.getLogger(__name__)

# ── 颜色 ──
LEVEL_COLORS: dict[str, tuple[int, int, int]] = {
    'high': (0, 0, 255),
    'medium': (0, 165, 255),
    'low': (0, 255, 255),
}

VIOLATION_LEVELS: dict[str, str] = {
    'warning_no_hardhat': 'high',
    'warning_people_in_controlled_area': 'high',
    'detect_machinery_close_to_pole': 'high',
    'warning_no_safety_vest': 'low',
    'warning_no_mask': 'low',
}

VIOLATION_LABELS_CN: dict[str, str] = {
    'warning_no_hardhat': '未戴安全帽',
    'warning_no_mask': '未戴口罩',
    'warning_no_safety_vest': '未穿反光背心',
    'warning_people_in_controlled_area': '进入锥形桶管控区',
    'detect_machinery_close_to_pole': '机械靠近电线杆',
    'warning_fire': '火焰',
    'warning_smoke': '烟雾',
}

# ── 中文字体加载 ──
_FONT_PATHS = [
    'C:/Windows/Fonts/simhei.ttf',
    'C:/Windows/Fonts/msyh.ttc',
    'C:/Windows/Fonts/simsun.ttc',
    '/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
    '/System/Library/Fonts/PingFang.ttc',
]

_FONT: ImageFont.FreeTypeFont | None = None
for _fp in _FONT_PATHS:
    p = Path(_fp)
    if p.exists():
        try:
            _FONT = ImageFont.truetype(str(p), 18)
            _FONT_SMALL = ImageFont.truetype(str(p), 14)
            logger.info(f"Loaded font: {p}")
            break
        except Exception:
            continue

if _FONT is None:
    logger.warning('No CJK font found, Chinese text may show as ???')
    _FONT = ImageFont.load_default()
    _FONT_SMALL = ImageFont.load_default()


def _cv2_to_pil(img_bgr: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR image to PIL RGB."""
    return Image.fromarray(cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB))


def _pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL RGB back to OpenCV BGR."""
    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


def draw_annotations(
    frame: Any,
    detections: list[Any],
    warnings: dict[str, Any],
    polygons: list[list[list[float]]] | None = None,
) -> Any:
    """Draw detection boxes and violation labels on a copy of the frame.

    Chinese violation labels are rendered via PIL to support CJK glyphs.
    """
    img = frame.copy()

    # ── 1. Draw all detection boxes (cv2) ──
    for d in detections:
        x1, y1, x2, y2 = map(int, d.bbox[:4])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)

    # ── 2. Highlight violation boxes (cv2) ──
    for vtype, vdata in warnings.items():
        if not isinstance(vdata, dict):
            continue
        objects = vdata.get('objects', [])
        if not isinstance(objects, list):
            continue
        level = VIOLATION_LEVELS.get(vtype, 'medium')
        color = LEVEL_COLORS[level]
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            bbox = obj.get('bbox', [])
            if len(bbox) < 4:
                continue
            x1, y1, x2, y2 = map(int, bbox[:4])
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)

    # ── 3. Draw zone polygons (semi-transparent on PIL) ──
    pil_img = _cv2_to_pil(img)
    draw = ImageDraw.Draw(pil_img, 'RGBA')

    if polygons:
        for poly in polygons:
            if len(poly) < 3:
                continue
            flat = [(pt[0], pt[1]) for pt in poly]
            draw.polygon(flat, fill=(255, 235, 59, 64), outline=(255, 235, 59, 180))

    for d in detections:
        x1, y1, x2, y2 = map(int, d.bbox[:4])
        label = f'{d.class_name} {d.confidence:.2f}'
        draw.text(
            (x1 + 2, y1 - _FONT_SMALL.size - 2),
            label, font=_FONT_SMALL, fill=(0, 255, 0),
        )

    for vtype, vdata in warnings.items():
        if not isinstance(vdata, dict):
            continue
        objects = vdata.get('objects', [])
        if not isinstance(objects, list):
            continue
        level = VIOLATION_LEVELS.get(vtype, 'medium')
        color = LEVEL_COLORS[level]
        color_rgb = (color[2], color[1], color[0])
        cn_label = VIOLATION_LABELS_CN.get(vtype, vtype)
        for obj in objects:
            if not isinstance(obj, dict):
                continue
            bbox = obj.get('bbox', [])
            if len(bbox) < 4:
                continue
            x1, y1, x2, y2 = map(int, bbox[:4])
            conf = obj.get('confidence', 0)
            label = f'{cn_label} {conf:.2f}'
            draw.text(
                (x1 + 2, y1 - _FONT.size - 2),
                label, font=_FONT, fill=color_rgb,
            )

    return _pil_to_cv2(pil_img)
