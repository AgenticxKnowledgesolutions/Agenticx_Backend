from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from app.models.activity import Activity
from app.schemas.activity import ActivityCreate, ActivityUpdate


async def list_activities(db: AsyncSession) -> List[Activity]:
    result = await db.execute(
        select(Activity).where(Activity.is_active == True).order_by(Activity.created_at.desc())
    )
    return list(result.scalars().all())


async def get_activity(db: AsyncSession, activity_id: str) -> Activity | None:
    result = await db.execute(select(Activity).where(Activity.id == activity_id))
    return result.scalar_one_or_none()


async def create_activity(db: AsyncSession, data: ActivityCreate) -> Activity:
    activity = Activity(**data.model_dump())
    db.add(activity)
    await db.commit()
    await db.refresh(activity)
    return activity


async def update_activity(db: AsyncSession, activity: Activity, data: ActivityUpdate) -> Activity:
    for field, value in data.model_dump(exclude_none=True).items():
        setattr(activity, field, value)
    await db.commit()
    await db.refresh(activity)
    return activity


async def delete_activity(db: AsyncSession, activity: Activity) -> None:
    activity.is_active = False
    await db.commit()
