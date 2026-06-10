from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.course import CourseCreate, CourseUpdate, CourseResponse
from app.services import course_service
from app.deps import require_admin
from app.models.user import User
from app.models.course import Course

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("/", response_model=List[CourseResponse])
async def list_courses(db: AsyncSession = Depends(get_db)):
    return await course_service.list_courses(db)


@router.get("/trash", response_model=List[CourseResponse])
async def list_trash_courses(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await course_service.list_trash_courses(db)


@router.get("/{slug}", response_model=CourseResponse)
async def get_course(slug: str, db: AsyncSession = Depends(get_db)):
    course = await course_service.get_course_by_slug(db, slug)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return course


@router.post("/", response_model=CourseResponse, status_code=status.HTTP_201_CREATED)
async def create_course(
    data: CourseCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await course_service.create_course(db, data)


@router.put("/{course_id}", response_model=CourseResponse)
async def update_course(
    course_id: str,
    data: CourseUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    course = await course_service.get_course_orm(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return await course_service.update_course(db, course, data)


@router.delete("/{course_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    course = await course_service.get_course_orm(db, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    await course_service.delete_course(db, course, current_user.email)


@router.post("/{course_id}/restore", response_model=CourseResponse)
async def restore_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    return await course_service.restore_course(db, course)


@router.delete("/{course_id}/hard-delete", status_code=status.HTTP_200_OK)
async def hard_delete_course(
    course_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    course = await db.get(Course, course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")
    await course_service.hard_delete_course(db, course)
    return {"detail": "Course permanently deleted"}
