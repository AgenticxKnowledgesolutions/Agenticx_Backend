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
    # Certificate V2 Metadata Section
    certificate_title: Optional[str] = None
    certificate_subtitle: Optional[str] = None
    certificate_body_template: Optional[str] = None
    certificate_domain: Optional[str] = None
    certificate_topics: Optional[str] = None
    certificate_partner: Optional[str] = None
    certificate_duration: Optional[str] = None
    certificate_default_mode: Optional[str] = None
    certificate_default_program_type: Optional[str] = None
    certificate_footer: Optional[str] = None
    certificate_signatory_name: Optional[str] = None
    certificate_signatory_title: Optional[str] = None
    certificate_signature_image: Optional[str] = None
    certificate_logo: Optional[str] = None
    certificate_background: Optional[str] = None
    certificate_qr_enabled: bool = True
    certificate_verification_enabled: bool = True


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
    certificate_title: Optional[str] = None
    certificate_subtitle: Optional[str] = None
    certificate_body_template: Optional[str] = None
    certificate_domain: Optional[str] = None
    certificate_topics: Optional[str] = None
    certificate_partner: Optional[str] = None
    certificate_duration: Optional[str] = None
    certificate_default_mode: Optional[str] = None
    certificate_default_program_type: Optional[str] = None
    certificate_footer: Optional[str] = None
    certificate_signatory_name: Optional[str] = None
    certificate_signatory_title: Optional[str] = None
    certificate_signature_image: Optional[str] = None
    certificate_logo: Optional[str] = None
    certificate_background: Optional[str] = None
    certificate_qr_enabled: Optional[bool] = None
    certificate_verification_enabled: Optional[bool] = None


class ProgramResponse(ProgramBase):
    id: str
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
