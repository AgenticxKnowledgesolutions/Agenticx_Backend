import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_, and_, func
from sqlalchemy.orm import selectinload

from pydantic import BaseModel
from urllib.parse import urlencode
from app.services.email_service import EmailService
from app.core.config import settings
from app.models.lead import Lead
from app.models.lead_note import LeadNote
from app.models.lead_timeline import LeadTimelineEvent
from app.models.lead_interaction import LeadInteraction
from app.schemas.lead import LeadCreate, LeadUpdate

# Setup crm_audit_logger
audit_logger = logging.getLogger("crm_audit_logger")
audit_logger.setLevel(logging.INFO)
if not audit_logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))
    audit_logger.addHandler(ch)

def log_crm_audit_event(event_type: str, lead_id: str, source: str, ip: str):
    timestamp = datetime.now(timezone.utc).isoformat()
    audit_logger.info(f"{timestamp} {lead_id} {source} {ip} {event_type}")

def normalize_source(src: str | None) -> str:
    if not src:
        return "Unknown"
    s = src.strip().lower()
    if "home" in s:
        return "Home Page"
    if "courses" in s and "detail" not in s:
        return "Courses Page"
    if "detail" in s or "enquiry" in s:
        return "Course Detail Page"
    if "contact" in s:
        return "Contact Page"
    if "demo" in s:
        return "Demo Request"
    if "footer" in s:
        return "Footer Form"
    if "admin" in s or "manual" in s:
        return "Admin Manual Entry"
    if "whatsapp" in s:
        return "WhatsApp"
    return src

def calculate_score(lead: Lead, interactions: List[LeadInteraction], notes_count: int) -> int:
    score = 10  # first submission
    score += (lead.duplicate_hits or 0) * 5
    
    has_demo = False
    has_enquiry = False
    for inter in interactions:
        t = inter.interaction_type.lower()
        if "demo" in t:
            has_demo = True
        if "enquiry" in t or "course" in t or "contact" in t:
            has_enquiry = True
            
    lead_source = (lead.source or "").lower()
    if "demo" in lead_source:
        has_demo = True
    if "enquiry" in lead_source or "contact" in lead_source:
        has_enquiry = True
        
    if has_demo:
        score += 10
    if has_enquiry:
        score += 15
        
    merged = lead.merged_courses or []
    if len(merged) > 1:
        score += 20
        
    if notes_count > 0 or lead.admin_notes:
        score += 25
        
    return score

async def find_duplicate_lead(db: AsyncSession, data: LeadCreate) -> Optional[Lead]:
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    conditions = [Lead.email.ilike(data.email)]
    if data.phone:
        conditions.append(Lead.phone == data.phone)
        conditions.append(
            and_(
                func.lower(Lead.name) == func.lower(data.name),
                Lead.phone == data.phone,
                Lead.created_at >= thirty_days_ago
            )
        )
        
    query = select(Lead).where(
        Lead.is_deleted == False,
        or_(*conditions)
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events),
        selectinload(Lead.interactions)
    )
    
    result = await db.execute(query)
    candidates = result.scalars().all()
    
    # Priority 1: Exact Match (Email OR Phone)
    for c in candidates:
        if c.email.lower() == data.email.lower():
            return c
        if data.phone and c.phone:
            p1 = "".join(filter(str.isdigit, data.phone))
            p2 = "".join(filter(str.isdigit, c.phone))
            if p1 and p2 and p1 == p2:
                return c
                
    # Priority 2: Strong Match (Same phone AND same interested course)
    if data.phone:
        p1 = "".join(filter(str.isdigit, data.phone))
        course_interest = data.course_interest or data.interested_course
        for c in candidates:
            if c.phone and course_interest:
                p2 = "".join(filter(str.isdigit, c.phone))
                c_course = c.interested_course
                if p1 == p2 and c_course and course_interest.lower() == c_course.lower():
                    return c
                    
    # Priority 3: Soft Match (Same email AND same interested course)
    course_interest = data.course_interest or data.interested_course
    if course_interest:
        for c in candidates:
            if c.email.lower() == data.email.lower() and c.interested_course:
                if course_interest.lower() == c.interested_course.lower():
                    return c
                    
    # Priority 4: Near Duplicate (Same name case-insensitive AND same phone AND created in last 30 days)
    if data.phone:
        p1 = "".join(filter(str.isdigit, data.phone))
        for c in candidates:
            if c.phone and c.name.strip().lower() == data.name.strip().lower():
                p2 = "".join(filter(str.isdigit, c.phone))
                if p1 == p2 and c.created_at >= thirty_days_ago:
                    return c
                    
    return None

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

