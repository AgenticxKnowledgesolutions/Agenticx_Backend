from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.placed_student import (
    PlacedStudentCreate,
    PlacedStudentUpdate,
    PlacedStudentResponse,
    PlacedStudentPublicResponse,
)
from app.services import placed_student_service
from app.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/placed-students", tags=["placed-students"])
admin_router = APIRouter(prefix="/admin/placed-students", tags=["admin-placed-students"])


@router.get("/", response_model=List[PlacedStudentPublicResponse])
async def list_active_placed_students(db: AsyncSession = Depends(get_db)):
    """Public: Returns active placed students sorted by display_order."""
    return await placed_student_service.list_active_placed_students(db)


@admin_router.get("/", response_model=List[PlacedStudentResponse])
async def list_admin_placed_students(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: List all placed students."""
    return await placed_student_service.list_all_placed_students(db)


@admin_router.post("/", response_model=PlacedStudentResponse, status_code=status.HTTP_201_CREATED)
async def create_placed_student(
    data: PlacedStudentCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: Create placed student."""
    return await placed_student_service.create_placed_student(db, data)


@admin_router.put("/{student_id}", response_model=PlacedStudentResponse)
async def update_placed_student(
    student_id: str,
    data: PlacedStudentUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: Update placed student."""
    student = await placed_student_service.get_placed_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Placed student not found")
    return await placed_student_service.update_placed_student(db, student, data)


@admin_router.delete("/{student_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_placed_student(
    student_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: Delete placed student."""
    student = await placed_student_service.get_placed_student(db, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Placed student not found")
    await placed_student_service.delete_placed_student(db, student)
