from pydantic import BaseModel
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


# --- Nested schemas (match courseService.ts Course interface exactly) ---

class TechStackItem(BaseModel):
    name: str

    model_config = {"from_attributes": True, "populate_by_name": True}


class ModuleData(BaseModel):
    id: str
    title: str
    description: Optional[str] = None

    model_config = {"from_attributes": True}


class CurriculumMonth(BaseModel):
    tabTitle: str
    sectionTitle: str
    modules: List[ModuleData] = []

    model_config = {"from_attributes": True, "populate_by_name": True}


class CourseStats(BaseModel):
    duration: Optional[str] = None
    format: Optional[str] = None
    projects: Optional[str] = None
    careerSupport: Optional[str] = None


# --- Request schemas ---

class TechStackCreate(BaseModel):
    name: str
    order: int = 0


class CurriculumModuleCreate(BaseModel):
    title: str
    description: Optional[str] = None
    order: int = 0


class CurriculumMonthCreate(BaseModel):
    tab_title: str
    section_title: str
    order: int = 0
    modules: List[CurriculumModuleCreate] = []


class CourseCreate(BaseModel):
    title: str
    slug: str
    description: str
    badge: Optional[str] = None
    price: Decimal = Decimal("0")
    duration: Optional[str] = None
    format: Optional[str] = None
    projects: Optional[str] = None
    career_support: Optional[str] = None
    cover_image_url: Optional[str] = None
    brochure_url: Optional[str] = None
    next_cohort: Optional[str] = None
    mode: str = "hybrid"
    difficulty: str = "intermediate"
    is_ai_optimized: bool = False
    stack: List[TechStackCreate] = []
    curriculum: List[CurriculumMonthCreate] = []


class CourseUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    badge: Optional[str] = None
    price: Optional[Decimal] = None
    duration: Optional[str] = None
    format: Optional[str] = None
    projects: Optional[str] = None
    career_support: Optional[str] = None
    cover_image_url: Optional[str] = None
    brochure_url: Optional[str] = None
    next_cohort: Optional[str] = None
    mode: Optional[str] = None
    difficulty: Optional[str] = None
    is_ai_optimized: Optional[bool] = None
    is_active: Optional[bool] = None
    stack: Optional[List[TechStackCreate]] = None
    curriculum: Optional[List[CurriculumMonthCreate]] = None


# --- Response schema (matches courseService.ts Course interface) ---

class CourseResponse(BaseModel):
    id: str
    slug: str
    badge: Optional[str] = None
    title: str
    description: str
    price: Decimal
    stats: CourseStats
    stack: List[TechStackItem] = []
    curriculum: List[CurriculumMonth] = []
    nextCohort: Optional[str] = None
    coverImageUrl: Optional[str] = None
    brochureUrl: Optional[str] = None
    isAiOptimized: bool = False
    is_deleted: bool = False
    deleted_at: Optional[datetime] = None
    deleted_by: Optional[str] = None

    model_config = {"from_attributes": True}
