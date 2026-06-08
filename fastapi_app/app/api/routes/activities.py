from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.activity import ActivityCreate, ActivityUpdate, ActivityResponse
from app.services import activity_service
from app.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/activities", tags=["activities"])


@router.get("/", response_model=List[ActivityResponse])
async def list_activities(db: AsyncSession = Depends(get_db)):
    return await activity_service.list_activities(db)


@router.post("/", response_model=ActivityResponse, status_code=status.HTTP_201_CREATED)
async def create_activity(
    data: ActivityCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await activity_service.create_activity(db, data)


@router.put("/{activity_id}", response_model=ActivityResponse)
async def update_activity(
    activity_id: str,
    data: ActivityUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    activity = await activity_service.get_activity(db, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    return await activity_service.update_activity(db, activity, data)


@router.delete("/{activity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_activity(
    activity_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    activity = await activity_service.get_activity(db, activity_id)
    if not activity:
        raise HTTPException(status_code=404, detail="Activity not found")
    await activity_service.delete_activity(db, activity)
