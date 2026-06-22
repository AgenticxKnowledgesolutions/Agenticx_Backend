import io
from datetime import datetime
import httpx
from fastapi import APIRouter, Depends, status, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.core.database import get_db
from app.core.limiter import limiter
from app.deps import require_admin
from app.models.user import User
from app.models.candidate_application import CandidateApplication
from app.schemas.certificate import (
    CertificateFetchRequest,
    CertificateFetchResponse,
    CertificateVerifyResponse,
)

router = APIRouter(prefix="/certificates", tags=["certificates"])


@router.post("/fetch", response_model=CertificateFetchResponse)
@limiter.limit("10/minute")
async def fetch_certificate(
    request: Request,
    payload: CertificateFetchRequest,
    db: AsyncSession = Depends(get_db),
):
    """Public endpoint to fetch a generated certificate using candidate email and date of birth.

    Rate-limited to prevent brute forcing.
    """
    try:
        # Parse the expected dob format YYYY-MM-DD
        dob_date = datetime.strptime(payload.dob, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid date of birth format. Must be YYYY-MM-DD.",
        )

    # Search for candidate by email (case-insensitive)
    stmt = select(CandidateApplication).where(
        func.lower(CandidateApplication.email) == payload.email.lower()
    )
    res = await db.execute(stmt)
    candidates = res.scalars().all()

    # Find the candidate matching the parsed date of birth
    matched_candidate = None
    from datetime import timedelta
    for candidate in candidates:
        if candidate.date_of_birth:
            utc_date = candidate.date_of_birth.date()
            ist_date = (candidate.date_of_birth + timedelta(hours=5, minutes=30)).date()
            if utc_date == dob_date or ist_date == dob_date:
                matched_candidate = candidate
                break

    if not matched_candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No candidate matches the provided email and date of birth.",
        )

    # Check if a certificate has been generated
    if matched_candidate.certificate_status != "generated":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No certificate has been generated for this candidate yet.",
        )

    # Format completed date nicely
    date_str = (
        matched_candidate.completed_at.strftime("%B %d, %Y")
        if matched_candidate.completed_at
        else ""
    )

    return CertificateFetchResponse(
        name=matched_candidate.full_name,
        course=matched_candidate.course_applied or "Professional Certification Program",
        completion_date=date_str,
        certificate_url=matched_candidate.certificate_url or "",
        certificate_id=matched_candidate.certificate_id or "",
    )


@router.get("/verify/{certificate_id}", response_model=CertificateVerifyResponse)
async def verify_certificate(
    certificate_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Public verification endpoint to authenticate a certificate using its UUID/ID."""
    stmt = select(CandidateApplication).where(
        CandidateApplication.certificate_id == certificate_id
    )
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Certificate verification failed: Invalid certificate ID.",
        )

    # Formulate status value based on DB status field
    status_val = "valid" if candidate.certificate_status == "generated" else "revoked"
    date_str = (
        candidate.completed_at.strftime("%B %d, %Y")
        if candidate.completed_at
        else ""
    )

    return CertificateVerifyResponse(
        name=candidate.full_name,
        course=candidate.course_applied or "Professional Certification Program",
        status=status_val,
        completion_date=date_str,
        certificate_url=candidate.certificate_url,
    )


@router.post("/{candidate_id}/regenerate")
async def regenerate_certificate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only endpoint to force manual regeneration of a candidate's certificate."""
    stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id)
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    from app.services.certificate_service import certificate_service

    # Re-run certificate generation and upload
    await certificate_service.generate_and_save_certificate(db, candidate)
    await db.commit()
    await db.refresh(candidate)

    return {
        "message": "Certificate generated successfully.",
        "certificate_url": candidate.certificate_url,
    }


@router.get("/{candidate_id}/download")
async def download_certificate(
    candidate_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Admin-only endpoint to download/stream the PDF certificate from storage."""
    stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id)
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()

    if not candidate:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate not found.",
        )

    if not candidate.certificate_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Certificate has not been generated for this candidate.",
        )

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(candidate.certificate_url, timeout=30.0)
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to retrieve PDF certificate from storage.",
                )

            # Strip non-alphanumeric chars to create a clean, safe filename
            safe_name = "".join(
                c for c in candidate.full_name if c.isalnum() or c in (" ", "_", "-")
            ).strip()
            filename = f"Certificate_{safe_name.replace(' ', '_')}.pdf"

            return StreamingResponse(
                io.BytesIO(response.content),
                media_type="application/pdf",
                headers={
                    "Content-Disposition": f"attachment; filename={filename}"
                },
            )
        except httpx.HTTPError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Network error downloading certificate from storage: {str(e)}",
            )
