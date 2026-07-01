import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Integer, Boolean, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class CandidateOTP(Base):
    __tablename__ = "candidate_otps"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    hashed_otp: Mapped[str] = mapped_column(String(255), nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
