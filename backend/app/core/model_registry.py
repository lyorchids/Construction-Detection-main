from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from app.core.detector import YOLODetector

logger = logging.getLogger(__name__)

CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / 'config' / 'models.json'


class ModelRegistry:
    """Registry for managing multiple YOLO models with lazy loading."""

    def __init__(self, config_path: str | Path | None = None) -> None:
        self._config: dict[str, dict[str, Any]] = {}
        self._instances: dict[str, YOLODetector] = {}
        self._load_config(config_path or CONFIG_PATH)

    def _load_config(self, config_path: str | Path) -> None:
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Model config not found: {path}")
            return
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        self._config = data.get('models', {})
        logger.info(f"Loaded {len(self._config)} model(s) from config")

    def get_available_models(self) -> dict[str, Any]:
        """Return model metadata without loading the actual model."""
        result: dict[str, Any] = {}
        for key, cfg in self._config.items():
            classes_raw = cfg.get('classes', {})
            classes_out: dict[str, str] = {}
            for k, v in classes_raw.items():
                classes_out[str(k)] = str(v)
            result[key] = {
                'name': cfg.get('name', key),
                'classes': classes_out,
                'danger_rules': cfg.get('danger_rules', False),
            }
        return result

    def get_model(self, key: str) -> YOLODetector:
        """Get (or lazy-load) a YOLODetector instance by model key."""
        if key not in self._config:
            raise ValueError(f"Unknown model key: {key}")
        if key not in self._instances:
            cfg = self._config[key]
            class_names = {int(k): v for k, v in cfg.get('classes', {}).items()}
            logger.info(f"Loading model '{key}' from {cfg['path']}")
            self._instances[key] = YOLODetector(
                model_path=str(cfg['path']),
                device=cfg.get('device', 'cpu'),
                class_names=class_names,
            )
        return self._instances[key]

    def get_config(self, key: str) -> dict[str, Any]:
        """Get model config dict without loading the model."""
        if key not in self._config:
            raise ValueError(f"Unknown model key: {key}")
        return dict(self._config[key])
