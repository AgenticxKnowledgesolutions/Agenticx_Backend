from pydantic import BaseModel
from typing import Optional
from decimal import Decimal
from datetime import datetime


class ProgramBase(BaseModel):
    name: str
    slug: str
    program_type: str
    category: Optional[str] = None
    description: Optional[str] = None
    standard_fee: Decimal = Decimal("0.0")
    duration: Optional[str] = None
    mode: Optional[str] = None
    certificate_template: str = "completion"
    certificate_enabled: bool = True
    verification_enabled: bool = True
    attendance_required: bool = False
    status: str = "active"
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    topics: Optional[str] = None
    domain: Optional[str] = None


class ProgramCreate(ProgramBase):
    pass


class ProgramUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    program_type: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    standard_fee: Optional[Decimal] = None
    duration: Optional[str] = None
    mode: Optional[str] = None
    certificate_template: Optional[str] = None
    certificate_enabled: Optional[bool] = None
    verification_enabled: Optional[bool] = None
    attendance_required: Optional[bool] = None
    status: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    topics: Optional[str] = None
    domain: Optional[str] = None


class ProgramResponse(ProgramBase):
    id: str
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
