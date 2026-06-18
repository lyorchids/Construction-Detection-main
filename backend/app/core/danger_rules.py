from __future__ import annotations

import logging
from typing import Any

from shapely.geometry import LineString
from shapely.geometry import Point
from shapely.geometry import Polygon
from sklearn.cluster import HDBSCAN

from app.utils.bbox_utils import Utils

logger = logging.getLogger(__name__)

CLASS_NAMES: dict[int, str] = {
    0: 'Hardhat',
    1: 'Mask',
    2: 'NO-Hardhat',
    3: 'NO-Mask',
    4: 'NO-Safety Vest',
    5: 'Person',
    6: 'Safety Cone',
    7: 'Safety Vest',
    8: 'Machinery',
    9: 'Utility Pole',
    10: 'Vehicle',
}

VIOLATION_TYPE_LABELS: dict[str, str] = {
    'warning_no_hardhat': '未戴安全帽',
    'warning_no_mask': '未佩戴口罩',
    'warning_no_safety_vest': '未穿反光背心',

    'warning_people_in_controlled_area': '进入锥形桶管控区',
    'warning_people_in_utility_pole_controlled_area': '进入电线杆管控区',
    'warning_fire': '检测到火焰',
    'warning_smoke': '检测到烟雾',
}


class DangerDetector:
    """Detect potential safety hazards based on detection data."""

    def __init__(
        self,
        detection_items: dict[str, bool] | None = None,
    ) -> None:
        """Initialise the danger detector.

        Args:
            detection_items: Dict to enable/disable specific safety checks.
                Keys:
                - 'detect_no_safety_vest_or_helmet'
                 - 'detect_in_restricted_area'
                - 'detect_in_utility_pole_restricted_area'
                - 'detect_machinery_close_to_pole'
                If None, all checks are enabled.
        """
        self.clusterer = HDBSCAN(
            min_samples=3, min_cluster_size=2, copy=True,
        )

        required_keys = {
            'detect_no_hardhat',
            'detect_no_mask',
            'detect_no_safety_vest',
            'detect_in_restricted_area',
            'detect_in_utility_pole_restricted_area',
            'detect_machinery_close_to_pole',
        }

        self.detection_items = (
            detection_items
            if detection_items and required_keys.issubset(detection_items)
            else {}
        )

    def detect_danger(
        self,
        datas: list,
    ) -> tuple:
        """Detect potential safety violations.

        Args:
            datas: Detection data, each entry is
                [x1, y1, x2, y2, conf, cls_id].

        Returns:
            Tuple of (warnings dict, warnings_only dict,
            cone polygon coords, pole polygon coords).
        """
        datas = Utils.normalise_data(datas)
        warnings: dict = {}
        warnings_only: dict = {}

        cone_polygons_raw: list = []
        pole_polygons_raw: list = []

        # (A) Safety cone restricted area
        if (
            not self.detection_items
            or self.detection_items.get('detect_in_restricted_area', False)
        ):
            self._check_cone_restricted_area(
                datas, warnings, cone_polygons_raw,
            )

        # (B) Classify data
        persons = [d for d in datas if d[5] == 5]
        hardhat_violations = [d for d in datas if d[5] == 2]
        no_mask_violations = [d for d in datas if d[5] == 3]
        safety_vest_violations = [d for d in datas if d[5] == 4]
        machinery_vehicles = [d for d in datas if d[5] in [8, 10]]

        # Filter out potential drivers
        if machinery_vehicles:
            persons = [
                p for p in persons
                if not any(
                    Utils.is_driver(p[:4], mv[:4]) for mv in machinery_vehicles
                )
            ]

        # (C1) No-Hardhat
        if (
            not self.detection_items
            or self.detection_items.get('detect_no_hardhat', False)
        ):
            self._check_no_hardhat(hardhat_violations, warnings)

        # (C2) No-Mask
        if (
            not self.detection_items
            or self.detection_items.get('detect_no_mask', False)
        ):
            self._check_no_mask(no_mask_violations, warnings_only)

        # (C3) No-Safety Vest
        if (
            not self.detection_items
            or self.detection_items.get('detect_no_safety_vest', False)
        ):
            self._check_no_safety_vest(
                safety_vest_violations, warnings,
            )

        # (D) Machinery close to utility pole
        if (
            self.detection_items
            and self.detection_items.get(
                'detect_machinery_close_to_pole', False,
            )
        ):
            self._check_machinery_near_utility_pole(
                datas, warnings, circle_ratio=0.35,
            )

        # (F) Utility pole restricted area
        if (
            self.detection_items
            and self.detection_items.get(
                'detect_in_utility_pole_restricted_area', False,
            )
        ):
            self._check_pole_restricted_area(
                datas, warnings, pole_polygons_raw,
            )

        cone_polygons_coords = Utils.polygons_to_coords(cone_polygons_raw)
        pole_polygons_coords = Utils.polygons_to_coords(pole_polygons_raw)

        return warnings, warnings_only, cone_polygons_coords, pole_polygons_coords

    def _check_cone_restricted_area(
        self,
        datas: list,
        warnings: dict,
        polygons: list,
    ) -> None:
        """Check if personnel enter the controlled area formed by safety cones."""
        new_polygons = Utils.detect_polygon_from_cones(datas, self.clusterer)
        polygons.extend(new_polygons)

        people_objects = []
        for d in datas:
            if d[5] == 5:
                cx = (d[0] + d[2]) / 2.0
                cy = (d[1] + d[3]) / 2.0
                pt = Point(cx, cy)
                for poly in new_polygons:
                    if poly.contains(pt):
                        people_objects.append({'bbox': d[:4], 'confidence': d[4]})
                        break
        if people_objects:
            warnings['warning_people_in_controlled_area'] = {
                'count': len({(o['bbox'][0], o['bbox'][1]) for o in people_objects}),
                'objects': people_objects,
            }

    def _check_pole_restricted_area(
        self,
        datas: list,
        warnings: dict,
        pole_polygons: list,
    ) -> None:
        """Check if personnel enter the controlled area formed by utility poles."""
        pole_union_poly = Utils.build_utility_pole_union(
            datas, self.clusterer,
        )
        if not pole_union_poly.is_empty:
            pole_polygons.append(pole_union_poly)

            people_objects = []
            for d in datas:
                if d[5] == 5:
                    cx = (d[0] + d[2]) / 2.0
                    cy = (d[1] + d[3]) / 2.0
                    if pole_union_poly.contains(Point(cx, cy)):
                        people_objects.append({'bbox': d[:4], 'confidence': d[4]})
            if people_objects:
                warnings['warning_people_in_utility_pole_controlled_area'] = {
                    'count': len({(o['bbox'][0], o['bbox'][1]) for o in people_objects}),
                    'objects': people_objects,
                }

    def _check_no_hardhat(
        self,
        hardhat_violations: list,
        warnings: dict,
    ) -> None:
        objects = [
            {'bbox': v[:4], 'confidence': v[4]}
            for v in hardhat_violations
        ]
        if objects:
            warnings['warning_no_hardhat'] = {
                'count': len(objects), 'objects': objects,
            }

    def _check_no_mask(
        self,
        no_mask_violations: list,
        warnings_only: dict,
    ) -> None:
        objects = [
            {'bbox': v[:4], 'confidence': v[4]}
            for v in no_mask_violations
        ]
        if objects:
            warnings_only['warning_no_mask'] = {
                'count': len(objects), 'objects': objects,
            }

    def _check_no_safety_vest(
        self,
        safety_vest_violations: list,
        warnings: dict,
    ) -> None:
        objects = [
            {'bbox': v[:4], 'confidence': v[4]}
            for v in safety_vest_violations
        ]
        if objects:
            warnings['warning_no_safety_vest'] = {
                'count': len(objects), 'objects': objects,
            }

    def _check_machinery_near_utility_pole(
        self,
        datas: list,
        warnings: dict,
        circle_ratio: float = 0.35,
    ) -> None:
        """Check if machinery/vehicles are near the utility pole."""
        poles = [d for d in datas if d[5] == 9]
        machinery_vehicles = [d for d in datas if d[5] in [8, 10]]

        if not poles or not machinery_vehicles:
            return

        intersect_count = 0

        for pole in poles:
            px1, py1, px2, py2, *_ = pole
            pole_height = (py2 - py1)
            if pole_height <= 0:
                continue

            two_thirds_y = py1 + (2.0 / 3.0) * pole_height
            circle_radius = circle_ratio * pole_height
            circle_center = ((px1 + px2) / 2.0, py2)

            for mv in machinery_vehicles:
                mx1, my1, mx2, my2, *_ = mv
                if not (py1 <= my1 <= two_thirds_y):
                    continue

                bottom_line = LineString([(mx1, my2), (mx2, my2)])
                pole_circle = Point(circle_center).buffer(circle_radius)
                dist_to_circle = bottom_line.distance(pole_circle)

                if dist_to_circle <= 0:
                    intersect_count += 1

        if intersect_count > 0:
            warnings['detect_machinery_close_to_pole'] = {
                'count': intersect_count,
            }


def main() -> None:
    """Demo of DangerDetector."""
    detector = DangerDetector()

    data: list[list[float]] = [
        [50, 50, 150, 150, 0.95, 0],
        [200, 200, 300, 300, 0.85, 5],
        [400, 400, 500, 500, 0.75, 2],
        [0, 0, 10, 10, 0.88, 6],
        [0, 1000, 10, 1010, 0.87, 6],
        [1000, 0, 1010, 10, 0.89, 6],
        [100, 100, 120, 120, 0.9, 6],
        [150, 150, 170, 170, 0.85, 6],
        [200, 200, 220, 220, 0.89, 6],
        [100, 100, 120, 200, 0.9, 9],
        [200, 180, 230, 210, 0.85, 8],
    ]

    warnings, warnings_only, cone_polys, pole_polys = detector.detect_danger(data)
    print(f"Warnings: {warnings}")
    print(f"Warnings only: {warnings_only}")
    print(f"Cone polygons: {len(cone_polys)}")
    print(f"Pole polygons: {len(pole_polys)}")


if __name__ == '__main__':
    main()
