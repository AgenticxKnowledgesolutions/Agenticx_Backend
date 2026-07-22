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
    
    existing_template = "completion"
    existing_cert_enabled = True
    existing_verif_enabled = True
    existing_attendance = False
    existing_status = "active"
    existing_category = None
    existing_topics = None
    existing_domain = None
    existing_start_date = None
    existing_end_date = None

    if not program:
        # Check if another program has the same name or slug to avoid unique constraint violations
        existing_result = await db.execute(
            select(Program).where((Program.name == course.title) | (Program.slug == course.slug))
        )
        existing_program = existing_result.scalar_one_or_none()
        
        lead_ids = []
        candidate_ids = []
        
        if existing_program:
            old_id = existing_program.id
            existing_template = existing_program.certificate_template
            existing_cert_enabled = existing_program.certificate_enabled
            existing_verif_enabled = existing_program.verification_enabled
            existing_attendance = existing_program.attendance_required
            existing_status = existing_program.status
            existing_category = existing_program.category
            existing_topics = existing_program.topics
            existing_domain = existing_program.domain
            existing_start_date = existing_program.start_date
            existing_end_date = existing_program.end_date

            # Fetch IDs of leads and candidates pointing to the old program ID
            from app.models.lead import Lead
            from app.models.candidate_application import CandidateApplication
            
            lead_ids_res = await db.execute(
                select(Lead.id).where(Lead.program_id == old_id)
            )
            lead_ids = list(lead_ids_res.scalars().all())

            candidate_ids_res = await db.execute(
                select(CandidateApplication.id).where(CandidateApplication.program_id == old_id)
            )
            candidate_ids = list(candidate_ids_res.scalars().all())
            
            # Delete old program to release the unique name/slug constraints.
            # This sets leads.program_id and candidate_applications.program_id to NULL.
            await db.delete(existing_program)
            await db.flush()

        program = Program(id=course.id)
        db.add(program)
        program.certificate_template = existing_template
        program.certificate_enabled = existing_cert_enabled
        program.verification_enabled = existing_verif_enabled
        program.attendance_required = existing_attendance
        program.status = existing_status
        program.category = existing_category
        program.topics = existing_topics
        program.domain = existing_domain
        program.start_date = existing_start_date
        program.end_date = existing_end_date

        # Populate new program fields before flush so that it is a fully valid record
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

        # Flush to insert the new Program with course.id into the database
        await db.flush()

        # Now that the new Program exists, we can update the associated leads and candidates
        if existing_program:
            from app.models.lead import Lead
            from app.models.candidate_application import CandidateApplication
            from sqlalchemy import update

            if lead_ids:
                await db.execute(
                    update(Lead).where(Lead.id.in_(lead_ids)).values(program_id=course.id)
                )
            if candidate_ids:
                await db.execute(
                    update(CandidateApplication).where(CandidateApplication.id.in_(candidate_ids)).values(program_id=course.id)
                )
    
    # Update fields again in case the program already existed or has been updated
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
    
    # Do not call db.commit() here; the caller will commit the transaction.

