import json
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from datetime import datetime

from app.core.database import get_db
from app.schemas.candidate import CandidateCreate, CandidateStatusUpdate, CandidateNoteCreate, CandidateImportMapping, BulkDeleteCandidatesPayload, BulkRegenerateCertificatesPayload
from app.services.candidate_service import CandidateService
from app.deps import require_admin
from app.models.user import User
from app.models.admin_notification import AdminNotification
from app.models.lead_token import LeadToken
from app.models.lead import Lead
from sqlalchemy import select, update

router = APIRouter(prefix="/candidates", tags=["candidates"])
optional_bearer = HTTPBearer(auto_error=False)


@router.get("/validate-token")
async def validate_conversion_token(
    token: str = Query(..., description="Single-use conversion token from email link"),
    db: AsyncSession = Depends(get_db),
):
    """Public: validate a single-use lead conversion token and return lead details.
    
    Returns lead name, email, phone, course for pre-filling the apply form.
    Returns 400 if the token is not found or has already been used.
    """
    stmt = select(LeadToken).where(LeadToken.token == token)
    result = await db.execute(stmt)
    lead_token = result.scalar_one_or_none()

    if not lead_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired application link. Please contact the admissions office."
        )
    if lead_token.used:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This application link has already been used. Each link can only be used once."
        )

    # Fetch associated lead details for pre-filling the form
    lead_stmt = select(Lead).where(Lead.id == lead_token.lead_id)
    lead_res = await db.execute(lead_stmt)
    lead = lead_res.scalar_one_or_none()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Associated lead record not found."
        )

    return {
        "valid": True,
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone or "",
        "course": lead.interested_course or "",
    }

