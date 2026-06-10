from datetime import datetime
from typing import List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
import uuid

from app.models.lead import Lead
from app.models.lead_note import LeadNote
from app.models.lead_timeline import LeadTimelineEvent
from app.schemas.lead import LeadCreate, LeadUpdate


async def add_timeline_event(
    db: AsyncSession,
    lead_id: str,
    event_type: str,
    description: str,
    created_by: Optional[str] = None
) -> LeadTimelineEvent:
    event = LeadTimelineEvent(
        id=str(uuid.uuid4()),
        lead_id=lead_id,
        event_type=event_type,
        description=description,
        created_by=created_by,
        created_at=datetime.utcnow()
    )
    db.add(event)
    await db.flush()
    return event


async def check_duplicate_lead(
    db: AsyncSession,
    phone: Optional[str],
    email: str,
    course: Optional[str]
) -> Optional[Lead]:
    # We look for a lead that is not soft deleted, has matching email OR phone,
    # AND matches the interested course.
    if not course:
        return None
        
    query = select(Lead).where(
        Lead.is_deleted == False,
        Lead.interested_course == course
    )
    
    if phone:
        query = query.where(
            (Lead.email == email) | (Lead.phone == phone)
        )
    else:
        query = query.where(Lead.email == email)
        
    result = await db.execute(query)
    return result.scalars().first()


async def add_lead_note(
    db: AsyncSession,
    lead_id: str,
    content: str,
    created_by: Optional[str] = None
) -> LeadNote:
    note = LeadNote(
        id=str(uuid.uuid4()),
        lead_id=lead_id,
        content=content,
        created_by=created_by,
        created_at=datetime.utcnow()
    )
    db.add(note)
    
    # Also log to timeline
    await add_timeline_event(
        db,
        lead_id=lead_id,
        event_type="Notes Added",
        description=f"Added note: '{content[:60]}...'" if len(content) > 60 else f"Added note: '{content}'",
        created_by=created_by
    )
    
    await db.flush()
    await db.commit()
    return note


async def soft_delete_lead(
    db: AsyncSession,
    lead_id: str,
    user_email: Optional[str] = None
) -> bool:
    query = select(Lead).where(Lead.id == lead_id, Lead.is_deleted == False)
    result = await db.execute(query)
    lead = result.scalars().first()
    if not lead:
        return False
        
    lead.is_deleted = True
    lead.deleted_at = datetime.utcnow()
    lead.deleted_by = user_email
    
    await add_timeline_event(
        db,
        lead_id=lead_id,
        event_type="Deleted",
        description="Lead soft deleted",
        created_by=user_email
    )
    
    await db.commit()
    return True


async def bulk_update_leads(
    db: AsyncSession,
    lead_ids: List[str],
    updates: Dict[str, Any],
    user_email: Optional[str] = None
) -> int:
    query = select(Lead).where(Lead.id.in_(lead_ids), Lead.is_deleted == False)
    result = await db.execute(query)
    leads = result.scalars().all()
    
    updated_count = 0
    for lead in leads:
        changes = []
        if "status" in updates and updates["status"] != lead.status:
            changes.append(f"Status → {updates['status']}")
            lead.status = updates["status"]
            if updates["status"].lower() in ["enrolled", "converted"]:
                await add_timeline_event(db, lead.id, "Converted", f"Lead converted to enrollment via bulk operation", user_email)
            else:
                await add_timeline_event(db, lead.id, "Status Updated", f"Status changed to {updates['status']} via bulk operation", user_email)

        if "priority" in updates and updates["priority"] != lead.priority:
            changes.append(f"Priority → {updates['priority']}")
            lead.priority = updates["priority"]
            await add_timeline_event(db, lead.id, "Priority Changed", f"Priority changed to {updates['priority']} via bulk operation", user_email)

        if "source" in updates and updates["source"] != lead.source:
            changes.append(f"Source → {updates['source']}")
            lead.source = updates["source"]
            await add_timeline_event(db, lead.id, "Status Updated", f"Source updated to {updates['source']} via bulk operation", user_email)

        if "assigned_to" in updates and updates["assigned_to"] != lead.assigned_to:
            changes.append(f"Assigned to → {updates['assigned_to']}")
            lead.assigned_to = updates["assigned_to"]
            await add_timeline_event(db, lead.id, "Lead Assigned", f"Assigned to {updates['assigned_to']} via bulk operation", user_email)

        if changes:
            updated_count += 1
            
    await db.commit()
    return updated_count


