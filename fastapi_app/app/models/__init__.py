# Models package — import all so alembic autogenerates every table
from app.models.base import Base
from app.models.user import User, UserRole
from app.models.review import Review, ReviewSource
from app.models.activity import Activity, ActivityType
from app.models.course import Course, TechStack, CurriculumMonth, CurriculumModule, CourseMode, CourseDifficulty
from app.models.lead import Lead
from app.models.lead_note import LeadNote
from app.models.lead_timeline import LeadTimelineEvent
from app.models.lead_interaction import LeadInteraction
from app.models.lead_token import LeadToken
from app.models.company_settings import CompanySettings
from app.models.candidate_application import CandidateImportBatch, CandidateApplication, CandidateNote, CandidateTimelineEvent
from app.models.admin_notification import AdminNotification

__all__ = [
    "Base",
    "User", "UserRole",
    "Review", "ReviewSource",
    "Activity", "ActivityType",
    "Course", "TechStack", "CurriculumMonth", "CurriculumModule", "CourseMode", "CourseDifficulty",
    "Lead",
    "LeadNote",
    "LeadTimelineEvent",
    "LeadInteraction",
    "LeadToken",
    "CompanySettings",
    "CandidateImportBatch",
    "CandidateApplication",
    "CandidateNote",
    "CandidateTimelineEvent",
    "AdminNotification"
]

