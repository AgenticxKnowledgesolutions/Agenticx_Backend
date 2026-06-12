import json
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List, Dict
from datetime import datetime

from app.core.database import get_db
from app.schemas.candidate import CandidateCreate, CandidateStatusUpdate, CandidateNoteCreate, CandidateImportMapping
from app.services.candidate_service import CandidateService
from app.deps import require_admin
from app.models.user import User
from app.models.admin_notification import AdminNotification
from sqlalchemy import select, update

router = APIRouter(prefix="/candidates", tags=["candidates"])

@router.post("/apply", status_code=status.HTTP_201_CREATED)
async def apply_candidate(
    data: CandidateCreate,
    db: AsyncSession = Depends(get_db)
):
    """Public: submit a candidate application form."""
    try:
        candidate = await CandidateService.create_candidate_application(db, data.model_dump(), created_by="Website Form")
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
        limit=limit
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
        db, id, payload.status, remarks=payload.remarks, user_email=current_user.email
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
    current_user: User = Depends(require_admin)
):
    """Admin/Public: Upload candidate documents (CV, photo, Aadhaar, college ID, confirmation letter)."""
    # Size checks: 5MB for images, 20MB for PDFs
    content = await file.read()
    max_size = 20 * 1024 * 1024 if doc_type == "cv" or file.content_type == "application/pdf" else 5 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size ({max_size // (1024 * 1024)}MB)."
        )

    candidate = await CandidateService.upload_document(
        db, id, doc_type, content, file.filename or "", file.content_type or "application/octet-stream", user_email=current_user.email
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