async def bulk_delete_leads(
    db: AsyncSession,
    lead_ids: List[str],
    user_email: Optional[str] = None
) -> int:
    query = select(Lead).where(Lead.id.in_(lead_ids), Lead.is_deleted == False)
    result = await db.execute(query)
    leads = result.scalars().all()
    
    deleted_count = 0
    for lead in leads:
        lead.is_deleted = True
        lead.deleted_at = datetime.utcnow()
        lead.deleted_by = user_email
        
        await add_timeline_event(
            db,
            lead_id=lead.id,
            event_type="Deleted",
            description="Lead soft deleted via bulk operation",
            created_by=user_email
        )
        deleted_count += 1
        
    await db.commit()
    return deleted_count


# Re-implementing standard CRUD methods
async def create_lead(db: AsyncSession, data: LeadCreate) -> Lead:
    lead = Lead(
        id=str(uuid.uuid4()),
        name=data.name,
        email=data.email,
        phone=data.phone,
        message=data.goal or data.message,
        interested_course=data.course_interest or data.interested_course,
        source_page=data.course_slug or data.source_page,
        status=data.status or "Pending",
        admin_notes=data.admin_notes,
        last_contacted_at=data.last_contacted_at,
        next_followup_date=data.next_followup_date,
        followup_notes=data.followup_notes,
        source=data.source or "Website",
        priority=data.priority or "Cold",
        assigned_to=data.assigned_to,
        created_at=datetime.utcnow()
    )
    db.add(lead)
    await db.flush()
    
    # Add timeline event
    await add_timeline_event(
        db,
        lead_id=lead.id,
        event_type="Lead Created",
        description=f"Lead registered from source: {lead.source}",
        created_by="System" if lead.source != "Manual Entry" else "Admin"
    )
    
    # Handle initial message/note
    initial_message = data.goal or data.message
    if initial_message:
        await add_lead_note(db, lead.id, initial_message, created_by="System")
    elif data.admin_notes:
        await add_lead_note(db, lead.id, data.admin_notes, created_by="Admin")
        
    await db.commit()
    
    # Reload relationships
    query = select(Lead).where(Lead.id == lead.id).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def list_leads(db: AsyncSession, skip: int = 0, limit: int = 50) -> List[Lead]:
    query = select(Lead).where(
        Lead.is_deleted == False
    ).order_by(
        Lead.created_at.desc()
    ).offset(skip).limit(limit).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def get_lead_by_id(db: AsyncSession, lead_id: str) -> Optional[Lead]:
    query = select(Lead).where(
        Lead.id == lead_id,
        Lead.is_deleted == False
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events)
    )
    result = await db.execute(query)
    return result.scalars().first()


async def update_lead(db: AsyncSession, lead_id: str, data: LeadUpdate) -> Optional[Lead]:
    query = select(Lead).where(
        Lead.id == lead_id,
        Lead.is_deleted == False
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events)
    )
    result = await db.execute(query)
    lead = result.scalars().first()
    if not lead:
        return None
        
    changes = []
    update_data = data.model_dump(exclude_unset=True)
    
    for key, value in update_data.items():
        old_val = getattr(lead, key)
        if old_val != value:
            setattr(lead, key, value)
            if key == "status":
                changes.append(f"Status → {value}")
                if value.lower() in ["enrolled", "converted"]:
                    await add_timeline_event(db, lead.id, "Converted", f"Lead converted to enrollment", "Admin")
                else:
                    await add_timeline_event(db, lead.id, "Status Updated", f"Status changed to {value}", "Admin")
            elif key == "priority":
                changes.append(f"Priority → {value}")
                await add_timeline_event(db, lead.id, "Priority Changed", f"Priority changed to {value}", "Admin")
            elif key == "assigned_to":
                changes.append(f"Assigned to → {value}")
                await add_timeline_event(db, lead.id, "Lead Assigned", f"Assigned to {value}", "Admin")
            elif key == "source":
                changes.append(f"Source → {value}")
                await add_timeline_event(db, lead.id, "Status Updated", f"Source updated to {value}", "Admin")
                
    if changes:
        await db.commit()
        
    return lead


async def list_trash_leads(db: AsyncSession) -> List[Lead]:
    query = select(Lead).where(
        Lead.is_deleted == True
    ).order_by(
        Lead.deleted_at.desc()
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events)
    )
    result = await db.execute(query)
    return result.scalars().all()


async def restore_lead(db: AsyncSession, lead: Lead, user_email: Optional[str] = None) -> Lead:
    lead.is_deleted = False
    lead.deleted_at = None
    lead.deleted_by = None
    
    await add_timeline_event(
        db,
        lead_id=lead.id,
        event_type="Restored",
        description="Lead restored from trash",
        created_by=user_email
    )
    
    await db.commit()
    return lead


async def hard_delete_lead(db: AsyncSession, lead: Lead) -> None:
    await db.delete(lead)
    await db.commit()
