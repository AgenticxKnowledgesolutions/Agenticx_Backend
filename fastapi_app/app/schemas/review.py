from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ReviewCreate(BaseModel):
    name: str
    rating: int
    review: str
    role: Optional[str] = None
    image_url: Optional[str] = None
    source: str = "internal"
    is_featured: bool = False


class ReviewUpdate(BaseModel):
    name: Optional[str] = None
    rating: Optional[int] = None
    review: Optional[str] = None
    role: Optional[str] = None
    image_url: Optional[str] = None
    source: Optional[str] = None
    is_active: Optional[bool] = None
    is_featured: Optional[bool] = None


class ReviewResponse(BaseModel):
    id: str
    name: str
    rating: int
    review: str
    role: Optional[str] = None
    image_url: Optional[str] = None
    source: str
    is_active: bool
    is_featured: bool
    created_at: datetime

    model_config = {"from_attributes": True}
