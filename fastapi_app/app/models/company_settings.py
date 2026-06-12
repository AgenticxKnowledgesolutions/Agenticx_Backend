from datetime import datetime
from sqlalchemy import String, Integer, Text, DateTime, func, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column
from app.models.base import Base


class CompanySettings(Base):
    __tablename__ = "company_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    
    # Company Information
    company_name: Mapped[str] = mapped_column(String(255), default="AgenticX Knowledge Solutions")
    company_tagline: Mapped[str | None] = mapped_column(String(255), nullable=True)
    company_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Contact Information
    primary_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    secondary_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    primary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    secondary_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website_url: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Address Information
    address_line_1: Mapped[str | None] = mapped_column(String(255), nullable=True)
    address_line_2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(100), nullable=True)
    state: Mapped[str | None] = mapped_column(String(100), nullable=True)
    country: Mapped[str | None] = mapped_column(String(100), nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Homepage Statistics
    placement_assistance_percentage: Mapped[int] = mapped_column(Integer, default=100)
    college_partners_count: Mapped[int] = mapped_column(Integer, default=20)
    graduates_trained_count: Mapped[int] = mapped_column(Integer, default=250)
    students_trained_count: Mapped[int] = mapped_column(Integer, default=100)
    core_services_count: Mapped[int] = mapped_column(Integer, default=5)

    # Social Links
    linkedin_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    whatsapp_number: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Hero Section
    hero_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hero_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hero_primary_cta_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hero_secondary_cta_text: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # SEO Settings
    meta_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    meta_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    meta_keywords: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Global Curriculum Brochure
    curriculum_brochure_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        CheckConstraint("id = 1", name="company_settings_singleton"),
    )
