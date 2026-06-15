from __future__ import annotations

import logging

from fastapi import APIRouter

from app.core.model_registry import ModelRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix='/api/v1/models', tags=['models'])

_registry: ModelRegistry | None = None


def get_registry() -> ModelRegistry:
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


@router.get('')
def list_models():
    """Return available models with metadata (no model loading)."""
    registry = get_registry()
    return {'models': registry.get_available_models()}
