"""Model catalogue endpoint.

Lists the free models OpenRouter currently offers, so a valid id can be chosen
for the ``LLM_MODEL`` setting.
"""

import logging

import httpx
from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.llm import factory
from app.llm import models as model_catalogue
from app.schemas import FreeModel, SelectedModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/models", tags=["models"])


@router.get("/free", response_model=list[FreeModel])
def free_models():
    settings = get_settings()
    try:
        return model_catalogue.list_free_models(settings.openrouter_base_url)
    except httpx.HTTPError as exc:
        logger.error("failed to fetch model catalogue: %s", exc)
        raise HTTPException(status_code=502, detail="Could not reach the model provider.")


@router.get("/selected", response_model=SelectedModel)
def selected_model():
    """Report which model the pipeline will use right now.

    When no model is pinned, this is the best currently-available free model.
    """
    settings = get_settings()
    if not settings.llm_enabled:
        return SelectedModel(model=None, source="stub", reason="No API key configured.")
    model = factory.resolve_model()
    if model is None:
        return SelectedModel(
            model=None, source="stub", reason="No free model is currently available."
        )
    source = "pinned" if settings.llm_model else "auto-selected"
    return SelectedModel(model=model, source=source)
