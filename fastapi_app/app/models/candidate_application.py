import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Boolean, Integer, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class CandidateImportBatch(Base):
    __tablename__ = "candidate_import_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by: Mapped[str] = mapped_column(String(255), nullable=False)
    total_rows: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    new_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    updated_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    duplicate_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_records: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CandidateApplication(Base):
    __tablename__ = "candidate_applications"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    lead_id: Mapped[str | None] = mapped_column(String, ForeignKey("leads.id"), nullable=True)
    
    application_number: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(20), nullable=True)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    emergency_contact: Mapped[str | None] = mapped_column(String(20), nullable=True)
    qualification: Mapped[str | None] = mapped_column(String(255), nullable=True)
    blood_group: Mapped[str | None] = mapped_column(String(20), nullable=True)
    course_applied: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mode_of_learning: Mapped[str | None] = mapped_column(String(100), nullable=True)
    college_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    date_of_birth: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    gender: Mapped[str | None] = mapped_column(String(50), nullable=True)
    reference_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    languages_known: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_guardian_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_guardian_occupation: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Secure encrypted Aadhaar stored as text
    aadhaar_number_encrypted: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    registration_transaction_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    application_status: Mapped[str] = mapped_column(String(50), default="Submitted", nullable=False)
    document_status: Mapped[str] = mapped_column(String(50), default="Missing Documents", nullable=False)
    candidate_source: Mapped[str] = mapped_column(String(100), default="Website", nullable=False)
    candidate_token: Mapped[str] = mapped_column(String(255), unique=True, index=True, default=lambda: uuid.uuid4().hex)
    next_followup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Storage URLs
    cv_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    photo_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    aadhaar_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    college_id_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    confirmation_letter_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    
    # Import references
    import_batch_id: Mapped[str | None] = mapped_column(String, ForeignKey("candidate_import_batches.id"), nullable=True)
    import_tag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    notes: Mapped[list["CandidateNote"]] = relationship(
        "CandidateNote", back_populates="candidate", cascade="all, delete-orphan", order_by="desc(CandidateNote.created_at)"
    )
    timeline_events: Mapped[list["CandidateTimelineEvent"]] = relationship(
        "CandidateTimelineEvent", back_populates="candidate", cascade="all, delete-orphan", order_by="desc(CandidateTimelineEvent.created_at)"
    )


class CandidateNote(Base):
    __tablename__ = "candidate_notes"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String, ForeignKey("candidate_applications.id"), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped[CandidateApplication] = relationship("CandidateApplication", back_populates="notes")


class CandidateTimelineEvent(Base):
    __tablename__ = "candidate_timeline"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    candidate_id: Mapped[str] = mapped_column(String, ForeignKey("candidate_applications.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    created_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    candidate: Mapped[CandidateApplication] = relationship("CandidateApplication", back_populates="timeline_events")
