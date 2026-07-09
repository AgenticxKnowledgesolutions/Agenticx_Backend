from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from app.models.placed_student import PlacedStudent
from app.schemas.placed_student import PlacedStudentCreate, PlacedStudentUpdate


async def shift_display_orders(db: AsyncSession, target_order: int, exclude_id: Optional[str] = None) -> None:
    """Increment display_order of all placed students with display_order >= target_order by 1."""
    stmt = (
        update(PlacedStudent)
        .where(PlacedStudent.display_order >= target_order)
    )
    if exclude_id:
        stmt = stmt.where(PlacedStudent.id != exclude_id)
        
    stmt = stmt.values(display_order=PlacedStudent.display_order + 1)
    await db.execute(stmt)


async def list_active_placed_students(db: AsyncSession) -> List[PlacedStudent]:
    """Returns active placed students sorted by display_order ascending."""
    result = await db.execute(
        select(PlacedStudent)
        .where(PlacedStudent.is_active == True)
        .order_by(PlacedStudent.display_order.asc(), PlacedStudent.created_at.asc())
    )
    return list(result.scalars().all())


async def list_all_placed_students(db: AsyncSession) -> List[PlacedStudent]:
    """Returns all placed students sorted by display_order ascending (for admin)."""
    result = await db.execute(
        select(PlacedStudent)
        .order_by(PlacedStudent.display_order.asc(), PlacedStudent.created_at.asc())
    )
    return list(result.scalars().all())


async def get_placed_student(db: AsyncSession, student_id: str) -> PlacedStudent | None:
    result = await db.execute(select(PlacedStudent).where(PlacedStudent.id == student_id))
    return result.scalar_one_or_none()


async def create_placed_student(db: AsyncSession, data: PlacedStudentCreate) -> PlacedStudent:
    # Shift orders to avoid conflicts
    await shift_display_orders(db, data.display_order)
    
    student = PlacedStudent(**data.model_dump())
    db.add(student)
    await db.commit()
    await db.refresh(student)
    return student


async def update_placed_student(db: AsyncSession, student: PlacedStudent, data: PlacedStudentUpdate) -> PlacedStudent:
    update_data = data.model_dump(exclude_none=True)
    
    # If display_order is changing, perform display order shifting
    if "display_order" in update_data and update_data["display_order"] != student.display_order:
        await shift_display_orders(db, update_data["display_order"], exclude_id=student.id)
        
    for field, value in update_data.items():
        setattr(student, field, value)
        
    await db.commit()
    await db.refresh(student)
    return student


async def delete_placed_student(db: AsyncSession, student: PlacedStudent) -> None:
    await db.delete(student)
    await db.commit()
