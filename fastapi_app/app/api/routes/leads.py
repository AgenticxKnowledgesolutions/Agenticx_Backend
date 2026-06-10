from fastapi import APIRouter, Depends, status, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional

from app.core.database import get_db
from app.schemas.lead import (
    LeadCreate, LeadResponse, LeadUpdate, 
    DuplicateCheckRequest, BulkUpdatePayload, BulkDeletePayload,
    LeadNoteCreate, LeadNoteResponse, LeadTimelineResponse
)
from app.services import lead_service
from app.deps import require_admin
from app.models.user import User
from app.models.lead import Lead
from app.core.limiter import limiter

router = APIRouter(prefix="/leads", tags=["leads"])


@router.post("/", response_model=LeadResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/15 minutes;20/day")
async def submit_lead(request: Request, data: LeadCreate, db: AsyncSession = Depends(get_db)):
    """Public: anyone can submit a contact/enquiry form."""
    return await lead_service.create_lead(db, data)


@router.post("/check-duplicate", response_model=Optional[LeadResponse])
async def check_duplicate_lead(
    data: DuplicateCheckRequest,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: check if a lead with matching email/phone and course already exists."""
    dup = await lead_service.check_duplicate_lead(
        db, phone=data.phone, email=data.email, course=data.interested_course
    )
    return dup


@router.get("/", response_model=List[LeadResponse])
async def list_leads(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await lead_service.list_leads(db, skip=skip, limit=limit)


@router.get("/trash", response_model=List[LeadResponse])
async def list_trash_leads(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    return await lead_service.list_trash_leads(db)


@router.get("/{lead_id}", response_model=LeadResponse)
async def get_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead


@router.put("/{lead_id}", response_model=LeadResponse)
async def update_lead(
    lead_id: str,
    data: LeadUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    updated = await lead_service.update_lead(db, lead_id, data)
    if not updated:
        raise HTTPException(status_code=404, detail="Lead not found")
    return updated


@router.delete("/{lead_id}", status_code=status.HTTP_200_OK)
async def delete_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    success = await lead_service.soft_delete_lead(db, lead_id, current_user.email)
    if not success:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"detail": "Lead deleted successfully"}


@router.post("/bulk-update", status_code=status.HTTP_200_OK)
async def bulk_update_leads(
    payload: BulkUpdatePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    count = await lead_service.bulk_update_leads(
        db, lead_ids=payload.ids, updates=payload.updates, user_email=current_user.email
    )
    return {"detail": f"Successfully updated {count} leads"}


@router.post("/bulk-delete", status_code=status.HTTP_200_OK)
async def bulk_delete_leads(
    payload: BulkDeletePayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    count = await lead_service.bulk_delete_leads(
        db, lead_ids=payload.ids, user_email=current_user.email
    )
    return {"detail": f"Successfully deleted {count} leads"}


@router.post("/{lead_id}/notes", response_model=LeadNoteResponse, status_code=status.HTTP_201_CREATED)
async def add_note(
    lead_id: str,
    payload: LeadNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await lead_service.add_lead_note(
        db, lead_id=lead_id, content=payload.content, created_by=current_user.email
    )


@router.get("/{lead_id}/timeline", response_model=List[LeadTimelineResponse])
async def get_timeline(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    lead = await lead_service.get_lead_by_id(db, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return lead.timeline_events


@router.post("/{lead_id}/restore", response_model=LeadResponse)
async def restore_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return await lead_service.restore_lead(db, lead, current_user.email)


@router.delete("/{lead_id}/hard-delete", status_code=status.HTTP_200_OK)
async def hard_delete_lead(
    lead_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    lead = await db.get(Lead, lead_id)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    await lead_service.hard_delete_lead(db, lead)
    return {"detail": "Lead permanently deleted"}
