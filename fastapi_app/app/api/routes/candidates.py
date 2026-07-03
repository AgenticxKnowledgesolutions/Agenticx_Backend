import json
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form, Query, BackgroundTasks
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
from app.models.candidate_application import CandidateApplication
from sqlalchemy import select, update, or_

router = APIRouter(prefix="/candidates", tags=["candidates"])
optional_bearer = HTTPBearer(auto_error=False)


@router.get("/validate-token")
async def validate_conversion_token(
    token: str = Query(..., description="Single-use conversion token from email link"),
    db: AsyncSession = Depends(get_db),
):
    """Public: validate a single-use lead conversion token and return lead/candidate details.
    
    Returns details for pre-filling the apply form.
    Returns 400 if the token is not found, has already been used, or the application is already completed.
    """
    # 1. Check LeadToken first
    stmt = select(LeadToken).where(LeadToken.token == token)
    result = await db.execute(stmt)
    lead_token = result.scalar_one_or_none()

    existing_candidate = None
    lead = None

    if lead_token:
        if lead_token.used:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your application has already been submitted. Please contact AgenticX if you need to modify your information."
            )
        
        # Check if candidate application already exists for this lead
        cand_stmt = select(CandidateApplication).where(
            CandidateApplication.lead_id == lead_token.lead_id,
            CandidateApplication.is_deleted == False
        )
        cand_res = await db.execute(cand_stmt)
        existing_candidate = cand_res.scalar_one_or_none()
    else:
        # Check if the token matches CandidateApplication.candidate_token directly
        cand_stmt = select(CandidateApplication).where(
            CandidateApplication.candidate_token == token,
            CandidateApplication.is_deleted == False
        )
        cand_res = await db.execute(cand_stmt)
        existing_candidate = cand_res.scalar_one_or_none()

    if existing_candidate:
        # If candidate already has DOB, they completed the form
        if existing_candidate.date_of_birth is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your application has already been submitted. Please contact AgenticX if you need to modify your information."
            )
        
        return {
            "valid": True,
            "name": existing_candidate.full_name,
            "email": existing_candidate.email,
            "phone": existing_candidate.phone or "",
            "course": existing_candidate.course_applied or "",
            "program_id": existing_candidate.program_id or "",
        }

    # Fetch associated lead details for pre-filling the form if no existing candidate
    if lead_token:
        lead_stmt = select(Lead).where(Lead.id == lead_token.lead_id)
        lead_res = await db.execute(lead_stmt)
        lead = lead_res.scalar_one_or_none()

    if not lead:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired application link. Please contact the admissions office."
        )

    return {
        "valid": True,
        "name": lead.name,
        "email": lead.email,
        "phone": lead.phone or "",
        "course": lead.interested_course or "",
        "program_id": lead.program_id or "",
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
    existing_candidate = None

    if token_value:
        # Validate the token
        stmt = select(LeadToken).where(LeadToken.token == token_value)
        result = await db.execute(stmt)
        resolved_lead_token = result.scalar_one_or_none()

        if resolved_lead_token:
            if resolved_lead_token.used:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Your application has already been submitted. Please contact AgenticX if you need to modify your information."
                )
            
            # Find candidate by lead_id from LeadToken
            cand_stmt = select(CandidateApplication).where(
                CandidateApplication.lead_id == resolved_lead_token.lead_id,
                CandidateApplication.is_deleted == False
            )
            cand_res = await db.execute(cand_stmt)
            existing_candidate = cand_res.scalar_one_or_none()
        else:
            # Check by CandidateApplication.candidate_token directly
            cand_stmt = select(CandidateApplication).where(
                CandidateApplication.candidate_token == token_value,
                CandidateApplication.is_deleted == False
            )
            cand_res = await db.execute(cand_stmt)
            existing_candidate = cand_res.scalar_one_or_none()

    if not existing_candidate:
        # Check by email or phone to catch duplicate key constraint violations
        email = data.email.strip().lower()
        phone = data.phone.strip()
        stmt = select(CandidateApplication).where(
            or_(
                CandidateApplication.email.ilike(email),
                CandidateApplication.phone == phone
            ),
            CandidateApplication.is_deleted == False
        )
        result = await db.execute(stmt)
        existing_candidate = result.scalar_one_or_none()

    if existing_candidate:
        if existing_candidate.date_of_birth is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Your application has already been submitted. Please contact AgenticX if you need to modify your information."
            )

    try:
        payload = data.model_dump()
        if resolved_lead_token:
            payload["lead_id"] = resolved_lead_token.lead_id

        if existing_candidate:
            # Update existing candidate record
            candidate = await CandidateService.update_existing_candidate_application(
                db, existing_candidate, payload, created_by="Website Form"
            )
        else:
            # Create new candidate application
            candidate = await CandidateService.create_candidate_application(
                db, payload, created_by="Website Form"
            )

        # Mark token as used instead of deleting it
        if resolved_lead_token:
            resolved_lead_token.used = True
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
    from app.models.candidate_application import CandidateApplication
    stmt = select(CandidateApplication).where(CandidateApplication.id == id)
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()
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
        user_email=current_user.email,
        program_id=payload.program_id,
        programme_domain=payload.programme_domain,
        college_name=payload.college_name
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
    background_tasks: BackgroundTasks,
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

    # Calculate total_rows quickly in request thread
    import io
    import openpyxl
    total_rows = "Processing..."
    try:
        if filename.endswith(".csv"):
            total_rows = max(0, content.count(b"\n") - 1)
        else:
            wb = openpyxl.load_workbook(io.BytesIO(content), read_only=True)
            sheet = wb.active
            total_rows = max(0, (sheet.max_row or 0) - 1)
    except Exception:
        pass

    try:
        background_tasks.add_task(
            CandidateService.execute_import_in_background,
            file_bytes=content,
            filename=filename,
            column_mapping=mapping_dict,
            mode=mode,
            upload_user=current_user.email,
            tag=tag
        )
        return {
            "success": True,
            "stats": {
                "total_rows": total_rows,
                "new_records": "Processing...",
                "updated_records": "Processing...",
                "duplicate_records": "Processing...",
                "failed_records": "Processing..."
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error starting background import: {str(e)}"
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


# Candidate Portal & Offer Management Endpoints

import hmac
import hashlib
import base64
import uuid
import logging
import httpx
from sqlalchemy.orm import selectinload
from app.deps import get_current_candidate
from app.models.candidate_payment import CandidatePayment
from app.schemas.candidate import (
    CandidateOfferUpdate,
    RecordOfflinePayment,
    CreateOrderRequest,
    VerifyPaymentRequest
)
from app.core.config import settings

logger = logging.getLogger(__name__)


@router.put("/{id}/offer")
async def update_candidate_offer(
    id: str,
    data: CandidateOfferUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Update candidate financial offer and settings."""
    try:
        stmt = select(CandidateApplication).where(CandidateApplication.id == id, CandidateApplication.is_deleted == False)
        res = await db.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
            
        standard_fee = data.standard_course_fee
        if standard_fee is None:
            if candidate.program_id:
                from app.models.program import Program
                prog_res = await db.execute(select(Program).where(Program.id == candidate.program_id))
                prog = prog_res.scalar_one_or_none()
                if prog and prog.standard_fee and float(prog.standard_fee) > 0.0:
                    standard_fee = float(prog.standard_fee)
            
            if standard_fee is None:
                standard_fee = candidate.standard_course_fee or 0.0

        candidate.standard_course_fee = standard_fee
        candidate.scholarship_amount = data.scholarship_amount
        candidate.special_discount = data.special_discount
        candidate.corporate_discount = data.corporate_discount
        candidate.promo_discount = data.promo_discount
        candidate.booking_amount = data.booking_amount
        candidate.offer_remarks = data.offer_remarks
        candidate.offer_expiry_date = data.offer_expiry_date
        candidate.admission_fee_amount = data.admission_fee_amount
        candidate.auto_enroll_enabled = data.auto_enroll_enabled
        
        # Calculate final payable amount
        candidate.final_payable_amount = max(
            0.0,
            standard_fee - (
                data.scholarship_amount +
                data.special_discount +
                data.corporate_discount +
                data.promo_discount
            )
        )
        
        # Log timeline event
        from app.models.candidate_application import CandidateTimelineEvent
        evt = CandidateTimelineEvent(
            candidate_id=candidate.id,
            event_type="Offer Updated",
            description=f"Financial offer updated by admin: Course Fee ₹{candidate.standard_course_fee}, Final Payable ₹{candidate.final_payable_amount}",
            created_by=current_user.email
        )
        db.add(evt)
        await db.commit()
        
        return await CandidateService.get_application_by_id(db, id)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Exception occurred in update_candidate_offer: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update candidate offer: {str(e)}"
        )


@router.post("/{id}/record-payment")
async def record_candidate_payment(
    id: str,
    data: RecordOfflinePayment,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    """Admin: Record an offline payment (Cash/UPI/Bank Transfer) for a candidate."""
    try:
        stmt = select(CandidateApplication).where(CandidateApplication.id == id, CandidateApplication.is_deleted == False)
        res = await db.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=404, detail="Candidate not found")
            
        # Record payment
        payment = CandidatePayment(
            candidate_id=candidate.id,
            amount=data.amount,
            payment_type=data.payment_type,
            payment_method=data.payment_method,
            status="Paid",
            transaction_id=data.transaction_id,
            payment_date=datetime.now()
        )
        db.add(payment)
        
        # Update candidate status
        from app.models.candidate_application import CandidateTimelineEvent
        if data.payment_type == "Admission Fee":
            candidate.admission_fee_paid = True
            old_status = candidate.application_status
            if candidate.auto_enroll_enabled:
                candidate.application_status = "Enrolled"
            else:
                candidate.application_status = "Admission Fee Paid"
                
            evt_status = CandidateTimelineEvent(
                candidate_id=candidate.id,
                event_type="Status Updated",
                description=f"Status changed from {old_status} to {candidate.application_status} on manual payment record",
                created_by=current_user.email
            )
            db.add(evt_status)
            
        evt_pay = CandidateTimelineEvent(
            candidate_id=candidate.id,
            event_type="Payment Recorded",
            description=f"Manual payment of ₹{data.amount} ({data.payment_type}) via {data.payment_method} recorded.",
            created_by=current_user.email
        )
        db.add(evt_pay)
        await db.commit()
        
        return await CandidateService.get_application_by_id(db, id)
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        logger.exception("Exception occurred in record_candidate_payment: %s", str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to record payment: {str(e)}"
        )


@router.get("/portal/profile")
async def get_candidate_portal_profile(
    db: AsyncSession = Depends(get_db),
    current_candidate: CandidateApplication = Depends(get_current_candidate)
):
    """Candidate: Get logged-in candidate profile, financial offers, and payment logs."""
    return await CandidateService.get_application_by_id(db, current_candidate.id)


@router.post("/portal/upload-document")
async def upload_candidate_portal_document(
    doc_type: str = Query(..., description="Document type: cv, photo, aadhaar"),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_candidate: CandidateApplication = Depends(get_current_candidate)
):
    """Candidate: Upload/replace own document (CV, Photo, Aadhaar)."""
    if doc_type not in ["cv", "photo", "aadhaar"]:
        raise HTTPException(status_code=400, detail="Invalid document type for candidate self-service upload")
        
    content = await file.read()
    max_size = 20 * 1024 * 1024 if doc_type == "cv" or file.content_type == "application/pdf" else 5 * 1024 * 1024
    if len(content) > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File exceeds maximum allowed size ({max_size // (1024 * 1024)}MB)."
        )
        
    candidate = await CandidateService.upload_document(
        db, current_candidate.id, doc_type, content, file.filename or "", file.content_type or "application/octet-stream", user_email=current_candidate.email
    )
    field_mapping = {
        "cv": "cv_url",
        "photo": "photo_url",
        "aadhaar": "aadhaar_url"
    }
    url = getattr(candidate, field_mapping[doc_type])
    return {"success": True, "url": url, "document_status": candidate.document_status}


@router.post("/portal/payments/create-order")
async def candidate_portal_create_payment_order(
    data: CreateOrderRequest,
    current_candidate: CandidateApplication = Depends(get_current_candidate)
):
    """Candidate: Generate a Razorpay or mock order ID for payment verification."""
    amount = data.amount
    amount_in_paise = int(amount * 100)
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET
    
    if not key_id or not key_secret:
        return {
            "success": True,
            "order_id": f"order_mock_{uuid.uuid4().hex[:12]}",
            "amount": amount,
            "currency": "INR",
            "key": "mock_key_id",
            "sandbox": True
        }
        
    try:
        url = "https://api.razorpay.com/v1/orders"
        auth_str = f"{key_id}:{key_secret}"
        auth_bytes = auth_str.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        order_data = {
            "amount": amount_in_paise,
            "currency": "INR",
            "receipt": f"rcpt_{uuid.uuid4().hex[:12]}"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=order_data, headers=headers, timeout=10.0)
            if response.status_code == 200:
                resp_json = response.json()
                return {
                    "success": True,
                    "order_id": resp_json.get("id"),
                    "amount": amount,
                    "currency": "INR",
                    "key": key_id,
                    "sandbox": False
                }
            else:
                logger.error(f"Razorpay order creation failed: {response.text}")
                raise HTTPException(status_code=500, detail="Razorpay order creation failed")
    except Exception as e:
        logger.error(f"Exception creating Razorpay order: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to connect to payment gateway")


@router.post("/portal/payments/verify")
async def candidate_portal_verify_payment(
    data: VerifyPaymentRequest,
    db: AsyncSession = Depends(get_db),
    current_candidate: CandidateApplication = Depends(get_current_candidate)
):
    """Candidate: Verify Razorpay webhook signature and record transaction."""
    stmt = select(CandidateApplication).where(CandidateApplication.id == current_candidate.id)
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    # Signature verification
    is_valid = False
    if data.razorpay_order_id.startswith("order_mock_"):
        is_valid = True
    else:
        key_secret = settings.RAZORPAY_KEY_SECRET
        if not key_secret:
            raise HTTPException(status_code=500, detail="Payment gateway credentials missing.")
            
        msg = f"{data.razorpay_order_id}|{data.razorpay_payment_id}"
        generated_signature = hmac.new(
            key_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature == data.razorpay_signature:
            is_valid = True
            
    if not is_valid:
        raise HTTPException(status_code=400, detail="Payment signature verification failed.")
        
    # Record payment
    payment = CandidatePayment(
        candidate_id=candidate.id,
        amount=data.amount,
        payment_type=data.payment_type,
        payment_method="Razorpay",
        status="Paid",
        transaction_id=data.razorpay_payment_id,
        payment_date=datetime.now()
    )
    db.add(payment)
    
    # Status progression
    from app.models.candidate_application import CandidateTimelineEvent
    if data.payment_type == "Admission Fee":
        candidate.admission_fee_paid = True
        old_status = candidate.application_status
        if candidate.auto_enroll_enabled:
            candidate.application_status = "Enrolled"
        else:
            candidate.application_status = "Admission Fee Paid"
            
        evt_status = CandidateTimelineEvent(
            candidate_id=candidate.id,
            event_type="Status Updated",
            description=f"Status changed from {old_status} to {candidate.application_status} on successful online payment",
            created_by=candidate.email
        )
        db.add(evt_status)
        
    evt_pay = CandidateTimelineEvent(
        candidate_id=candidate.id,
        event_type="Payment Successful",
        description=f"Online payment of ₹{data.amount} ({data.payment_type}) via Razorpay verified successfully.",
        created_by=candidate.email
    )
    db.add(evt_pay)
    await db.commit()
    
    return {"success": True, "detail": f"Payment of ₹{data.amount} verified successfully."}
