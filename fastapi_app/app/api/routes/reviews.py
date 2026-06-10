from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.review import ReviewCreate, ReviewUpdate, ReviewResponse
from app.services import review_service
from app.deps import require_admin
from app.models.user import User
from app.models.review import Review

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/", response_model=List[ReviewResponse])
async def list_reviews(db: AsyncSession = Depends(get_db)):
    """Public: active reviews >= 4 stars, sorted by rating + length."""
    return await review_service.list_active_reviews(db)


@router.get("/trash", response_model=List[ReviewResponse])
async def list_trash_reviews(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await review_service.list_trash_reviews(db)


@router.post("/", response_model=ReviewResponse, status_code=status.HTTP_201_CREATED)
async def create_review(
    data: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await review_service.create_review(db, data)


@router.put("/{review_id}", response_model=ReviewResponse)
async def update_review(
    review_id: str,
    data: ReviewUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    review = await review_service.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return await review_service.update_review(db, review, data)


@router.delete("/{review_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    review = await review_service.get_review(db, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    await review_service.delete_review(db, review, current_user.email)


@router.post("/{review_id}/restore", response_model=ReviewResponse)
async def restore_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return await review_service.restore_review(db, review)


@router.delete("/{review_id}/hard-delete", status_code=status.HTTP_200_OK)
async def hard_delete_review(
    review_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    review = await db.get(Review, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    await review_service.hard_delete_review(db, review)
    return {"detail": "Review permanently deleted"}