async def send_lead_qualification_email(db: AsyncSession, lead: Lead):
    params = {
        "lead_id": lead.id,
        "name": lead.name,
        "email": lead.email
    }
    if lead.phone:
        params["phone"] = lead.phone
    if lead.interested_course:
        params["course"] = lead.interested_course
        
    frontend_url = settings.FRONTEND_URL or "http://localhost:5173"
    apply_url = f"{frontend_url.rstrip('/')}/apply?{urlencode(params)}"
    
    # Backend email sending for admission link is disabled (handled exclusively by frontend EmailJS)
    logger = logging.getLogger("app.services.lead_service")
    logger.info(f"Skipping backend email for qualified lead {lead.id}. Handled by frontend EmailJS.")
    
    # Log timeline event
    description = f"Lead qualified. Candidate admission form link ready: {apply_url} (Email sending is handled by frontend EmailJS)"
    await add_timeline_event(db, lead.id, "Qualified", description, "System")

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
            new_status = updates["status"]
            if new_status == "Converted" and lead.status != "Qualified":
                raise ValueError("Only qualified leads can be converted.")
            changes.append(f"Status → {new_status}")
            lead.status = new_status
            if new_status.lower() in ["enrolled", "converted"]:
                await add_timeline_event(db, lead.id, "Converted", f"Lead converted to enrollment via bulk operation", user_email)
            elif new_status.lower() == "qualified":
                await add_timeline_event(db, lead.id, "Status Updated", f"Status changed to {new_status} via bulk operation", user_email)
                await send_lead_qualification_email(db, lead)
            else:
                await add_timeline_event(db, lead.id, "Status Updated", f"Status changed to {new_status} via bulk operation", user_email)

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

