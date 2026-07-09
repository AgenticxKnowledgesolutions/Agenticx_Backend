from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class CollaboratorCreate(BaseModel):
    name: str
    logo_url: str
    display_order: int = 0
    is_active: bool = True


class CollaboratorUpdate(BaseModel):
    name: Optional[str] = None
    logo_url: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class CollaboratorResponse(BaseModel):
    id: str
    name: str
    logo_url: str
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CollaboratorPublicResponse(BaseModel):
    id: str
    name: str
    logo_url: str
    display_order: int

    model_config = {"from_attributes": True}
