import uuid
import enum
from datetime import datetime
from decimal import Decimal
from typing import List
from sqlalchemy import (
    String, Boolean, DateTime, Text, Numeric, Integer,
    ForeignKey, Enum as SAEnum, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base


class CourseMode(str, enum.Enum):
    online = "online"
    offline = "offline"
    hybrid = "hybrid"


class CourseDifficulty(str, enum.Enum):
    beginner = "beginner"
    intermediate = "intermediate"
    advanced = "advanced"


class TechStack(Base):
    __tablename__ = "tech_stacks"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    icon_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped["Course"] = relationship(back_populates="stack")


class CurriculumModule(Base):
    __tablename__ = "curriculum_modules"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    month_id: Mapped[str] = mapped_column(
        String, ForeignKey("curriculum_months.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    order: Mapped[int] = mapped_column(Integer, default=0)

    month: Mapped["CurriculumMonth"] = relationship(back_populates="modules")


class CurriculumMonth(Base):
    __tablename__ = "curriculum_months"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    course_id: Mapped[str] = mapped_column(
        String, ForeignKey("courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tab_title: Mapped[str] = mapped_column(String(255), nullable=False)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    order: Mapped[int] = mapped_column(Integer, default=0)

    course: Mapped["Course"] = relationship(back_populates="curriculum")
    modules: Mapped[List[CurriculumModule]] = relationship(
        back_populates="month",
        cascade="all, delete-orphan",
        order_by=CurriculumModule.order,
    )


class Course(Base):
    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    badge: Mapped[str | None] = mapped_column(String(100), nullable=True)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), default=0)
    # Flattened stats fields (serialised into stats:{} in schema)
    duration: Mapped[str | None] = mapped_column(String(100), nullable=True)
    format: Mapped[str | None] = mapped_column(String(100), nullable=True)
    projects: Mapped[str | None] = mapped_column(String(100), nullable=True)
    career_support: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    brochure_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    next_cohort: Mapped[str | None] = mapped_column(String(100), nullable=True)
    mode: Mapped[CourseMode] = mapped_column(SAEnum(CourseMode), default=CourseMode.hybrid)
    difficulty: Mapped[CourseDifficulty] = mapped_column(SAEnum(CourseDifficulty), default=CourseDifficulty.intermediate)
    is_ai_optimized: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_by: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    stack: Mapped[List[TechStack]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by=TechStack.order,
    )
    curriculum: Mapped[List[CurriculumMonth]] = relationship(
        back_populates="course",
        cascade="all, delete-orphan",
        order_by=CurriculumMonth.order,
    )
