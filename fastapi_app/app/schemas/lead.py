from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime


class LeadNoteCreate(BaseModel):
    content: str


class LeadNoteResponse(BaseModel):
    id: str
    lead_id: str
    content: str
    created_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadTimelineResponse(BaseModel):
    id: str
    lead_id: str
    event_type: str
    description: str
    created_by: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LeadCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    message: Optional[str] = None
    interested_course: Optional[str] = None
    source_page: Optional[str] = None
    status: Optional[str] = "Pending"
    admin_notes: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    next_followup_date: Optional[datetime] = None
    followup_notes: Optional[str] = None
    source: Optional[str] = "Website"
    priority: Optional[str] = "Cold"
    assigned_to: Optional[str] = None
    
    # New fields for frontend form submissions (backward compatible)
    course_interest: Optional[str] = None
    course_slug: Optional[str] = None
    goal: Optional[str] = None



class LeadUpdate(BaseModel):
    status: Optional[str] = None
    admin_notes: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    next_followup_date: Optional[datetime] = None
    followup_notes: Optional[str] = None
    source: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[str] = None


class LeadResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str] = None
    message: Optional[str] = None
    interested_course: Optional[str] = None
    source_page: Optional[str] = None
    status: str
    admin_notes: Optional[str] = None
    last_contacted_at: Optional[datetime] = None
    next_followup_date: Optional[datetime] = None
    followup_notes: Optional[str] = None
    source: Optional[str] = None
    priority: str
    assigned_to: Optional[str] = None
    created_at: datetime
    
    notes: List[LeadNoteResponse] = []
    timeline_events: List[LeadTimelineResponse] = []

    model_config = {"from_attributes": True}


class DuplicateCheckRequest(BaseModel):
    phone: Optional[str] = None
    email: str
    interested_course: Optional[str] = None


class BulkUpdatePayload(BaseModel):
    ids: List[str]
    updates: Dict[str, Any]


class BulkDeletePayload(BaseModel):
    ids: List[str]
