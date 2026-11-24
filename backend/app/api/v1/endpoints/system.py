import os
from typing import Any, Dict
from fastapi import APIRouter
from app.core.config import get_settings

router = APIRouter()


@router.get("/config")
async def get_system_config() -> Dict[str, Any]:
    settings = get_settings()
    has_gemini = bool(os.getenv("GEMINI_API_KEY") or settings.gemini_api_key)
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env,
        "provider": settings.default_llm_provider,
        "model": settings.gemini_model,
        "gemini_configured": has_gemini,
        "docker_sandbox_enabled": settings.docker_sandbox_enabled,
    }
