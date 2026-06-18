from __future__ import annotations

import base64
import logging
import math
from datetime import datetime

import cv2
import networkx as nx
import numpy as np
from shapely.geometry import LineString
from shapely.geometry import MultiPoint
from shapely.geometry import Point
from shapely.geometry import Polygon
from shapely.ops import unary_union
from sklearn.cluster import HDBSCAN


class Utils:
    """Utility functions for construction hazard detection."""

    CIRCLE_BUFFER_SEGMENTS: int = 64
    TANGENT_BUFFER_WIDTH: float = 0.05
    TANGENT_BUFFER_SEGMENTS: int = 32
    UTILITY_POLE_RADIUS_FACTOR: float = 0.35

    @staticmethod
    def is_expired(expire_date_str: str | None) -> bool:
        if expire_date_str:
            try:
                expire_date = datetime.fromisoformat(expire_date_str)
                return datetime.now() > expire_date
            except ValueError:
                return False
        return False

    @staticmethod
    def encode(value: str) -> str:
        return base64.urlsafe_b64encode(
            value.encode('utf-8'),
        ).decode('utf-8')

    @staticmethod
    def encode_frame(
        frame: np.ndarray, format: str = 'jpeg', quality: int = 85,
    ) -> bytes:
        try:
            if format.lower() == 'jpeg':
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                success, buffer = cv2.imencode('.jpg', frame, encode_params)
            else:
                encode_params = [
                    cv2.IMWRITE_PNG_COMPRESSION, min(quality // 10, 9),
                ]
                success, buffer = cv2.imencode('.png', frame, encode_params)

            if not success:
                logging.error(
                    f"Failed to encode frame for {format}",
                )
                return b''
            return buffer.tobytes()
        except Exception as e:
            logging.error(f"Error encoding frame as {format}: {e}")
            return b''

    @staticmethod
    def normalise_bbox(bbox: list[float]) -> list[float]:
        left_x = min(bbox[0], bbox[2])
        right_x = max(bbox[0], bbox[2])
        top_y = min(bbox[1], bbox[3])
        bottom_y = max(bbox[1], bbox[3])
        if len(bbox) > 4:
            return [left_x, top_y, right_x, bottom_y, bbox[4], bbox[5]]
        return [left_x, top_y, right_x, bottom_y]

    @staticmethod
    def normalise_data(datas: list[list[float]]) -> list[list[float]]:
        return [Utils.normalise_bbox(data[:4] + data[4:]) for data in datas]

    @staticmethod
    def overlap_percentage(bbox1: list[float], bbox2: list[float]) -> float:
        x1 = max(bbox1[0], bbox2[0])
        y1 = max(bbox1[1], bbox2[1])
        x2 = min(bbox1[2], bbox2[2])
        y2 = min(bbox1[3], bbox2[3])

        overlap_area = max(0, x2 - x1) * max(0, y2 - y1)
        area1 = (bbox1[2] - bbox1[0]) * (bbox1[3] - bbox1[1])
        area2 = (bbox2[2] - bbox2[0]) * (bbox2[3] - bbox2[1])

        return overlap_area / float(area1 + area2 - overlap_area)

    @staticmethod
    def is_driver(person_bbox: list[float], vehicle_bbox: list[float]) -> bool:
        person_bottom_y = person_bbox[3]
        person_top_y = person_bbox[1]
        person_left_x = person_bbox[0]
        person_right_x = person_bbox[2]
        person_width = person_bbox[2] - person_bbox[0]
        person_height = person_bbox[3] - person_bbox[1]

        vehicle_top_y = vehicle_bbox[1]
        vehicle_bottom_y = vehicle_bbox[3]
        vehicle_left_x = vehicle_bbox[0]
        vehicle_right_x = vehicle_bbox[2]
        vehicle_height = vehicle_bbox[3] - vehicle_bbox[1]

        if not (
            person_bottom_y < vehicle_bottom_y
            and vehicle_bottom_y - person_bottom_y >= person_height / 2
        ):
            return False

        if not (
            person_left_x >= vehicle_left_x - person_width / 2
            and person_right_x <= vehicle_right_x + person_width / 2
        ):
            return False

        if not (person_top_y > vehicle_top_y):
            return False

        if not (person_height <= vehicle_height / 2):
            return False

        return True

    @staticmethod
    def detect_polygon_from_cones(
        datas: list[list[float]],
        clusterer: HDBSCAN,
    ) -> list[Polygon]:
        if not datas:
            return []

        cone_positions = np.array([
            (
                (float(data[0]) + float(data[2])) / 2,
                (float(data[1]) + float(data[3])) / 2,
            )
            for data in datas if data[5] == 6
        ])

        if len(cone_positions) < 3:
            return []

        labels = clusterer.fit_predict(cone_positions)

        clusters: dict[int, list[np.ndarray]] = {}
        for point, label in zip(cone_positions, labels):
            if label == -1:
                continue
            if label not in clusters:
                clusters[label] = []
            clusters[label].append(point)

        polygons = []
        for cluster_points in clusters.values():
            if len(cluster_points) >= 3:
                polygon = MultiPoint(cluster_points).convex_hull
                polygons.append(polygon)

        return polygons

    @staticmethod
    def calculate_people_in_controlled_area(
        polygons: list[Polygon],
        datas: list[list[float]],
    ) -> int:
        if not datas or not polygons:
            return 0

        unique_people = set()

        for data in datas:
            if data[5] == 5:
                x_center = (data[0] + data[2]) / 2
                y_center = (data[1] + data[3]) / 2
                point = Point(x_center, y_center)
                for polygon in polygons:
                    if polygon.contains(point):
                        unique_people.add((x_center, y_center))
                        break

        return len(unique_people)

    @staticmethod
    def polygons_to_coords(
        polygons: list[Polygon],
    ) -> list[list[list[float]]]:
        coords_list: list[list[list[float]]] = []
        for poly in polygons:
            if poly.is_empty:
                continue
            if poly.geom_type == 'Polygon':
                coords_list.append([
                    list(pt) for pt in poly.exterior.coords
                ])
            elif poly.geom_type == 'MultiPolygon':
                for subpoly in poly.geoms:
                    if (
                        not subpoly.is_empty and
                        subpoly.geom_type == 'Polygon'
                    ):
                        coords_list.append([
                            list(pt)
                            for pt in subpoly.exterior.coords
                        ])
        return coords_list

    @staticmethod
    def _extract_utility_poles(
        datas: list[list[float]],
    ) -> list[tuple[float, float, float]]:
        poles: list[tuple[float, float, float]] = []
        for d in datas:
            if d[5] == 9:
                left, top, right, bottom, *_ = d
                cx: float = (left + right) / 2.0
                cy: float = bottom
                height: float = bottom - top
                radius: float = Utils.UTILITY_POLE_RADIUS_FACTOR * height
                if radius > 0:
                    poles.append((cx, cy, radius))
        return poles

    @staticmethod
    def _union_circles(
        poles: list[tuple[float, float, float]],
    ) -> Polygon:
        circle_polys: list[Polygon] = [
            Point(cx, cy).buffer(r, quad_segs=Utils.CIRCLE_BUFFER_SEGMENTS)
            for (cx, cy, r) in poles
        ]
        return unary_union(circle_polys)

    @staticmethod
    def _cluster_utility_poles(
        poles: list[tuple[float, float, float]],
        clusterer: HDBSCAN,
    ) -> dict[str | int, list[tuple[float, float, float]]]:
        coords: np.ndarray = np.array([(p[0], p[1]) for p in poles])
        labels: np.ndarray = clusterer.fit_predict(coords)

        clusters: dict[str | int, list[tuple[float, float, float]]] = {}
        for idx, (circle, label) in enumerate(zip(poles, labels)):
            if label == -1:
                key: str = f"noise_{idx}"
                clusters.setdefault(key, []).append(circle)
            else:
                clusters.setdefault(int(label), []).append(circle)
        return clusters

    @staticmethod
    def _build_cluster_union(
        circles_in_cluster: list[tuple[float, float, float]],
    ) -> Polygon:
        if len(circles_in_cluster) == 1:
            cx, cy, r = circles_in_cluster[0]
            return Point(cx, cy).buffer(
                r, quad_segs=Utils.CIRCLE_BUFFER_SEGMENTS,
            )

        circle_polys_: list[Polygon] = [
            Point(cx, cy).buffer(r, quad_segs=Utils.CIRCLE_BUFFER_SEGMENTS)
            for (cx, cy, r) in circles_in_cluster
        ]
        tangent_buffers = Utils._build_mst_tangent_buffers(circles_in_cluster)
        return unary_union(circle_polys_ + tangent_buffers)

    @staticmethod
    def _build_mst_tangent_buffers(
        circles_in_cluster: list[tuple[float, float, float]],
    ) -> list[Polygon]:
        mst_edges: list[tuple[int, int]] = Utils.build_mst_pairs(
            circles_in_cluster,
        )
        lines: list[LineString] = []
        for (u, v) in mst_edges:
            cx1, cy1, r1 = circles_in_cluster[u]
            cx2, cy2, r2 = circles_in_cluster[v]
            lines.extend(Utils.get_outer_tangents(cx1, cy1, r1, cx2, cy2, r2))
        return [
            ls.buffer(
                Utils.TANGENT_BUFFER_WIDTH,
                quad_segs=Utils.TANGENT_BUFFER_SEGMENTS,
            ) for ls in lines
        ]

    @staticmethod
    def build_mst_pairs(
        poles: list[tuple[float, float, float]],
    ) -> list[tuple[int, int]]:
        G: nx.Graph = nx.Graph()
        for i, (cx, cy, r) in enumerate(poles):
            G.add_node(i, pos=(cx, cy), radius=r)

        n: int = len(poles)
        for i in range(n):
            cx1, cy1, r1 = poles[i]
            for j in range(i + 1, n):
                cx2, cy2, r2 = poles[j]
                dist_centers: float = math.dist((cx1, cy1), (cx2, cy2))
                weight: float = max(0, dist_centers - (r1 + r2))
                G.add_edge(i, j, weight=weight)

        mst: nx.Graph = nx.minimum_spanning_tree(G, weight='weight')
        return list(mst.edges())

    @staticmethod
    def get_outer_tangents(
        cx1: float,
        cy1: float,
        r1: float,
        cx2: float,
        cy2: float,
        r2: float,
        eps: float = 1e-9,
    ) -> list[LineString]:
        dx: float = cx2 - cx1
        dy: float = cy2 - cy1
        d2: float = dx * dx + dy * dy
        d: float = math.sqrt(d2)
        if d < abs(r1 - r2):
            return []
        if d < eps:
            return []

        if r2 > r1:
            cx1, cx2 = cx2, cx1
            cy1, cy2 = cy2, cy1
            r1, r2 = r2, r1
            dx, dy = -dx, -dy

        d2 = (cx2 - cx1) ** 2 + (cy2 - cy1) ** 2
        d = math.sqrt(d2)
        rdiff: float = r1 - r2
        if d < rdiff:
            return []

        alpha: float = math.acos(rdiff / d)
        theta: float = math.atan2((cy2 - cy1), (cx2 - cx1))

        lines: list[LineString] = []
        for sign in [1, -1]:
            phi: float = theta + sign * alpha
            x1t: float = cx1 + r1 * math.cos(phi)
            y1t: float = cy1 + r1 * math.sin(phi)
            x2t: float = cx2 + r2 * math.cos(phi)
            y2t: float = cy2 + r2 * math.sin(phi)
            ls: LineString = LineString([
                (x1t, y1t),
                (x2t, y2t),
            ])
            lines.append(ls)

        return lines

    @staticmethod
    def build_utility_pole_union(
        datas: list[list[float]],
        clusterer: HDBSCAN,
    ) -> Polygon:
        utility_poles = Utils._extract_utility_poles(datas)
        if not utility_poles:
            return Polygon()

        if len(utility_poles) == 1:
            cx, cy, r = utility_poles[0]
            return Point(cx, cy).buffer(r, quad_segs=64)

        if len(utility_poles) < clusterer.min_samples:
            return Utils._union_circles(utility_poles)

        clusters = Utils._cluster_utility_poles(utility_poles, clusterer)
        cluster_polys: list[Polygon] = [
            Utils._build_cluster_union(circles_in_cluster)
            for circles_in_cluster in clusters.values()
        ]
        return unary_union(cluster_polys)

    @staticmethod
    def count_people_in_polygon(
        poly: Polygon,
        datas: list[list[float]],
    ) -> int:
        persons: list[list[float]] = [d for d in datas if d[5] == 5]
        found_people: set[tuple[float, float]] = set()
        for p in persons:
            left, top, right, bottom, *_ = p
            px: float = (left + right) / 2.0
            py: float = (top + bottom) / 2.0
            if poly.contains(Point(px, py)):
                found_people.add((px, py))
        return len(found_people)
