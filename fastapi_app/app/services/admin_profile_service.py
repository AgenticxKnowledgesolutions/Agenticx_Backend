import uuid
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, Any
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.models.user import User
from app.models.admin_email_verification import AdminEmailVerification
from app.core.security import verify_password, hash_password
from app.services.email_service import EmailService
from app.core.config import settings

logger = logging.getLogger("admin_profile_service")


class AdminProfileService:
    @classmethod
    def get_profile(cls, user: User) -> Dict[str, Any]:
        """Returns safe profile details for the authenticated admin user."""
        role_val = user.role.value if hasattr(user.role, "value") else str(user.role)
        return {
            "id": user.id,
            "name": user.username,
            "username": user.username,
            "email": user.email,
            "role": role_val,
        }

    @classmethod
    async def request_email_change(
        cls,
        db: AsyncSession,
        user: User,
        new_email: str
    ) -> Dict[str, Any]:
        new_email_clean = new_email.strip().lower()

        if not new_email_clean or "@" not in new_email_clean:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Please provide a valid email address."
            )

        if new_email_clean == user.email.lower():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New email address must be different from your current email address."
            )

        # Check if email is registered to another account
        existing_stmt = select(User).where(User.email.ilike(new_email_clean), User.id != user.id)
        existing_res = await db.execute(existing_stmt)
        if existing_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email address is already registered to another account."
            )

        # Throttling check: 60s minimum interval between OTP resends
        recent_stmt = (
            select(AdminEmailVerification)
            .where(
                AdminEmailVerification.user_id == user.id,
                AdminEmailVerification.verified == False,
                AdminEmailVerification.created_at >= datetime.now(timezone.utc) - timedelta(seconds=60)
            )
            .order_by(AdminEmailVerification.created_at.desc())
        )
        recent_res = await db.execute(recent_stmt)
        if recent_res.scalars().first():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Please wait at least 60 seconds before requesting another verification code."
            )

        # Invalidate previous pending verification requests for this user
        invalidate_stmt = (
            update(AdminEmailVerification)
            .where(
                AdminEmailVerification.user_id == user.id,
                AdminEmailVerification.verified == False
            )
            .values(expires_at=datetime.now(timezone.utc))
        )
        await db.execute(invalidate_stmt)

        # Generate 6-digit cryptographically random OTP
        otp_code = f"{secrets.randbelow(900000) + 100000}"
        hashed_otp = hash_password(otp_code)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        verification = AdminEmailVerification(
            id=str(uuid.uuid4()),
            user_id=user.id,
            new_email=new_email_clean,
            hashed_otp=hashed_otp,
            attempts=0,
            expires_at=expires_at,
            verified=False
        )
        db.add(verification)
        await db.commit()

        # Send OTP email
        subject = f"{otp_code} is your AgenticX Admin Email Change Code"
        body = f"""Hi {user.username},

You requested to update your AgenticX Admin Portal email address to: {new_email_clean}

Your 6-digit verification code (OTP) is:

{otp_code}

This code is valid for 10 minutes. If you did not request this change, please ignore this email and ensure your account password remains secure.

Best regards,
AgenticX Security Team
"""
        sent = False
        if settings.RESEND_API_KEY:
            sent = EmailService.send_via_resend(new_email_clean, subject, body)
        else:
            sent = EmailService.send_otp_email(new_email_clean, otp_code)

        return {
            "success": True,
            "message": "Verification code sent to your new email address.",
            "sandbox": not sent,
            "code": otp_code if not sent else None
        }

    @classmethod
    async def verify_email_change_otp(
        cls,
        db: AsyncSession,
        user: User,
        otp_code: str
    ) -> Dict[str, Any]:
        otp_clean = otp_code.strip()

        # Query active unverified verification record
        stmt = (
            select(AdminEmailVerification)
            .where(
                AdminEmailVerification.user_id == user.id,
                AdminEmailVerification.verified == False,
                AdminEmailVerification.expires_at > datetime.now(timezone.utc)
            )
            .order_by(AdminEmailVerification.created_at.desc())
        )
        res = await db.execute(stmt)
        verifications = res.scalars().all()

        if not verifications:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification code expired or not found. Please request a new code."
            )

        verification = verifications[0]

        if verification.attempts >= 5:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum verification attempts exceeded. Please request a new verification code."
            )

        if not verify_password(otp_clean, verification.hashed_otp):
            verification.attempts += 1
            await db.commit()
            remaining = max(0, 5 - verification.attempts)
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid verification code. Attempts remaining: {remaining}"
            )

        # Check if target new email was taken while waiting for OTP
        conflict_stmt = select(User).where(User.email.ilike(verification.new_email), User.id != user.id)
        conflict_res = await db.execute(conflict_stmt)
        if conflict_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This email address is already registered to another account."
            )

        # Mark verification as consumed & update user email
        verification.verified = True
        user.email = verification.new_email
        await db.commit()
        await db.refresh(user)

        return {
            "success": True,
            "message": "Email address updated successfully.",
            "profile": cls.get_profile(user)
        }

    @classmethod
    async def change_password(
        cls,
        db: AsyncSession,
        user: User,
        current_password: str,
        new_password: str
    ) -> Dict[str, Any]:
        if not verify_password(current_password, user.hashed_password):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect current password."
            )

        if len(new_password) < 8:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="New password must be at least 8 characters long."
            )

        user.hashed_password = hash_password(new_password)
        await db.commit()

        return {
            "success": True,
            "message": "Password updated successfully."
        }
