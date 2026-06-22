from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List, Dict
from datetime import datetime


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
    next_followup_at: Optional[datetime] = None
    # Single-use conversion token from email link (replaces plain lead_id in URL)
    token: Optional[str] = Field(None, max_length=255)


class CandidateStatusUpdate(BaseModel):
    status: str = Field(..., max_length=50)
    remarks: Optional[str] = None
    course_start_date: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    course_duration: Optional[str] = None
    performance: Optional[str] = None
    course_applied: Optional[str] = None


class CandidateNoteCreate(BaseModel):
    content: str


class CandidateImportMapping(BaseModel):
    column_mapping: Dict[str, str]
    mode: str = Field("candidate_only", description="candidate_only, lead_only, or lead_candidate")
    tag: Optional[str] = None
