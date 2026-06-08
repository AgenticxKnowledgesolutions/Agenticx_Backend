from fastapi import APIRouter, Response
from datetime import datetime, timezone
import logging
from app.core.config import settings
from app.schemas.health import HealthResponse, RootResponse

# Set up standard logger
logger = logging.getLogger("app.health")

router = APIRouter(tags=["health"])


@router.get(
    "/",
    response_model=RootResponse,
    summary="Root metadata endpoint",
    description="Returns lightweight service identification and metadata.",
)
async def get_root() -> RootResponse:
    logger.info("Root endpoint request received")
    return RootResponse(
        status="healthy",
        service="agenticx-backend",
        version=settings.APP_VERSION,
        environment=settings.ENVIRONMENT,
        health="/health",
        docs="/docs",
    )


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


@router.head(
    "/health",
    status_code=200,
    summary="Health check HEAD endpoint",
    description="Returns HTTP 200 with an empty body for automated uptime monitoring checks.",
)
async def head_health() -> Response:
    logger.info("Uptime health check HEAD request received")
    return Response(status_code=200)
