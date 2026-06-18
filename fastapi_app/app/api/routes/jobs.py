from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import selectinload
from typing import List
from app.core.database import get_db
from app.models.job import Job
from app.schemas.job import JobResponse, JobCreate
from app.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/", response_model=List[JobResponse])
async def list_active_jobs(db: AsyncSession = Depends(get_db)):
    """
    Public endpoint to fetch all active job opportunities.
    """
    result = await db.execute(
        select(Job)
        .where(Job.is_active == True)
        .order_by(Job.created_at.desc())
    )
    return result.scalars().all()


@router.get("/admin", response_model=List[JobResponse])
async def list_all_jobs_admin(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to fetch all jobs (active and inactive).
    """
    result = await db.execute(
        select(Job)
        .order_by(Job.created_at.desc())
    )
    return result.scalars().all()


@router.post("/", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to post a new job opportunity.
    """
    job = Job(**data.model_dump())
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job_by_id(job_id: str, db: AsyncSession = Depends(get_db)):
    """
    Public/Admin endpoint to fetch a single job by its ID.
    """
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job position not found."
        )
    return job


@router.put("/{job_id}", response_model=JobResponse)
async def update_job(
    job_id: str,
    data: JobCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to update an existing job position.
    """
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job position not found."
        )
    
    for key, value in data.model_dump().items():
        setattr(job, key, value)
        
    await db.commit()
    await db.refresh(job)
    return job


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job(
    job_id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """
    Admin-only endpoint to delete a job position.
    """
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job position not found."
        )
    await db.delete(job)
    await db.commit()
    return None
