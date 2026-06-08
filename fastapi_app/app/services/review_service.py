from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.models.review import Review
from app.schemas.review import ReviewCreate, ReviewUpdate


async def list_active_reviews(db: AsyncSession) -> List[Review]:
    """Returns active reviews with rating >= 4, sorted by rating desc then review length desc.
    Mirrors the filter/sort logic previously living in reviewsService.ts."""
    result = await db.execute(
        select(Review)
        .where(Review.is_active == True, Review.rating >= 4)
        .order_by(Review.rating.desc(), Review.is_featured.desc())
    )
    reviews = list(result.scalars().all())
    # Secondary sort by review length (longest first) matches frontend behaviour
    reviews.sort(key=lambda r: (r.rating, r.is_featured, len(r.review)), reverse=True)
    return reviews


async def get_review(db: AsyncSession, review_id: str) -> Review | None:
    result = await db.execute(select(Review).where(Review.id == review_id))
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


async def delete_review(db: AsyncSession, review: Review) -> None:
    """Soft delete — sets is_active=False."""
    review.is_active = False
    await db.commit()
