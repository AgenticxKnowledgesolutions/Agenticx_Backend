from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: str  # accepts email or username
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: str
    email: str
    username: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class CandidateOTPRequest(BaseModel):
    email: EmailStr


class CandidateOTPVerify(BaseModel):
    email: EmailStr
    otp: str
