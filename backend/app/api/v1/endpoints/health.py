from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from app.core.config import Settings, get_settings
from app.schemas.common import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def check_health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        environment=settings.app_env,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
