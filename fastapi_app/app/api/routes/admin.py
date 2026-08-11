from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.deps import require_admin
from app.models.user import User
from app.services.admin_profile_service import AdminProfileService

router = APIRouter(prefix="/admin", tags=["admin"])


class EmailChangeRequestPayload(BaseModel):
    new_email: EmailStr


class EmailChangeVerifyPayload(BaseModel):
    otp: str = Field(..., min_length=1, max_length=10)


class PasswordChangePayload(BaseModel):
    current_password: str
    new_password: str = Field(..., min_length=8)


@router.get("/profile")
async def get_admin_profile(
    current_user: User = Depends(require_admin)
):
    """Admin: Get current authenticated admin profile information."""
    return AdminProfileService.get_profile(current_user)


@router.post("/profile/email/request")
async def request_email_change(
    payload: EmailChangeRequestPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Request an email address update and trigger OTP transmission."""
    return await AdminProfileService.request_email_change(db, current_user, payload.new_email)


@router.post("/profile/email/verify")
async def verify_email_change_otp(
    payload: EmailChangeVerifyPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Verify OTP and update admin email address."""
    return await AdminProfileService.verify_email_change_otp(db, current_user, payload.otp)


@router.post("/profile/password")
async def change_password(
    payload: PasswordChangePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Change current admin password."""
    return await AdminProfileService.change_password(
        db, current_user, payload.current_password, payload.new_password
    )
