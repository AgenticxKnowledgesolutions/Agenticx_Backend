import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, Text, Boolean, Integer, JSON, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    interested_course: Mapped[str | None] = mapped_column(String(255), nullable=True)
    source_page: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="Pending")
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_followup_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    followup_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), default="Website", nullable=True)
    
    # Phase 3 CRM additions
    priority: Mapped[str] = mapped_column(String(20), default="Cold", nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(50), nullable=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Duplicate lead detection & scoring
    interaction_count: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    last_interaction_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    first_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latest_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    merged_courses: Mapped[list[str] | None] = mapped_column(JSON, default=list, server_default="[]")
    duplicate_hits: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)
    lead_score: Mapped[int] = mapped_column(Integer, default=0, server_default="0", nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    notes: Mapped[list["LeadNote"]] = relationship("LeadNote", back_populates="lead", cascade="all, delete-orphan", order_by="desc(LeadNote.created_at)")
    timeline_events: Mapped[list["LeadTimelineEvent"]] = relationship("LeadTimelineEvent", back_populates="lead", cascade="all, delete-orphan", order_by="desc(LeadTimelineEvent.created_at)")
    interactions: Mapped[list["LeadInteraction"]] = relationship("LeadInteraction", back_populates="lead", cascade="all, delete-orphan", order_by="desc(LeadInteraction.created_at)")