@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def apply_candidate(
    data: CandidateCreate,
    db: AsyncSession = Depends(get_db)
):
    """Public: submit a candidate application form.
    
    If a 'token' field is present in the payload, validates it as a single-use
    conversion token, links lead_id, and marks the token as used on success.
    """
    token_value = data.token  # Optional[str]
    resolved_lead_token = None

    if token_value:
        # Validate the token
        stmt = select(LeadToken).where(LeadToken.token == token_value)
        result = await db.execute(stmt)
        resolved_lead_token = result.scalar_one_or_none()

        if not resolved_lead_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid application link. Please contact the admissions office."
            )
        if resolved_lead_token.used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This application link has already been used."
            )

    try:
        payload = data.model_dump()
        # If token was valid, link lead_id from token (authoritative source)
        if resolved_lead_token:
            payload["lead_id"] = resolved_lead_token.lead_id

        candidate = await CandidateService.create_candidate_application(
            db, payload, created_by="Website Form"
        )

        # Mark token as used and delete/invalidate it AFTER successful candidate creation
        if resolved_lead_token:
            resolved_lead_token.used = True
            await db.delete(resolved_lead_token)
            await db.commit()

        return {"success": True, "application_number": candidate.application_number, "id": candidate.id}
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/")
async def list_candidates(
    status_filter: Optional[str] = Query(None, alias="status"),
    course_filter: Optional[str] = Query(None, alias="course"),
    qualification_filter: Optional[str] = Query(None, alias="qualification"),
    search_query: Optional[str] = Query(None, alias="search"),
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    skip: int = 0,
    limit: int = 50,
    is_deleted: bool = Query(False, alias="is_deleted"),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: list all applications with filters and pagination."""
    return await CandidateService.get_applications(
        db,
        status_filter=status_filter,
        course_filter=course_filter,
        qualification_filter=qualification_filter,
        search_query=search_query,
        start_date=start_date,
        end_date=end_date,
        skip=skip,
        limit=limit,
        is_deleted=is_deleted
    )

@router.get("/import/history")
async def list_import_history(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: get candidate Excel/CSV import history."""
    from app.models.candidate_application import CandidateImportBatch
    stmt = select(CandidateImportBatch).order_by(CandidateImportBatch.created_at.desc())
    res = await db.execute(stmt)
    batches = res.scalars().all()
    return batches

@router.get("/notifications")
async def list_notifications(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: list admin notifications."""
    stmt = select(AdminNotification).order_by(AdminNotification.created_at.desc()).limit(100)
    res = await db.execute(stmt)
    notifications = res.scalars().all()
    return notifications

@router.put("/notifications/read")
async def mark_notifications_read(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: mark all admin notifications as read."""
    stmt = update(AdminNotification).values(is_read=True)
    await db.execute(stmt)
    await db.commit()
    return {"success": True}


@router.delete("/permanent", status_code=status.HTTP_200_OK)
async def bulk_permanent_delete_candidates(
    payload: BulkDeleteCandidatesPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: permanently delete candidates from database and clear storage files."""
    count = await CandidateService.bulk_hard_delete_applications(db, payload.candidate_ids)
    return {"success": True, "detail": f"Permanently deleted {count} candidates and cleaned up associated storage files."}


@router.post("/bulk-trash", status_code=status.HTTP_200_OK)
async def bulk_trash_candidates(
    payload: BulkDeleteCandidatesPayload,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: move selected candidates to trash (soft delete)."""
    count = await CandidateService.bulk_soft_delete_applications(db, payload.candidate_ids, user_email=current_user.email)
    return {"success": True, "detail": f"Successfully moved {count} candidates to trash."}


@router.post("/bulk-regenerate-certificates", status_code=status.HTTP_200_OK)
async def bulk_regenerate_certificates(
    payload: BulkRegenerateCertificatesPayload,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: bulk regenerate certificates for selected candidate IDs."""
    result = await CandidateService.bulk_regenerate_certificates(db, payload.candidate_ids)
    return result


@router.post("/{id}/regenerate-certificate", status_code=status.HTTP_200_OK)
async def regenerate_single_certificate(
    id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: regenerate certificate for a single candidate."""
    candidate = await CandidateService.get_application_by_id(db, id)
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
    
    if (candidate.application_status or "").lower() != "completed":
        raise HTTPException(status_code=400, detail="Cannot regenerate certificate for non-completed application")
        
    from app.services.certificate_service import certificate_service
    updated_candidate = await certificate_service.regenerate_certificate(db, candidate)
    await db.commit()
    await db.refresh(updated_candidate)
    
    return {
        "success": True,
        "detail": "Certificate regenerated successfully",
        "certificate_url": updated_candidate.certificate_url,
        "certificate_id": updated_candidate.certificate_id
    }


@router.get("/{id}")
async def get_candidate(
    id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: get full application details by ID."""
    return await CandidateService.get_application_by_id(db, id)

@router.put("/{id}/status")
async def update_status(
    id: str,
    payload: CandidateStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: update candidate application status."""
    candidate = await CandidateService.update_application_status(
        db,
        id,
        payload.status,
        course_start_date=payload.course_start_date,
        completed_at=payload.completed_at,
        course_duration=payload.course_duration,
        performance=payload.performance,
        program_type=payload.program_type,
        course_applied=payload.course_applied,
        user_email=current_user.email
    )
    return {"success": True, "status": candidate.application_status}

@router.post("/{id}/notes")
async def create_note(
    id: str,
    payload: CandidateNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: add a counselor/admin note to a candidate application."""
    note = await CandidateService.add_candidate_note(
        db, id, payload.content, created_by=current_user.email
    )
    await db.commit()
    return {"success": True, "id": note.id, "content": note.content, "created_by": note.created_by, "created_at": note.created_at}

@router.post("/{id}/upload-document")
async def upload_candidate_document(
    id: str,
    doc_type: str = Query(..., description="Document type: cv, photo, aadhaar, college-id, confirmation-letter"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(optional_bearer)
):
    """Admin/Public: Upload candidate documents (CV, photo, Aadhaar, college ID, confirmation letter)."""
    user_email = "Website Form"
    if credentials:
        try:
            from app.core.security import decode_token
            from app.services.auth_service import get_user_by_id
            token = credentials.credentials
            payload = decode_token(token)
            user_id: str = payload.get("sub", "")
            if user_id and payload.get("type") == "access":
                user = await get_user_by_id(db, user_id)
                if user and user.is_active and user.role.value == "admin":
                    user_email = user.email
        except Exception:
            pass

    # Size checks: 5MB for images, 20MB for PDFs
    content = await file.read()
    max_size = 20 * 1024 * 1024 if doc_type == "cv" or file.content_type == "application/pdf" else 5 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size ({max_size // (1024 * 1024)}MB)."
        )

    candidate = await CandidateService.upload_document(
        db, id, doc_type, content, file.filename or "", file.content_type or "application/octet-stream", user_email=user_email
    )
    # Get public URL
    field_mapping = {
        "cv": "cv_url",
        "photo": "photo_url",
        "aadhaar": "aadhaar_url",
        "college-id": "college_id_url",
        "confirmation-letter": "confirmation_letter_url"
    }
    url = getattr(candidate, field_mapping[doc_type])
    return {"success": True, "url": url, "document_status": candidate.document_status}

@router.post("/import/preview")
async def preview_import_headers(
    file: UploadFile = File(...),
    _: User = Depends(require_admin)
):
    """Admin: parse Excel/CSV headers and return previews for layout mapping."""
    # Ensure correct extension
    filename = file.filename or ""
    if not (filename.endswith(".xlsx") or filename.endswith(".xls") or filename.endswith(".csv")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported format. Please upload .xlsx, .xls or .csv file. (Convert old .xls to .xlsx/.csv)."
        )

    content = await file.read()
    try:
        preview = CandidateService.parse_file_headers(content, filename)
        return preview
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse file: {str(e)}"
        )

@router.post("/import/process")
async def process_import(
    file: UploadFile = File(...),
    mapping: str = Form(..., description="JSON string of column mapping"),
    mode: str = Form("candidate_only", description="candidate_only, lead_only, lead_candidate"),
    tag: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: upload and import candidates with dynamic column mapping."""
    filename = file.filename or ""
    if not (filename.endswith(".xlsx") or filename.endswith(".xls") or filename.endswith(".csv")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file format.")

    try:
        mapping_dict = json.loads(mapping)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid mapping JSON format.")

    content = await file.read()
    try:
        stats = await CandidateService.process_import_batch(
            db=db,
            file_bytes=content,
            filename=filename,
            column_mapping=mapping_dict,
            mode=mode,
            upload_user=current_user.email,
            tag=tag
        )
        return {"success": True, "stats": stats}
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error processing import: {str(e)}"
        )

@router.delete("/{id}")
async def soft_delete_candidate(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: soft delete (trash) candidate application."""
    success = await CandidateService.soft_delete_application(db, id, user_email=current_user.email)
    if not success:
        raise HTTPException(status_code=404, detail="Candidate not found or already in trash")
    return {"success": True, "detail": "Candidate moved to trash"}

@router.post("/{id}/restore")
async def restore_candidate(
    id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: restore a soft-deleted candidate application."""
    success = await CandidateService.restore_application(db, id, user_email=current_user.email)
    if not success:
        raise HTTPException(status_code=404, detail="Candidate not found in trash")
    return {"success": True, "detail": "Candidate restored from trash"}

@router.delete("/{id}/permanent")
async def permanent_delete_candidate(
    id: str,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin)
):
    """Admin: permanently delete candidate application from database."""
    success = await CandidateService.hard_delete_application(db, id)
    if not success:
        raise HTTPException(status_code=404, detail="Candidate not found")
    return {"success": True, "detail": "Candidate permanently deleted"}
