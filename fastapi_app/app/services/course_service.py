from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Optional
from app.models.course import Course, TechStack, CurriculumMonth, CurriculumModule
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse, CourseStats, TechStackItem, CurriculumMonth as CurriculumMonthSchema, ModuleData


def _eager_options():
    return [
        selectinload(Course.stack),
        selectinload(Course.curriculum).selectinload(CurriculumMonth.modules),
    ]


def _to_response(course: Course) -> CourseResponse:
    """Map ORM Course → CourseResponse with nested stats/stack/curriculum."""
    return CourseResponse(
        id=course.id,
        slug=course.slug,
        badge=course.badge,
        title=course.title,
        description=course.description,
        price=course.price,
        nextCohort=course.next_cohort,
        coverImageUrl=course.cover_image_url,
        brochureUrl=course.brochure_url,
        isAiOptimized=course.is_ai_optimized,
        stats=CourseStats(
            duration=course.duration,
            format=course.format,
            projects=course.projects,
            careerSupport=course.career_support,
        ),
        stack=[TechStackItem(name=s.name) for s in course.stack],
        curriculum=[
            CurriculumMonthSchema(
                tabTitle=m.tab_title,
                sectionTitle=m.section_title,
                modules=[ModuleData(id=mod.id, title=mod.title, description=mod.description) for mod in m.modules],
            )
            for m in course.curriculum
        ],
    )


async def list_courses(db: AsyncSession) -> List[CourseResponse]:
    result = await db.execute(
        select(Course).where(Course.is_active == True, Course.is_deleted == False)
        .options(*_eager_options())
        .order_by(Course.created_at.desc())
    )
    courses = result.scalars().unique().all()
    return [_to_response(c) for c in courses]


async def get_course_by_slug(db: AsyncSession, slug: str) -> CourseResponse | None:
    result = await db.execute(
        select(Course).where(Course.slug == slug, Course.is_active == True, Course.is_deleted == False)
        .options(*_eager_options())
    )
    course = result.scalar_one_or_none()
    return _to_response(course) if course else None


async def get_course_orm(db: AsyncSession, course_id: str) -> Course | None:
    result = await db.execute(
        select(Course).where(Course.id == course_id, Course.is_deleted == False).options(*_eager_options())
    )
    return result.scalar_one_or_none()


async def create_course(db: AsyncSession, data: CourseCreate) -> CourseResponse:
    course_data = data.model_dump(exclude={"stack", "curriculum"})
    course = Course(**course_data)

    for i, s in enumerate(data.stack):
        course.stack.append(TechStack(name=s.name, icon_url=None, order=s.order or i))

    for i, month in enumerate(data.curriculum):
        cm = CurriculumMonth(tab_title=month.tab_title, section_title=month.section_title, order=month.order or i)
        for j, mod in enumerate(month.modules):
            cm.modules.append(CurriculumModule(title=mod.title, description=mod.description, order=mod.order or j))
        course.curriculum.append(cm)

    db.add(course)
    await db.commit()
    result = await db.execute(
        select(Course).where(Course.id == course.id).options(*_eager_options())
    )
    return _to_response(result.scalar_one())


async def update_course(db: AsyncSession, course: Course, data: CourseUpdate) -> CourseResponse:
    course_data = data.model_dump(exclude={"stack", "curriculum"}, exclude_none=True)
    for field, value in course_data.items():
        setattr(course, field, value)

    # Rebuild stack if supplied
    if data.stack is not None:
        course.stack.clear()
        for i, s in enumerate(data.stack):
            course.stack.append(TechStack(name=s.name, icon_url=None, order=s.order or i))

    # Rebuild curriculum if supplied
    if data.curriculum is not None:
        course.curriculum.clear()
        for i, month in enumerate(data.curriculum):
            cm = CurriculumMonth(tab_title=month.tab_title, section_title=month.section_title, order=month.order or i)
            for j, mod in enumerate(month.modules):
                cm.modules.append(CurriculumModule(title=mod.title, description=mod.description, order=mod.order or j))
            course.curriculum.append(cm)

    await db.commit()
    result = await db.execute(
        select(Course).where(Course.id == course.id).options(*_eager_options())
    )
    return _to_response(result.scalar_one())


async def delete_course(db: AsyncSession, course: Course, user_email: Optional[str] = None) -> None:
    course.is_deleted = True
    course.deleted_at = datetime.utcnow()
    course.deleted_by = user_email
    await db.commit()


async def list_trash_courses(db: AsyncSession) -> List[CourseResponse]:
    result = await db.execute(
        select(Course).where(Course.is_deleted == True)
        .options(*_eager_options())
        .order_by(Course.deleted_at.desc())
    )
    courses = result.scalars().unique().all()
    return [_to_response(c) for c in courses]


async def restore_course(db: AsyncSession, course: Course) -> CourseResponse:
    course.is_deleted = False
    course.deleted_at = None
    course.deleted_by = None
    await db.commit()
    return _to_response(course)


async def hard_delete_course(db: AsyncSession, course: Course) -> None:
    await db.delete(course)
    await db.commit()
