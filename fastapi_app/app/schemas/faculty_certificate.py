from pydantic import BaseModel, Field, EmailStr, model_validator
from typing import Optional
from datetime import datetime


class FacultyCertificateBase(BaseModel):
    faculty_name: str = Field(..., min_length=1, description="Faculty full name")
    faculty_email: Optional[EmailStr] = Field(None, description="Faculty email address")
    designation: Optional[str] = Field(None, description="Faculty designation/title")
    organization: Optional[str] = Field(None, description="Faculty associated organization/institution")

    programme_title: str = Field("Faculty Development Programme", description="Title of the FDP program")
    topic: str = Field("Artificial Intelligence & Machine Learning", description="FDP focus topic")
    start_date: datetime = Field(..., description="Program start date")
    end_date: datetime = Field(..., description="Program end date")
    duration: str = Field("5 Days", description="Program duration")
    mode: Optional[str] = Field("Online", description="Mode of training (e.g. Online, Hybrid, Offline)")
    description: Optional[str] = Field(None, description="Optional FDP details or syllabus description")

    organization_name: str = Field("AgenticX Knowledge Solutions LLP", description="Awarding organization")
    signatory_name: Optional[str] = Field(None, description="Name of authorized signatory")
    signatory_designation: Optional[str] = Field(None, description="Designation of signatory")


class FacultyCertificateCreate(FacultyCertificateBase):
    @model_validator(mode="after")
    def validate_dates(self):
        if self.end_date < self.start_date:
            raise ValueError("end_date cannot be before start_date")
        return self


class FacultyCertificateUpdate(BaseModel):
    faculty_name: Optional[str] = None
    faculty_email: Optional[EmailStr] = None
    designation: Optional[str] = None
    organization: Optional[str] = None

    programme_title: Optional[str] = None
    topic: Optional[str] = None
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    duration: Optional[str] = None
    mode: Optional[str] = None
    description: Optional[str] = None

    organization_name: Optional[str] = None
    signatory_name: Optional[str] = None
    signatory_designation: Optional[str] = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date and self.end_date:
            if self.end_date < self.start_date:
                raise ValueError("end_date cannot be before start_date")
        return self


class FacultyCertificateResponse(FacultyCertificateBase):
    id: str
    certificate_number: str
    status: str
    certificate_url: Optional[str] = None
    
    created_at: datetime
    updated_at: datetime
    generated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
