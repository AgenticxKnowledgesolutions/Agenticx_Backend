from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.models.program import Program
from app.models.course import Course
from app.schemas.program import ProgramCreate, ProgramUpdate, ProgramResponse


async def list_programs(db: AsyncSession) -> List[Program]:
    result = await db.execute(
        select(Program).where(Program.is_deleted == False)
        .order_by(Program.created_at.desc())
    )
    return list(result.scalars().all())


async def list_trash_programs(db: AsyncSession) -> List[Program]:
    result = await db.execute(
        select(Program).where(Program.is_deleted == True)
        .order_by(Program.deleted_at.desc())
    )
    return list(result.scalars().all())


async def get_program_by_slug(db: AsyncSession, slug: str) -> Program | None:
    result = await db.execute(
        select(Program).where(Program.slug == slug, Program.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def get_program_orm(db: AsyncSession, program_id: str) -> Program | None:
    result = await db.execute(
        select(Program).where(Program.id == program_id, Program.is_deleted == False)
    )
    return result.scalar_one_or_none()


async def create_program(db: AsyncSession, data: ProgramCreate) -> Program:
    program_data = data.model_dump()
    program = Program(**program_data)
    db.add(program)
    await db.commit()
    await db.refresh(program)
    return program


async def update_program(db: AsyncSession, program: Program, data: ProgramUpdate) -> Program:
    program_data = data.model_dump(exclude_none=True)
    for field, value in program_data.items():
        setattr(program, field, value)
    await db.commit()
    await db.refresh(program)
    return program


async def delete_program(db: AsyncSession, program: Program, user_email: Optional[str] = None) -> None:
    program.is_deleted = True
    program.deleted_at = datetime.utcnow()
    program.deleted_by = user_email
    await db.commit()


async def restore_program(db: AsyncSession, program: Program) -> Program:
    program.is_deleted = False
    program.deleted_at = None
    program.deleted_by = None
    await db.commit()
    await db.refresh(program)
    return program


async def hard_delete_program(db: AsyncSession, program: Program) -> None:
    await db.delete(program)
    await db.commit()


async def sync_course_to_program(db: AsyncSession, course: Course) -> None:
    """Helper to synchronize Course model changes to the corresponding Program."""
    result = await db.execute(select(Program).where(Program.id == course.id))
    program = result.scalar_one_or_none()
    if not program:
        program = Program(id=course.id)
        db.add(program)
    
    program.name = course.title
    program.slug = course.slug
    program.program_type = "Course"
    program.description = course.description
    program.standard_fee = course.price
    program.duration = course.duration
    program.mode = course.mode.value if hasattr(course.mode, "value") else str(course.mode)
    program.is_deleted = course.is_deleted
    program.deleted_at = course.deleted_at
    program.deleted_by = course.deleted_by
    program.certificate_template = "completion"
    
    # Do not call db.commit() here; the caller will commit the transaction.
