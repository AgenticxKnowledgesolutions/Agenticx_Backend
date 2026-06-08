import uuid
import enum
from datetime import datetime
from decimal import Decimal
from sqlalchemy import String, Boolean, DateTime, Text, Numeric, Enum as SAEnum, func
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class ActivityType(str, enum.Enum):
    webinar = "webinar"
    bootcamp = "bootcamp"
    workshop = "workshop"
    seminar = "seminar"


class Activity(Base):
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    duration: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    is_free: Mapped[bool] = mapped_column(Boolean, default=False)
    activity_type: Mapped[ActivityType] = mapped_column(SAEnum(ActivityType), default=ActivityType.webinar)
    start_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    registration_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
