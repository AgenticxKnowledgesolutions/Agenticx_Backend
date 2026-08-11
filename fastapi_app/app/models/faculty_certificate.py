import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class FacultyCertificate(Base):
    __tablename__ = "faculty_certificates"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    certificate_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    
    # Faculty Details
    faculty_name: Mapped[str] = mapped_column(String(255), nullable=False)
    faculty_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    designation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    organization: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # FDP Details
    programme_title: Mapped[str] = mapped_column(String(255), nullable=False, default="Faculty Development Programme")
    topic: Mapped[str] = mapped_column(String(255), nullable=False, default="Artificial Intelligence & Machine Learning")
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration: Mapped[str] = mapped_column(String(100), nullable=False, default="5 Days")
    mode: Mapped[str | None] = mapped_column(String(100), nullable=True, default="Online")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Organization & Signatory details
    organization_name: Mapped[str] = mapped_column(String(255), nullable=False, default="AgenticX Knowledge Solutions LLP")
    signatory_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    signatory_designation: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # State & Metadata
    status: Mapped[str] = mapped_column(String(50), default="Draft", nullable=False)  # "Draft", "Generated"
    certificate_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    generated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
