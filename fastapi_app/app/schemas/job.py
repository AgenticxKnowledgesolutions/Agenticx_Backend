from pydantic import BaseModel, EmailStr
from datetime import datetime
from typing import Optional, List


class JobApplicationBase(BaseModel):
    name: str
    email: EmailStr
    phone: str
    resume_url: str
    status: str = "new"
    is_deleted: bool = False


class JobApplicationCreate(JobApplicationBase):
    pass


class JobApplicationResponse(JobApplicationBase):
    id: str
    job_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class JobApplicationAdminResponse(JobApplicationBase):
    id: str
    job_id: str
    created_at: datetime
    job_title: str

    class Config:
        from_attributes = True


class JobBase(BaseModel):
    title: str
    description: str
    is_active: bool = True


class JobCreate(JobBase):
    pass


class JobResponse(JobBase):
    id: str
    created_at: datetime
    applications: List[JobApplicationResponse] = []

    class Config:
        from_attributes = True
