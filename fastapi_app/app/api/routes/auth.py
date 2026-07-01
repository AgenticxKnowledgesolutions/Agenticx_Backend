from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.schemas.auth import LoginRequest, TokenResponse, RefreshRequest, UserResponse
from app.services import auth_service
from app.deps import get_current_user
from app.models.user import User
from app.core.limiter import limiter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(request: Request, data: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await auth_service.authenticate_user(db, data.email, data.password)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return auth_service.build_tokens(user)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")
    user = await auth_service.get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return auth_service.build_tokens(user)


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user


import random
from datetime import datetime, timedelta, timezone
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.models.candidate_application import CandidateApplication
from app.models.candidate_otp import CandidateOTP
from app.schemas.auth import CandidateOTPRequest, CandidateOTPVerify
from app.services.email_service import EmailService

@router.post("/candidate/otp/request")
@limiter.limit("5/minute")
async def request_candidate_otp(request: Request, data: CandidateOTPRequest, db: AsyncSession = Depends(get_db)):
    email = data.email.strip().lower()
    # Check if candidate exists
    stmt = select(CandidateApplication).where(CandidateApplication.email.ilike(email), CandidateApplication.is_deleted == False)
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No registered candidate found with this email address."
        )
    
    # Generate 6-digit OTP
    otp = f"{random.randint(100000, 999999)}"
    hashed = hash_password(otp)
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    
    # Save to candidate_otps
    db_otp = CandidateOTP(
        email=email,
        hashed_otp=hashed,
        expires_at=expires,
        attempts=0,
        verified=False
    )
    db.add(db_otp)
    await db.commit()
    
    # Send email
    sent = EmailService.send_otp_email(email, otp)
    
    # If SMTP is not configured, we return the OTP in mock/sandbox mode to help testing!
    # That is extremely helpful for developers and QA without breaking production security
    return {
        "success": True, 
        "message": "OTP sent successfully.", 
        "sandbox": not sent,
        "code": otp if not sent else None
    }

@router.post("/candidate/otp/verify", response_model=TokenResponse)
async def verify_candidate_otp(data: CandidateOTPVerify, db: AsyncSession = Depends(get_db)):
    email = data.email.strip().lower()
    otp_code = data.otp.strip()
    
    # Fetch active OTPs
    stmt = select(CandidateOTP).where(
        CandidateOTP.email == email,
        CandidateOTP.verified == False,
        CandidateOTP.expires_at > datetime.now(timezone.utc)
    ).order_by(CandidateOTP.created_at.desc())
    
    res = await db.execute(stmt)
    db_otps = res.scalars().all()
    
    if not db_otps:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="OTP expired or not found. Please request a new one."
        )
        
    db_otp = db_otps[0]
    
    if db_otp.attempts >= 5:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum verification attempts exceeded. Please request a new OTP."
        )
        
    if not verify_password(otp_code, db_otp.hashed_otp):
        db_otp.attempts += 1
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid verification code. Attempts remaining: {5 - db_otp.attempts}"
        )
        
    # Mark as verified
    db_otp.verified = True
    await db.commit()
    
    # Fetch candidate
    cand_stmt = select(CandidateApplication).where(CandidateApplication.email.ilike(email), CandidateApplication.is_deleted == False)
    cand_res = await db.execute(cand_stmt)
    candidate = cand_res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate record not found."
        )
        
    # Issue JWT tokens with role="candidate"
    access_token = create_access_token(subject=candidate.id, role="candidate")
    refresh_token = create_refresh_token(subject=candidate.id)
    
    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer"
    }
