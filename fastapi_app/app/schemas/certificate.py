from pydantic import BaseModel, EmailStr, Field
from typing import Optional


class CertificateFetchRequest(BaseModel):
    email: EmailStr = Field(..., description="Candidate email address")
    dob: str = Field(..., description="Candidate Date of Birth (YYYY-MM-DD format)")


class CertificateFetchResponse(BaseModel):
    name: str = Field(..., description="Recipient full name")
    course: str = Field(..., description="Name of the course completed")
    completion_date: str = Field(..., description="Date of certificate generation/completion")
    certificate_url: str = Field(..., description="Link to download the certificate PDF")
    certificate_id: str = Field(..., description="Secure unique certificate identification UUID")


class CertificateVerifyResponse(BaseModel):
    name: str = Field(..., description="Recipient full name")
    course: str = Field(..., description="Name of the course completed")
    status: str = Field(..., description="Verification status (valid | revoked)")
    completion_date: str = Field(..., description="Date of certificate completion")
    certificate_url: Optional[str] = Field(None, description="Link to download the certificate PDF for verification")
    certificate_id: Optional[str] = Field(None, description="Certificate application number (CAF format)")