async def create_lead(db: AsyncSession, data: LeadCreate, client_ip: str = "127.0.0.1") -> Any:
    source_name = normalize_source(data.source or "Website")
    course_name = data.course_interest or data.interested_course or "General Inquiry"
    ip = client_ip
    
    existing_lead = await find_duplicate_lead(db, data)
    
    if existing_lead:
        existing_lead.interaction_count += 1
        existing_lead.duplicate_hits += 1
        existing_lead.last_interaction_at = datetime.utcnow()
        
        if source_name and source_name != existing_lead.latest_source:
            existing_lead.latest_source = source_name
            
        courses_list = existing_lead.merged_courses or []
        if not isinstance(courses_list, list):
            courses_list = [existing_lead.interested_course] if existing_lead.interested_course else []
        if course_name and course_name not in courses_list:
            courses_list.append(course_name)
        existing_lead.merged_courses = courses_list
        
        interaction_type = "Course Enquiry"
        if "demo" in source_name.lower():
            interaction_type = "Demo Request"
        elif "contact" in source_name.lower():
            interaction_type = "Contact Form"
        elif "detail" in source_name.lower():
            interaction_type = "Course Detail Enquiry"
        elif "home" in source_name.lower():
            interaction_type = "Home Form Submission"
            
        interaction = LeadInteraction(
            id=str(uuid.uuid4()),
            lead_id=existing_lead.id,
            interaction_type=interaction_type,
            source=source_name,
            course=course_name,
            notes=data.goal or data.message,
            ip_address=ip,
            created_at=datetime.utcnow()
        )
        db.add(interaction)
        await db.flush()
        
        await add_timeline_event(
            db,
            lead_id=existing_lead.id,
            event_type="Lead Duplicate Detected",
            description=f"Duplicate submission detected from source: {source_name}. Total interactions: {existing_lead.interaction_count}.",
            created_by="System"
        )
        
        q_inters = select(LeadInteraction).where(LeadInteraction.lead_id == existing_lead.id)
        res_inters = await db.execute(q_inters)
        all_inters = res_inters.scalars().all()
        
        existing_lead.lead_score = calculate_score(existing_lead, all_inters, len(existing_lead.notes))
        
        await db.commit()
        log_crm_audit_event("LEAD_DUPLICATE_DETECTED", existing_lead.id, source_name, ip)
        
        return {
            "success": True,
            "duplicate_detected": True,
            "lead_id": existing_lead.id,
            "message": "Existing lead updated."
        }
    else:
        lead = Lead(
            id=str(uuid.uuid4()),
            name=data.name,
            email=data.email,
            phone=data.phone,
            message=data.goal or data.message,
            interested_course=course_name,
            source_page=data.course_slug or data.source_page,
            status=data.status or "Pending",
            admin_notes=data.admin_notes,
            last_contacted_at=data.last_contacted_at,
            next_followup_date=data.next_followup_date,
            followup_notes=data.followup_notes,
            source=source_name,
            priority=data.priority or "Cold",
            assigned_to=data.assigned_to,
            
            interaction_count=1,
            last_interaction_at=datetime.utcnow(),
            first_source=source_name,
            latest_source=source_name,
            merged_courses=[course_name] if course_name else [],
            duplicate_hits=0,
            lead_score=10,
            created_at=datetime.utcnow()
        )
        db.add(lead)
        await db.flush()
        
        interaction_type = "Course Enquiry"
        if "demo" in source_name.lower():
            interaction_type = "Demo Request"
        elif "contact" in source_name.lower():
            interaction_type = "Contact Form"
        elif "detail" in source_name.lower():
            interaction_type = "Course Detail Enquiry"
        elif "home" in source_name.lower():
            interaction_type = "Home Form Submission"
            
        interaction = LeadInteraction(
            id=str(uuid.uuid4()),
            lead_id=lead.id,
            interaction_type=interaction_type,
            source=source_name,
            course=course_name,
            notes=data.goal or data.message,
            ip_address=ip,
            created_at=datetime.utcnow()
        )
        db.add(interaction)
        await db.flush()
        
        await add_timeline_event(
            db,
            lead_id=lead.id,
            event_type="Lead Created",
            description=f"Lead registered from source: {source_name}",
            created_by="System" if source_name != "Admin Manual Entry" else "Admin"
        )
        
        initial_message = data.goal or data.message
        notes_count = 0
        if initial_message:
            await add_lead_note(db, lead.id, initial_message, created_by="System")
            notes_count += 1
        elif data.admin_notes:
            await add_lead_note(db, lead.id, data.admin_notes, created_by="Admin")
            notes_count += 1
            
        lead.lead_score = calculate_score(lead, [interaction], notes_count)
        
        await db.commit()
        log_crm_audit_event("LEAD_CREATED", lead.id, source_name, ip)
        
        query = select(Lead).where(Lead.id == lead.id).options(
            selectinload(Lead.notes),
            selectinload(Lead.timeline_events),
            selectinload(Lead.interactions)
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
        selectinload(Lead.timeline_events),
        selectinload(Lead.interactions)
    )
    result = await db.execute(query)
    return result.scalars().all()

async def get_lead_by_id(db: AsyncSession, lead_id: str) -> Optional[Lead]:
    query = select(Lead).where(
        Lead.id == lead_id,
        Lead.is_deleted == False
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events),
        selectinload(Lead.interactions)
    )
    result = await db.execute(query)
    return result.scalars().first()

