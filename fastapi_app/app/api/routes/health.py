from fastapi import APIRouter
from datetime import datetime, timezone
import logging
from app.core.config import settings
from app.schemas.health import HealthResponse

# Set up standard logger
logger = logging.getLogger("app.health")

router = APIRouter(tags=["health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    response_model_exclude_none=True,
    summary="Health check endpoint",
    description="Returns structured health and version information about the API service.",
)
async def get_health() -> HealthResponse:
    logger.info("Uptime health check request received")
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        frontend_url=settings.FRONTEND_URL,
    )
