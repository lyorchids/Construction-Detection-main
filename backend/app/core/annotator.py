from __future__ import annotations

import cv2
from typing import Any

# 违规等级 → BGR 颜色
LEVEL_COLORS: dict[str, tuple[int, int, int]] = {
    'high': (0, 0, 255),
    'medium': (0, 165, 255),
    'low': (0, 255, 255),
}

# 违规类型 → 等级
VIOLATION_LEVELS: dict[str, str] = {
    'warning_no_hardhat': 'high',
    'warning_people_in_controlled_area': 'high',
    'warning_people_in_utility_pole_controlled_area': 'high',
    'warning_close_to_machinery': 'medium',
    'warning_close_to_vehicle': 'medium',
    'warning_no_safety_vest': 'low',
    'warning_no_mask': 'low',
}

# 违规类型 → 中文标签（用于截图标注）
VIOLATION_LABELS_CN: dict[str, str] = {
    'warning_no_hardhat': '未戴安全帽',
    'warning_no_mask': '未戴口罩',
    'warning_no_safety_vest': '未穿反光背心',
    'warning_close_to_machinery': '靠近机械',
    'warning_close_to_vehicle': '靠近车辆',
    'warning_people_in_controlled_area': '进入锥形桶管控区',
    'warning_people_in_utility_pole_controlled_area': '进入电线杆管控区',
    'warning_fire': '火焰',
    'warning_smoke': '烟雾',
}


def draw_annotations(
    frame: Any,
    detections: list[Any],
    warnings: dict[str, Any],
) -> Any:
    """在图像上绘制检测框和违规标注。

    Args:
        frame: BGR 图像 (numpy array)
        detections: 检测结果列表，每个元素有 .bbox, .confidence, .class_id, .class_name
        warnings: 违规字典，每个包含 'objects' 列表，内有 bbox/confidence

    Returns:
        标注后的图像（新图像，不修改原图）
    """
    img = frame.copy()

    # 1. 画所有检测框（浅色细线）
    for d in detections:
        x1, y1, x2, y2 = map(int, d.bbox[:4])
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 1)
        label = f'{d.class_name} {d.confidence:.2f}'
        cv2.putText(
            img, label, (x1, y1 - 5),
            cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 255, 0), 1,
        )

    # 2. 高亮违规对象（按等级着色，粗框）
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
            conf = obj.get('confidence', 0)
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 3)
            cn_label = VIOLATION_LABELS_CN.get(vtype, vtype)
            label = f'{cn_label} {conf:.2f}'
            cv2.putText(
                img, label, (x1, y1 - 8),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2,
            )

    return img
