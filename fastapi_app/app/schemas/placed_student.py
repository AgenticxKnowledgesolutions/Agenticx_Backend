from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class PlacedStudentCreate(BaseModel):
    student_name: str
    company_name: str
    job_role: str
    photo_url: str
    display_order: int = 0
    is_active: bool = True


class PlacedStudentUpdate(BaseModel):
    student_name: Optional[str] = None
    company_name: Optional[str] = None
    job_role: Optional[str] = None
    photo_url: Optional[str] = None
    display_order: Optional[int] = None
    is_active: Optional[bool] = None


class PlacedStudentResponse(BaseModel):
    id: str
    student_name: str
    company_name: str
    job_role: str
    photo_url: str
    display_order: int
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class PlacedStudentPublicResponse(BaseModel):
    id: str
    student_name: str
    company_name: str
    job_role: str
    photo_url: str
    display_order: int

    model_config = {"from_attributes": True}
