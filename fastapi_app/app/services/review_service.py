from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewUpdate


async def list_active_reviews(db: AsyncSession) -> List[Review]:
    """Returns active reviews with rating >= 4, sorted by rating desc then review length desc.
    Mirrors the filter/sort logic previously living in reviewsService.ts."""
    result = await db.execute(
        select(Review)
        .where(Review.is_active == True, Review.rating >= 4, Review.is_deleted == False)
        .order_by(Review.rating.desc(), Review.is_featured.desc())
    )
    reviews = list(result.scalars().all())
    # Secondary sort by review length (longest first) matches frontend behaviour
    reviews.sort(key=lambda r: (r.rating, r.is_featured, len(r.review)), reverse=True)
    return reviews


async def get_review(db: AsyncSession, review_id: str) -> Review | None:
    result = await db.execute(select(Review).where(Review.id == review_id, Review.is_deleted == False))
    return result.scalar_one_or_none()


async def create_review(db: AsyncSession, data: ReviewCreate) -> Review:
    review = Review(**data.model_dump())
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return review


async def update_review(db: AsyncSession, review: Review, data: ReviewUpdate) -> Review:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(review, field, value)
    await db.commit()
    await db.refresh(review)
    return review


async def delete_review(db: AsyncSession, review: Review, user_email: Optional[str] = None) -> None:
    """Soft delete — sets is_deleted=True."""
    review.is_deleted = True
    review.deleted_at = datetime.utcnow()
    review.deleted_by = user_email
    await db.commit()


async def list_trash_reviews(db: AsyncSession) -> List[Review]:
    result = await db.execute(
        select(Review).where(Review.is_deleted == True).order_by(Review.deleted_at.desc())
    )
    return list(result.scalars().all())


async def restore_review(db: AsyncSession, review: Review) -> Review:
    review.is_deleted = False
    review.deleted_at = None
    review.deleted_by = None
    await db.commit()
    return review


async def hard_delete_review(db: AsyncSession, review: Review) -> None:
    await db.delete(review)
    await db.commit()
