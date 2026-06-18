from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from app.core.database import get_db
from app.models.job import Job, JobApplication
from app.services.upload_service import upload_service
from app.schemas.job import JobApplicationAdminResponse
from app.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/applications", tags=["applications"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def submit_job_application(
    job_id: str = Form(...),
    name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    resume: UploadFile = File(...),
    db: AsyncSession = Depends(get_db)
):
    """
    Public multipart-form endpoint for job application submission.
    """
    # 1. Verify job exists and is active
    job = await db.get(Job, job_id)
    if not job or not job.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job position not found or is no longer active."
        )

    # 2. Validate resume file extension (PDF only)
    filename = resume.filename or ""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    if ext != "pdf" or resume.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported file format. Only PDF files are allowed."
        )

    # 3. Read content & validate size (max 5MB)
    content = await resume.read()
    max_size = 5 * 1024 * 1024  # 5 MB
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds the 5MB maximum limit."
        )

    # 4. Perform upload using upload_service
    try:
        resume_url = await upload_service.upload_file(
            file_content=content,
            folder="careers/resumes",
            original_filename=filename,
            mime_type="application/pdf"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload resume document: {str(e)}"
        )

    # 5. Insert JobApplication to database matching exact schema
    application = JobApplication(
        job_id=job_id,
        name=name,
        email=email,
        phone=phone,
        resume_url=resume_url,
        status="new",
        is_deleted=False
    )
    db.add(application)
    await db.commit()
    await db.refresh(application)

    return {
        "success": True,
        "detail": "Application submitted successfully.",
        "application_id": application.id,
        "resume_url": resume_url
    }


@router.get("/admin", response_model=List[JobApplicationAdminResponse])
async def list_admin_applications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to fetch job applications where is_deleted == False.
    """
    # Select applications joined with jobs
    result = await db.execute(
        select(JobApplication)
        .where(JobApplication.is_deleted == False)
        .options(selectinload(JobApplication.job))
        .order_by(JobApplication.created_at.desc())
    )
    applications = result.scalars().all()

    # Build response with job_title field
    response_list = []
    for app in applications:
        response_list.append(
            JobApplicationAdminResponse(
                id=app.id,
                job_id=app.job_id,
                name=app.name,
                email=app.email,
                phone=app.phone,
                resume_url=app.resume_url,
                status=app.status,
                is_deleted=app.is_deleted,
                created_at=app.created_at,
                job_title=app.job.title if app.job else "Unknown Job"
            )
        )
    return response_list


@router.put("/{application_id}/status", response_model=JobApplicationAdminResponse)
async def update_application_status(
    application_id: str,
    status_str: str = Form(...),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to update application status (e.g. reviewed).
    """
    app = await db.get(JobApplication, application_id)
    if not app or app.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found or has been deleted."
        )

    app.status = status_str
    await db.commit()
    await db.refresh(app)

    # Fetch job title to build response
    job = await db.get(Job, app.job_id)
    job_title = job.title if job else "Unknown Job"

    return JobApplicationAdminResponse(
        id=app.id,
        job_id=app.job_id,
        name=app.name,
        email=app.email,
        phone=app.phone,
        resume_url=app.resume_url,
        status=app.status,
        is_deleted=app.is_deleted,
        created_at=app.created_at,
        job_title=job_title
    )


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def soft_delete_application(
    application_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to soft-delete a job application.
    """
    app = await db.get(JobApplication, application_id)
    if not app:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Application not found."
        )

    app.is_deleted = True
    await db.commit()
    return None


@router.post("/admin/cleanup", status_code=status.HTTP_200_OK)
async def cleanup_deleted_applications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to permanently delete soft-deleted job applications
    and remove their associated PDF resumes from Supabase Storage.
    """
    result = await db.execute(
        select(JobApplication).where(JobApplication.is_deleted == True)
    )
    deleted_apps = result.scalars().all()

    count = 0
    for app in deleted_apps:
        # 1. Delete physical resume file from storage
        if app.resume_url:
            await upload_service.delete_file(app.resume_url)
        # 2. Delete DB record
        await db.delete(app)
        count += 1

    if count > 0:
        await db.commit()

    return {
        "success": True,
        "detail": f"Successfully hard-deleted {count} applications and their CV file attachments.",
        "cleaned_count": count
    }
