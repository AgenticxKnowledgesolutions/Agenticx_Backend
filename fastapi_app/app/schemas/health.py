from pydantic import BaseModel, Field
from typing import Optional


class HealthResponse(BaseModel):
    status: str = Field(description="The status of the application", default="healthy")
    service: str = Field(description="The name of the service", default="agenticx-backend")
    version: str = Field(description="The version of the service", default="1.0.0")
    environment: str = Field(description="The current deployment environment", default="production")
    timestamp: str = Field(description="UTC timestamp of the health check in ISO format")
    frontend_url: Optional[str] = Field(default=None, description="The frontend URL if configured", serialization_alias="frontend_url")
