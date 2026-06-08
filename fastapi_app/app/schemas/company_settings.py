from pydantic import BaseModel, EmailStr, HttpUrl
from typing import Optional
from datetime import datetime


class CompanySettingsUpdate(BaseModel):
    company_name: Optional[str] = None
    company_tagline: Optional[str] = None
    company_description: Optional[str] = None

    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    secondary_email: Optional[str] = None
    website_url: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    google_maps_url: Optional[str] = None

    placement_assistance_percentage: Optional[int] = None
    college_partners_count: Optional[int] = None
    graduates_trained_count: Optional[int] = None
    students_trained_count: Optional[int] = None
    core_services_count: Optional[int] = None

    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    youtube_url: Optional[str] = None
    whatsapp_number: Optional[str] = None

    hero_title: Optional[str] = None
    hero_description: Optional[str] = None
    hero_primary_cta_text: Optional[str] = None
    hero_secondary_cta_text: Optional[str] = None

    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


class CompanySettingsResponse(BaseModel):
    id: int
    company_name: str
    company_tagline: Optional[str] = None
    company_description: Optional[str] = None

    primary_phone: Optional[str] = None
    secondary_phone: Optional[str] = None
    primary_email: Optional[str] = None
    secondary_email: Optional[str] = None
    website_url: Optional[str] = None

    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    country: Optional[str] = None
    postal_code: Optional[str] = None
    google_maps_url: Optional[str] = None

    placement_assistance_percentage: int
    college_partners_count: int
    graduates_trained_count: int
    students_trained_count: int
    core_services_count: int

    linkedin_url: Optional[str] = None
    instagram_url: Optional[str] = None
    facebook_url: Optional[str] = None
    youtube_url: Optional[str] = None
    whatsapp_number: Optional[str] = None

    hero_title: Optional[str] = None
    hero_description: Optional[str] = None
    hero_primary_cta_text: Optional[str] = None
    hero_secondary_cta_text: Optional[str] = None

    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None

    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
