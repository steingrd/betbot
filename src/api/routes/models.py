"""Model management endpoints - CRUD for model configs and active model selection."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.models.model_config import DataFilter, ModelConfig

router = APIRouter(prefix="/api/models", tags=["models"])

MODELS_DIR = Path(__file__).parent.parent.parent.parent / "models"
ACTIVE_MODEL_PATH = Path(__file__).parent.parent.parent.parent / "data" / "processed" / "active_model.txt"


class CreateModelRequest(BaseModel):
    name: str
    strategies: list[str] = ["xgboost", "poisson", "elo", "logreg"]
    years: Optional[int] = None


class ModelResponse(BaseModel):
    slug: str
    name: str
    strategies: list[str]
    years: Optional[int]
    is_default: bool
    created_at: str
    is_trained: bool


def _slug_from_name(name: str) -> str:
    """Generate a slug from a display name."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "model"


def _get_active_slug() -> str:
    """Read the active model slug. Defaults to 'standard'."""
    if ACTIVE_MODEL_PATH.exists():
        slug = ACTIVE_MODEL_PATH.read_text().strip()
        if slug:
            return slug
    return "standard"


def _set_active_slug(slug: str) -> None:
    """Write the active model slug."""
    ACTIVE_MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    ACTIVE_MODEL_PATH.write_text(slug)


def _model_is_trained(slug: str) -> bool:
    """Check if a model has any trained strategy files."""
    model_dir = MODELS_DIR / slug
    if not model_dir.exists():
        return False
    return any(model_dir.glob("*.pkl")) or any(model_dir.glob("*.json"))


def _config_to_response(config: ModelConfig) -> ModelResponse:
    return ModelResponse(
        slug=config.slug,
        name=config.name,
        strategies=config.strategies,
        years=config.data_filter.years,
        is_default=config.is_default,
        created_at=config.created_at,
        is_trained=_model_is_trained(config.slug),
    )


@router.get("")
def list_models() -> list[ModelResponse]:
    configs = ModelConfig.list_all(MODELS_DIR)
    active = _get_active_slug()
    result = [_config_to_response(c) for c in configs]
    # Mark active model
    for r in result:
        if r.slug == active:
            r.is_default = True
    return result


@router.post("", status_code=201)
def create_model(req: CreateModelRequest) -> ModelResponse:
    slug = _slug_from_name(req.name)

    # Ensure unique slug
    if (MODELS_DIR / slug / "config.json").exists():
        raise HTTPException(status_code=409, detail=f"Model '{slug}' already exists")

    valid_slugs = {"xgboost", "poisson", "elo", "logreg"}
    invalid = set(req.strategies) - valid_slugs
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown strategies: {invalid}")

    config = ModelConfig(
        slug=slug,
        name=req.name,
        strategies=req.strategies,
        data_filter=DataFilter(years=req.years),
    )
    config.save(MODELS_DIR)
    return _config_to_response(config)


@router.delete("/{slug}")
def delete_model(slug: str):
    if slug == "standard":
        raise HTTPException(status_code=400, detail="Cannot delete the standard model")

    model_dir = MODELS_DIR / slug
    if not (model_dir / "config.json").exists():
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")

    # If this is the active model, switch back to standard
    if _get_active_slug() == slug:
        _set_active_slug("standard")

    shutil.rmtree(model_dir)
    return {"status": "deleted"}


@router.get("/active")
def get_active_model() -> dict:
    return {"slug": _get_active_slug()}


@router.put("/active")
def set_active_model(slug: str) -> dict:
    if not (MODELS_DIR / slug / "config.json").exists():
        raise HTTPException(status_code=404, detail=f"Model '{slug}' not found")
    _set_active_slug(slug)
    return {"slug": slug}
