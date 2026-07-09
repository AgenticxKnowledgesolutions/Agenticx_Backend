from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Optional
from app.models.collaborator import Collaborator
from app.schemas.collaborator import CollaboratorCreate, CollaboratorUpdate


async def shift_display_orders(db: AsyncSession, target_order: int, exclude_id: Optional[str] = None) -> None:
    """Increment display_order of all collaborators with display_order >= target_order by 1."""
    stmt = (
        update(Collaborator)
        .where(Collaborator.display_order >= target_order)
    )
    if exclude_id:
        stmt = stmt.where(Collaborator.id != exclude_id)
        
    stmt = stmt.values(display_order=Collaborator.display_order + 1)
    await db.execute(stmt)


async def list_active_collaborators(db: AsyncSession) -> List[Collaborator]:
    """Returns active collaborators sorted by display_order ascending."""
    result = await db.execute(
        select(Collaborator)
        .where(Collaborator.is_active == True)
        .order_by(Collaborator.display_order.asc(), Collaborator.created_at.asc())
    )
    return list(result.scalars().all())


async def list_all_collaborators(db: AsyncSession) -> List[Collaborator]:
    """Returns all collaborators sorted by display_order ascending (for admin)."""
    result = await db.execute(
        select(Collaborator)
        .order_by(Collaborator.display_order.asc(), Collaborator.created_at.asc())
    )
    return list(result.scalars().all())


async def get_collaborator(db: AsyncSession, collaborator_id: str) -> Collaborator | None:
    result = await db.execute(select(Collaborator).where(Collaborator.id == collaborator_id))
    return result.scalar_one_or_none()


async def create_collaborator(db: AsyncSession, data: CollaboratorCreate) -> Collaborator:
    # Shift orders to avoid conflicts
    await shift_display_orders(db, data.display_order)
    
    collaborator = Collaborator(**data.model_dump())
    db.add(collaborator)
    await db.commit()
    await db.refresh(collaborator)
    return collaborator


async def update_collaborator(db: AsyncSession, collaborator: Collaborator, data: CollaboratorUpdate) -> Collaborator:
    update_data = data.model_dump(exclude_none=True)
    
    # If display_order is changing, perform display order shifting
    if "display_order" in update_data and update_data["display_order"] != collaborator.display_order:
        await shift_display_orders(db, update_data["display_order"], exclude_id=collaborator.id)
        
    for field, value in update_data.items():
        setattr(collaborator, field, value)
        
    await db.commit()
    await db.refresh(collaborator)
    return collaborator


async def delete_collaborator(db: AsyncSession, collaborator: Collaborator) -> None:
    await db.delete(collaborator)
    await db.commit()
