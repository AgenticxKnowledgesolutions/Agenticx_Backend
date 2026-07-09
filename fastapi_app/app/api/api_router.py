from fastapi import APIRouter
from app.api.routes import auth, reviews, activities, courses, leads, uploads, company_settings, dashboard, reports, health, candidates, jobs, applications, certificates, programs, collaborators, placed_students

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(auth.router)
api_router.include_router(reviews.router)
api_router.include_router(activities.router)
api_router.include_router(courses.router)
api_router.include_router(leads.router)
api_router.include_router(uploads.router)
api_router.include_router(company_settings.router)
api_router.include_router(dashboard.router)
api_router.include_router(reports.router)
api_router.include_router(health.router)
api_router.include_router(candidates.router)
api_router.include_router(candidates.webhook_router)
api_router.include_router(jobs.router)
api_router.include_router(applications.router)
api_router.include_router(certificates.router)
api_router.include_router(programs.router)
api_router.include_router(collaborators.router)
api_router.include_router(collaborators.admin_router)
api_router.include_router(placed_students.router)
api_router.include_router(placed_students.admin_router)


