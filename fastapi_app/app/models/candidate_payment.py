import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, ForeignKey, Float, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class CandidatePayment(Base):
    __tablename__ = "candidate_payments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String, ForeignKey("candidate_applications.id"), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    payment_type: Mapped[str] = mapped_column(String(50), nullable=False)  # 'Admission Fee', 'Booking Amount', 'Installment'
    payment_method: Mapped[str] = mapped_column(String(50), nullable=False)  # 'UPI', 'Razorpay', 'Cash', 'Bank Transfer'
    status: Mapped[str] = mapped_column(String(50), default="Pending", nullable=False)  # 'Pending', 'Paid', 'Failed'
    transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    payment_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped["CandidateApplication"] = relationship("CandidateApplication", back_populates="payments")
