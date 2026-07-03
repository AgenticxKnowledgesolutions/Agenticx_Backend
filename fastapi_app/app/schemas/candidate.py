from pydantic import BaseModel, EmailStr, Field, model_validator
from typing import Optional, List, Dict
from datetime import datetime
from app.models.enums import ProgramType, PerformanceType


class CandidateCreate(BaseModel):
    full_name: str = Field(..., max_length=255)
    email: EmailStr
    phone: str = Field(..., max_length=20)
    whatsapp_number: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None
    emergency_contact: Optional[str] = Field(None, max_length=20)
    qualification: Optional[str] = Field(None, max_length=255)
    blood_group: Optional[str] = Field(None, max_length=20)
    course_applied: Optional[str] = Field(None, max_length=255)
    mode_of_learning: Optional[str] = Field(None, max_length=100)
    college_name: Optional[str] = Field(None, max_length=255)
    date_of_birth: Optional[datetime] = None
    gender: Optional[str] = Field(None, max_length=50)
    reference_details: Optional[str] = None
    languages_known: Optional[str] = Field(None, max_length=255)
    parent_guardian_name: Optional[str] = Field(None, max_length=255)
    parent_guardian_occupation: Optional[str] = Field(None, max_length=255)
    aadhaar_number: Optional[str] = Field(None, max_length=20)
    registration_transaction_id: Optional[str] = Field(None, max_length=255)
    remarks: Optional[str] = None
    lead_id: Optional[str] = None
    program_id: Optional[str] = None
    next_followup_at: Optional[datetime] = None
    # Single-use conversion token from email link (replaces plain lead_id in URL)
    token: Optional[str] = Field(None, max_length=255)
    program_type: Optional[ProgramType] = None
    programme_domain: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_fdp_requirements(self) -> "CandidateCreate":
        if self.program_type == ProgramType.FACULTY_DEVELOPMENT_PROGRAMME:
            if not self.college_name or not self.college_name.strip():
                raise ValueError("College / Institution Name is required for Faculty Development Programme.")
            if not self.programme_domain or not self.programme_domain.strip():
                raise ValueError("Programme Domain is required for Faculty Development Programme.")
        return self


class CandidateStatusUpdate(BaseModel):
    status: str = Field(..., max_length=50)
    course_start_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    course_duration: Optional[str] = None
    performance: Optional[PerformanceType] = None
    program_type: Optional[ProgramType] = None
    course_applied: Optional[str] = None
    program_id: Optional[str] = None
    programme_domain: Optional[str] = Field(None, max_length=255)
    college_name: Optional[str] = Field(None, max_length=255)

    @model_validator(mode="after")
    def validate_fdp_update(self) -> "CandidateStatusUpdate":
        if self.status.lower() == "completed" and self.program_type == ProgramType.FACULTY_DEVELOPMENT_PROGRAMME:
            if not self.college_name or not self.college_name.strip():
                raise ValueError("College / Institution Name is required for Faculty Development Programme.")
            if not self.programme_domain or not self.programme_domain.strip():
                raise ValueError("Programme Domain is required for Faculty Development Programme.")
        return self


class CandidateNoteCreate(BaseModel):
    content: str


class CandidateImportMapping(BaseModel):
    column_mapping: Dict[str, str]
    mode: str = Field("candidate_only", description="candidate_only, lead_only, or lead_candidate")
    tag: Optional[str] = None


class BulkDeleteCandidatesPayload(BaseModel):
    candidate_ids: List[str]


class BulkRegenerateCertificatesPayload(BaseModel):
    candidate_ids: List[str]


class CandidateOfferUpdate(BaseModel):
    standard_course_fee: Optional[float] = Field(None, ge=0)
    scholarship_amount: float = Field(0.0, ge=0)
    special_discount: float = Field(0.0, ge=0)
    corporate_discount: float = Field(0.0, ge=0)
    promo_discount: float = Field(0.0, ge=0)
    booking_amount: float = Field(0.0, ge=0)
    offer_remarks: Optional[str] = None
    offer_expiry_date: Optional[datetime] = None
    admission_fee_amount: float = Field(250.0, ge=0)
    auto_enroll_enabled: bool = True


class RecordOfflinePayment(BaseModel):
    amount: float = Field(..., gt=0)
    payment_type: str = Field(..., max_length=50)  # 'Admission Fee', 'Booking Amount', 'Installment'
    payment_method: str = Field(..., max_length=50)  # 'Cash', 'UPI', 'Bank Transfer', 'Razorpay'
    transaction_id: Optional[str] = Field(None, max_length=255)


class CreateOrderRequest(BaseModel):
    amount: float = Field(..., gt=0)
    payment_type: str = Field(..., max_length=50)


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str
    payment_type: str
    amount: float