async def update_lead(db: AsyncSession, lead_id: str, data: LeadUpdate) -> Optional[Lead]:
    query = select(Lead).where(
        Lead.id == lead_id,
        Lead.is_deleted == False
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events),
        selectinload(Lead.interactions)
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
                if value == "Converted" and lead.status != "Qualified":
                    raise ValueError("Only qualified leads can be converted.")
                changes.append(f"Status → {value}")
                if value.lower() in ["enrolled", "converted"]:
                    await add_timeline_event(db, lead.id, "Converted", f"Lead converted to enrollment", "Admin")
                elif value.lower() == "qualified":
                    await add_timeline_event(db, lead.id, "Status Updated", f"Status changed to {value}", "Admin")
                    await send_lead_qualification_email(db, lead)
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
        q_inters = select(LeadInteraction).where(LeadInteraction.lead_id == lead.id)
        res_inters = await db.execute(q_inters)
        all_inters = res_inters.scalars().all()
        lead.lead_score = calculate_score(lead, all_inters, len(lead.notes))
        await db.commit()
        
    return lead

async def list_trash_leads(db: AsyncSession) -> List[Lead]:
    query = select(Lead).where(
        Lead.is_deleted == True
    ).order_by(
        Lead.deleted_at.desc()
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events),
        selectinload(Lead.interactions)
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

async def merge_leads(db: AsyncSession, master_id: str, duplicate_ids: List[str], user_email: Optional[str] = "Admin") -> Lead:
    query = select(Lead).where(
        Lead.id == master_id,
        Lead.is_deleted == False
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events),
        selectinload(Lead.interactions)
    )
    result = await db.execute(query)
    master_lead = result.scalars().first()
    if not master_lead:
        raise ValueError(f"Master lead with ID {master_id} not found.")
        
    query_dups = select(Lead).where(
        Lead.id.in_(duplicate_ids),
        Lead.is_deleted == False
    ).options(
        selectinload(Lead.notes),
        selectinload(Lead.timeline_events),
        selectinload(Lead.interactions)
    )
    res_dups = await db.execute(query_dups)
    duplicates = res_dups.scalars().all()
    
    total_new_hits = len(duplicates)
    merged_courses_set = set(master_lead.merged_courses or [])
    if master_lead.interested_course:
        merged_courses_set.add(master_lead.interested_course)
        
    for dup in duplicates:
        for note in dup.notes:
            note.lead_id = master_id
            
        for evt in dup.timeline_events:
            evt.lead_id = master_id
            
        for inter in dup.interactions:
            inter.lead_id = master_id
            
        if dup.merged_courses:
            merged_courses_set.update(dup.merged_courses)
        elif dup.interested_course:
            merged_courses_set.add(dup.interested_course)
            
        total_new_hits += dup.duplicate_hits
        
        dup.is_deleted = True
        dup.deleted_at = datetime.utcnow()
        dup.deleted_by = user_email
        
        await add_timeline_event(
            db,
            lead_id=dup.id,
            event_type="Lead Merged",
            description=f"This lead was merged into Master Lead (ID: {master_id})",
            created_by=user_email
        )
        
    master_lead.duplicate_hits += total_new_hits
    master_lead.merged_courses = list(merged_courses_set)
    
    q_all_inters = select(LeadInteraction).where(LeadInteraction.lead_id == master_id)
    res_all_inters = await db.execute(q_all_inters)
    all_interactions = res_all_inters.scalars().all()
    master_lead.interaction_count = len(all_interactions)
    
    if all_interactions:
        master_lead.last_interaction_at = max(inter.created_at for inter in all_interactions)
        
    master_lead.lead_score = calculate_score(master_lead, all_interactions, len(master_lead.notes))
    
    await add_timeline_event(
        db,
        lead_id=master_id,
        event_type="Lead Merged",
        description=f"Merged {len(duplicates)} duplicate lead(s) into this record manually.",
        created_by=user_email
    )
    
    await db.commit()
    log_crm_audit_event("LEAD_MERGED", master_lead.id, master_lead.latest_source or "System", "0.0.0.0")
    
    return master_lead
