from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List
from app.core.database import get_db
from app.schemas.collaborator import (
    CollaboratorCreate,
    CollaboratorUpdate,
    CollaboratorResponse,
    CollaboratorPublicResponse,
)
from app.services import collaborator_service
from app.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/collaborators", tags=["collaborators"])
admin_router = APIRouter(prefix="/admin/collaborators", tags=["admin-collaborators"])


@router.get("/", response_model=List[CollaboratorPublicResponse])
async def list_active_collaborators(db: AsyncSession = Depends(get_db)):
    """Public: Returns active collaborators sorted by display_order."""
    return await collaborator_service.list_active_collaborators(db)


@admin_router.get("/", response_model=List[CollaboratorResponse])
async def list_admin_collaborators(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: List all collaborators."""
    return await collaborator_service.list_all_collaborators(db)


@admin_router.post("/", response_model=CollaboratorResponse, status_code=status.HTTP_201_CREATED)
async def create_collaborator(
    data: CollaboratorCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: Create collaborator."""
    return await collaborator_service.create_collaborator(db, data)


@admin_router.put("/{collaborator_id}", response_model=CollaboratorResponse)
async def update_collaborator(
    collaborator_id: str,
    data: CollaboratorUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: Update collaborator."""
    collaborator = await collaborator_service.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    return await collaborator_service.update_collaborator(db, collaborator, data)


@admin_router.delete("/{collaborator_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_collaborator(
    collaborator_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """Admin: Delete collaborator."""
    collaborator = await collaborator_service.get_collaborator(db, collaborator_id)
    if not collaborator:
        raise HTTPException(status_code=404, detail="Collaborator not found")
    await collaborator_service.delete_collaborator(db, collaborator)
