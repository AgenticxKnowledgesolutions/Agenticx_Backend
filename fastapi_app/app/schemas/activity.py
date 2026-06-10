from pydantic import BaseModel
from typing import Optional
from datetime import datetime
from decimal import Decimal


class ActivityCreate(BaseModel):
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    duration: str
    price: Optional[Decimal] = None
    is_free: bool = False
    activity_type: str = "webinar"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    registration_url: Optional[str] = None


class ActivityUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    image_url: Optional[str] = None
    duration: Optional[str] = None
    price: Optional[Decimal] = None
    is_free: Optional[bool] = None
    activity_type: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    registration_url: Optional[str] = None
    is_active: Optional[bool] = None


class ActivityResponse(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    image_url: Optional[str] = None
    duration: str
    price: Optional[Decimal] = None
    is_free: bool
    activity_type: str
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    registration_url: Optional[str] = None
    is_active: bool
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}
