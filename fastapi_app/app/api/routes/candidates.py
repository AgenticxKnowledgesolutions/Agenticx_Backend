import json
from fastapi import APIRouter, Depends, status, HTTPException, UploadFile, File, Form, Query, BackgroundTasks, Request
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
webhook_router = APIRouter(prefix="/portal/payments", tags=["payments"])
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
    import logging
    logger = logging.getLogger(__name__)

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
                msg = f"Token {token_value} has already been marked as used."
                logger.warning(f"Apply candidate failed: {msg}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Your application has already been submitted. (Detail: {msg})"
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
            msg = f"Candidate with email {existing_candidate.email} / phone {existing_candidate.phone} already completed application (App Ref: {existing_candidate.application_number})."
            logger.warning(f"Apply candidate failed: {msg}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Your application has already been submitted. (Detail: {msg})"
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
        logger.warning(f"HTTPException in apply_candidate: status={e.status_code}, detail={e.detail}")
        raise e
    except Exception as e:
        logger.error(f"Unexpected error in apply_candidate: {str(e)}", exc_info=True)
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
from datetime import timedelta
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


def log_payment_audit(
    action: str,
    candidate_id: str,
    caf_number: str,
    order_id: str,
    payment_id: str = "N/A",
    amount: float = 0.0,
    verification_result: str = "N/A",
    receipt_number: str = "N/A",
    client_ip: str = "Unknown"
):
    timestamp = datetime.now().isoformat()
    audit_msg = (
        f"[PAYMENT AUDIT] Action: {action} | Timestamp: {timestamp} | "
        f"Candidate ID: {candidate_id} | CAF: {caf_number} | "
        f"Order ID: {order_id} | Payment ID: {payment_id} | "
        f"Amount: {amount} | Result: {verification_result} | "
        f"Receipt: {receipt_number} | IP: {client_ip}"
    )
    logger.info(audit_msg)


async def reconcile_payment_state(db: AsyncSession, payment: CandidatePayment) -> bool:
    """Query Razorpay directly to check if the payment succeeded, and update status if so."""
    if payment.status == "Paid":
        return True
    if not payment.razorpay_order_id or payment.razorpay_order_id.startswith("order_mock_"):
        return False
        
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET
    if not key_id or not key_secret:
        return False
        
    try:
        url = f"https://api.razorpay.com/v1/orders/{payment.razorpay_order_id}/payments"
        auth_str = f"{key_id}:{key_secret}"
        auth_bytes = auth_str.encode('ascii')
        auth_b64 = base64.b64encode(auth_bytes).decode('ascii')
        headers = {
            "Authorization": f"Basic {auth_b64}",
            "Content-Type": "application/json"
        }
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=headers, timeout=10.0)
            if response.status_code == 200:
                resp_json = response.json()
                items = resp_json.get("items", [])
                for item in items:
                    if item.get("status") == "captured":
                        # Verify currency and amount
                        currency = item.get("currency")
                        amount_in_paise = item.get("amount")
                        if currency == "INR" and abs(amount_in_paise - int(payment.amount * 100)) <= 1:
                            payment_id = item.get("id")
                            
                            # Load candidate explicitly to avoid detached session issues
                            stmt = select(CandidateApplication).where(
                                CandidateApplication.id == payment.candidate_id
                            )
                            c_res = await db.execute(stmt)
                            candidate = c_res.scalar_one_or_none()
                            caf_no = candidate.application_number if candidate else "N/A"
                            
                            # Update payment record
                            payment.status = "Paid"
                            payment.transaction_id = payment_id
                            payment.razorpay_payment_id = payment_id
                            payment.payment_date = datetime.now()
                            
                            if candidate:
                                if payment.payment_type == "Admission Fee":
                                    candidate.admission_fee_paid = True
                                    old_status = candidate.application_status
                                    if candidate.auto_enroll_enabled:
                                        candidate.application_status = "Enrolled"
                                    else:
                                        candidate.application_status = "Admission Fee Paid"
                                        
                                    from app.models.candidate_application import CandidateTimelineEvent
                                    evt_status = CandidateTimelineEvent(
                                        candidate_id=candidate.id,
                                        event_type="Status Updated",
                                        description=f"Status changed from {old_status} to {candidate.application_status} on automatic payment reconciliation.",
                                        created_by="system_reconciliation"
                                    )
                                    db.add(evt_status)
                                    
                                from app.models.candidate_application import CandidateTimelineEvent
                                evt_pay = CandidateTimelineEvent(
                                    candidate_id=candidate.id,
                                    event_type="Payment Successful",
                                    description=f"Online payment of ₹{payment.amount} ({payment.payment_type}) reconciled successfully.",
                                    created_by="system_reconciliation"
                                )
                                db.add(evt_pay)
                            
                            await db.commit()
                            
                            # Generate receipt
                            try:
                                await CandidateService.generate_and_upload_receipt(db, payment.id)
                                # Refresh payment to get receipt number
                                await db.refresh(payment)
                            except Exception as re_err:
                                logger.error(f"Failed to generate receipt during reconciliation: {re_err}")
                            
                            log_payment_audit(
                                action="Automatic Reconciliation Success",
                                candidate_id=payment.candidate_id,
                                caf_number=caf_no,
                                order_id=payment.razorpay_order_id,
                                payment_id=payment_id,
                                amount=payment.amount,
                                verification_result="SUCCESS",
                                receipt_number=payment.receipt_number or "N/A",
                                client_ip="system"
                            )
                            return True
                        else:
                            log_payment_audit(
                                action="Automatic Reconciliation Validation Failure",
                                candidate_id=payment.candidate_id,
                                caf_number="N/A",
                                order_id=payment.razorpay_order_id,
                                payment_id=item.get("id"),
                                amount=float(amount_in_paise) / 100.0,
                                verification_result=f"FAILED (Currency: {currency}, expected INR. Amount: {amount_in_paise}, expected: {int(payment.amount*100)})",
                                client_ip="system"
                            )
    except Exception as e:
        logger.error(f"Reconciliation error for order {payment.razorpay_order_id}: {str(e)}")
        
    return False


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
        
        # Generate receipt
        await CandidateService.generate_and_upload_receipt(db, payment.id)
        
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
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_candidate: CandidateApplication = Depends(get_current_candidate)
):
    """Candidate: Verify and generate a Razorpay or mock order ID for payment."""
    client_ip = request.client.host if request.client else "Unknown"
    
    # 1. Fetch latest candidate state with payments loaded
    stmt = select(CandidateApplication).where(
        CandidateApplication.id == current_candidate.id,
        CandidateApplication.is_deleted == False
    ).options(selectinload(CandidateApplication.payments))
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()
    
    if not candidate:
        raise HTTPException(status_code=404, detail="Candidate not found")
        
    # 2. Check if candidate status is active
    if candidate.application_status == "Rejected":
         raise HTTPException(status_code=400, detail="This candidate application has been rejected.")
         
    # 3. Check if offer has expired
    if candidate.offer_expiry_date:
        now = datetime.now(candidate.offer_expiry_date.tzinfo) if candidate.offer_expiry_date.tzinfo else datetime.now()
        if candidate.offer_expiry_date < now:
            raise HTTPException(status_code=400, detail="The offer for this candidate has expired.")
            
    # 4. Check if standard_course_fee > 0 (or final_payable_amount > 0)
    if data.payment_type != "Admission Fee" and candidate.final_payable_amount <= 0:
        raise HTTPException(status_code=400, detail="No payable amount set for this candidate.")
        
    # 5. Check remaining balance
    if data.payment_type == "Admission Fee":
        if candidate.admission_fee_paid:
            raise HTTPException(status_code=400, detail="Admission fee has already been paid.")
        remaining = candidate.admission_fee_amount
    else:
        course_paid = sum(
            p.amount for p in candidate.payments 
            if p.status == "Paid" and p.payment_type != "Admission Fee"
        )
        remaining = max(0.0, candidate.final_payable_amount - course_paid)
        
    if data.amount <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than 0.")
        
    if data.amount > remaining:
        raise HTTPException(status_code=400, detail=f"Amount exceeds remaining balance of INR {remaining:.2f}.")

    # 6. Create local CandidatePayment record with status 'Created'
    payment = CandidatePayment(
        candidate_id=candidate.id,
        amount=data.amount,
        payment_type=data.payment_type,
        payment_method="Razorpay",
        status="Created",
    )
    db.add(payment)
    await db.flush()  # Generate payment.id

    amount_in_paise = int(data.amount * 100)
    key_id = settings.RAZORPAY_KEY_ID
    key_secret = settings.RAZORPAY_KEY_SECRET
    
    if not key_id or not key_secret:
        # Sandbox / Mock payment
        mock_order_id = f"order_mock_{uuid.uuid4().hex[:12]}"
        payment.razorpay_order_id = mock_order_id
        payment.transaction_id = mock_order_id
        await db.commit()
        
        log_payment_audit(
            action="Order Created (Sandbox)",
            candidate_id=candidate.id,
            caf_number=candidate.application_number,
            order_id=mock_order_id,
            amount=data.amount,
            client_ip=client_ip
        )
        
        return {
            "success": True,
            "order_id": mock_order_id,
            "amount": data.amount,
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
            "receipt": f"rcpt_{payment.id[:12]}"
        }
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=order_data, headers=headers, timeout=10.0)
            if response.status_code == 200:
                resp_json = response.json()
                razorpay_order_id = resp_json.get("id")
                payment.razorpay_order_id = razorpay_order_id
                await db.commit()
                
                log_payment_audit(
                    action="Order Created",
                    candidate_id=candidate.id,
                    caf_number=candidate.application_number,
                    order_id=razorpay_order_id,
                    amount=data.amount,
                    client_ip=client_ip
                )
                
                return {
                    "success": True,
                    "order_id": razorpay_order_id,
                    "amount": data.amount,
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


@router.get("/portal/payments/status/{order_id}")
async def get_payment_status(
    order_id: str,
    db: AsyncSession = Depends(get_db),
    current_candidate: CandidateApplication = Depends(get_current_candidate)
):
    """Check status of a payment by Razorpay order ID or transaction ID."""
    stmt = select(CandidatePayment).where(
        CandidatePayment.razorpay_order_id == order_id,
        CandidatePayment.candidate_id == current_candidate.id
    )
    res = await db.execute(stmt)
    payment = res.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")
        
    # Automatic reconciliation if status remains Created/Pending
    if payment.status != "Paid" and not order_id.startswith("order_mock_"):
        await reconcile_payment_state(db, payment)
        try:
            await db.refresh(payment)
        except Exception as ref_err:
            logger.warning(f"Could not refresh payment state in status endpoint: {ref_err}")
        
    return {
        "success": True,
        "status": payment.status,
        "amount": payment.amount,
        "payment_type": payment.payment_type,
        "receipt_url": payment.receipt_url
    }


@router.post("/portal/payments/verify")
async def candidate_portal_verify_payment(
    data: VerifyPaymentRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_candidate: CandidateApplication = Depends(get_current_candidate)
):
    """Candidate: Verify Razorpay sandbox or check real payment status."""
    client_ip = request.client.host if request.client else "Unknown"
    
    stmt = select(CandidatePayment).where(
        CandidatePayment.razorpay_order_id == data.razorpay_order_id,
        CandidatePayment.candidate_id == current_candidate.id
    ).options(selectinload(CandidatePayment.candidate))
    res = await db.execute(stmt)
    payment = res.scalar_one_or_none()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment record not found")
        
    # Signature verification
    is_valid = False
    if data.razorpay_order_id.startswith("order_mock_"):
        is_valid = True
        
        # In sandbox, since there is no real webhook, we mark it Paid here
        if payment.status != "Paid":
            payment.status = "Paid"
            payment.transaction_id = data.razorpay_payment_id
            payment.payment_date = datetime.now()
            payment.razorpay_signature = data.razorpay_signature
            
            # Progress candidate status for Admission Fee
            candidate = payment.candidate
            if payment.payment_type == "Admission Fee":
                candidate.admission_fee_paid = True
                old_status = candidate.application_status
                if candidate.auto_enroll_enabled:
                    candidate.application_status = "Enrolled"
                else:
                    candidate.application_status = "Admission Fee Paid"
                    
                from app.models.candidate_application import CandidateTimelineEvent
                evt_status = CandidateTimelineEvent(
                    candidate_id=candidate.id,
                    event_type="Status Updated",
                    description=f"Status changed from {old_status} to {candidate.application_status} on successful online payment (Mock)",
                    created_by=candidate.email
                )
                db.add(evt_status)
                
            from app.models.candidate_application import CandidateTimelineEvent
            evt_pay = CandidateTimelineEvent(
                candidate_id=candidate.id,
                event_type="Payment Successful",
                description=f"Online payment of ₹{payment.amount} ({payment.payment_type}) via Mock Razorpay verified successfully.",
                created_by=candidate.email
            )
            db.add(evt_pay)
            await db.commit()
            
            # Generate receipt synchronously for sandbox
            await CandidateService.generate_and_upload_receipt(db, payment.id)
            try:
                await db.refresh(payment)
            except Exception as ref_err:
                logger.warning(f"Could not refresh payment state in verify endpoint: {ref_err}")
            
        log_payment_audit(
            action="Signature Verified (Sandbox/Mock)",
            candidate_id=payment.candidate_id,
            caf_number=payment.candidate.application_number if payment.candidate else "N/A",
            order_id=data.razorpay_order_id,
            payment_id=data.razorpay_payment_id,
            amount=payment.amount,
            verification_result="SUCCESS",
            receipt_number=payment.receipt_number or "N/A",
            client_ip=client_ip
        )
        
        return {"success": True, "sandbox": True, "detail": "Sandbox payment mock-verified successfully."}
        
    else:
        # Real Razorpay checkout verification
        key_secret = settings.RAZORPAY_KEY_SECRET
        if not key_secret:
            raise HTTPException(status_code=500, detail="Payment gateway credentials missing.")
            
        msg = f"{data.razorpay_order_id}|{data.razorpay_payment_id}"
        generated_signature = hmac.new(
            key_secret.encode('utf-8'),
            msg.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        if generated_signature != data.razorpay_signature:
            log_payment_audit(
                action="Signature Verification Failed (Real)",
                candidate_id=payment.candidate_id,
                caf_number=payment.candidate.application_number if payment.candidate else "N/A",
                order_id=data.razorpay_order_id,
                payment_id=data.razorpay_payment_id,
                amount=payment.amount,
                verification_result="FAILED",
                client_ip=client_ip
            )
            raise HTTPException(status_code=400, detail="Payment signature verification failed.")
            
        # We do NOT mark the payment as Paid here for real orders.
        # We only save the transaction_id and razorpay_signature for reference/recovery
        # but keep status as "Created" or "Pending" if not already "Paid" by the webhook.
        if payment.status != "Paid":
            payment.transaction_id = data.razorpay_payment_id
            payment.razorpay_signature = data.razorpay_signature
            await db.commit()
            
        log_payment_audit(
            action="Signature Verified (Real, awaiting webhook)",
            candidate_id=payment.candidate_id,
            caf_number=payment.candidate.application_number if payment.candidate else "N/A",
            order_id=data.razorpay_order_id,
            payment_id=data.razorpay_payment_id,
            amount=payment.amount,
            verification_result="SUCCESS_AWAITING_WEBHOOK",
            client_ip=client_ip
        )
            
        return {"success": True, "sandbox": False, "detail": "Signature verified. Awaiting webhook confirmation."}


@router.post("/portal/payments/webhook")
@webhook_router.post("/webhook")
async def razorpay_payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """Razorpay Webhook: Capture payment completion events and transition state."""
    client_ip = request.client.host if request.client else "Unknown"
    payload_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    
    if not signature:
        logger.warning("Razorpay Webhook: Missing X-Razorpay-Signature header")
        raise HTTPException(status_code=400, detail="Missing signature")
        
    webhook_secret = settings.RAZORPAY_WEBHOOK_SECRET
    if not webhook_secret:
        logger.warning("Razorpay Webhook: Webhook secret not configured in settings")
        raise HTTPException(status_code=500, detail="Webhook configuration missing")
        
    # Verify signature
    generated_signature = hmac.new(
        webhook_secret.encode('utf-8'),
        payload_body,
        hashlib.sha256
    ).hexdigest()
    
    if not hmac.compare_digest(generated_signature, signature):
        logger.warning("Razorpay Webhook: Signature verification failed")
        raise HTTPException(status_code=400, detail="Signature verification failed")
        
    try:
        event_data = json.loads(payload_body.decode('utf-8'))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
        
    event_type = event_data.get("event")
    logger.info(f"Received Razorpay webhook event: {event_type}")
    
    # Handle events that signify payment success: payment.captured or order.paid
    if event_type in ["payment.captured", "order.paid"]:
        payment_entity = event_data.get("payload", {}).get("payment", {}).get("entity", {})
        order_id = payment_entity.get("order_id")
        payment_id = payment_entity.get("id")
        
        if not order_id or not payment_id:
            logger.warning(f"Razorpay Webhook: Missing order_id or payment_id in payload")
            return {"success": False, "detail": "Missing identifiers"}
            
        # Fetch payment record
        stmt = select(CandidatePayment).where(
            CandidatePayment.razorpay_order_id == order_id
        ).options(selectinload(CandidatePayment.candidate))
        res = await db.execute(stmt)
        payment = res.scalar_one_or_none()
        
        if not payment:
            logger.warning(f"Razorpay Webhook: Payment record not found for order_id: {order_id}")
            return {"success": False, "detail": "Payment record not found"}
            
        # Verify currency is INR
        currency = payment_entity.get("currency")
        if currency != "INR":
            logger.warning(f"Razorpay Webhook: Invalid currency {currency} for payment {payment_id}")
            log_payment_audit(
                action="Webhook Payment Failed",
                candidate_id=payment.candidate_id,
                caf_number=payment.candidate.application_number if payment.candidate else "N/A",
                order_id=order_id,
                payment_id=payment_id,
                amount=payment.amount,
                verification_result=f"FAILED_CURRENCY (Received: {currency})",
                client_ip=client_ip
            )
            return {"success": False, "detail": "Invalid currency"}

        # Verify amount matches (within minor precision error or exact match in paise)
        captured_amount_paise = payment_entity.get("amount")
        expected_amount_paise = int(payment.amount * 100)
        if abs(captured_amount_paise - expected_amount_paise) > 1:
            logger.warning(f"Razorpay Webhook: Amount mismatch for payment {payment_id}. Captured: {captured_amount_paise}, Expected: {expected_amount_paise}")
            log_payment_audit(
                action="Webhook Payment Failed",
                candidate_id=payment.candidate_id,
                caf_number=payment.candidate.application_number if payment.candidate else "N/A",
                order_id=order_id,
                payment_id=payment_id,
                amount=payment.amount,
                verification_result=f"FAILED_AMOUNT_MISMATCH (Captured paise: {captured_amount_paise}, Expected: {expected_amount_paise})",
                client_ip=client_ip
            )
            return {"success": False, "detail": "Amount mismatch"}
            
        # Duplicate webhook protection
        if payment.status == "Paid":
            logger.info(f"Razorpay Webhook: Payment for order_id {order_id} is already processed as Paid.")
            log_payment_audit(
                action="Webhook Already Processed",
                candidate_id=payment.candidate_id,
                caf_number=payment.candidate.application_number if payment.candidate else "N/A",
                order_id=order_id,
                payment_id=payment_id,
                amount=payment.amount,
                verification_result="DUPLICATE_IGNORED",
                client_ip=client_ip
            )
            return {"success": True, "detail": "Already processed"}
            
        # Update payment record
        payment.status = "Paid"
        payment.transaction_id = payment_id
        payment.razorpay_payment_id = payment_id
        payment.razorpay_signature = signature
        payment.payment_date = datetime.now()
        
        candidate = payment.candidate
        
        # Progress candidate status if Admission Fee
        if payment.payment_type == "Admission Fee":
            candidate.admission_fee_paid = True
            old_status = candidate.application_status
            if candidate.auto_enroll_enabled:
                candidate.application_status = "Enrolled"
            else:
                candidate.application_status = "Admission Fee Paid"
                
            from app.models.candidate_application import CandidateTimelineEvent
            evt_status = CandidateTimelineEvent(
                candidate_id=candidate.id,
                event_type="Status Updated",
                description=f"Status changed from {old_status} to {candidate.application_status} on successful online payment via Razorpay Webhook",
                created_by="Razorpay Webhook"
            )
            db.add(evt_status)
            
        from app.models.candidate_application import CandidateTimelineEvent
        evt_pay = CandidateTimelineEvent(
            candidate_id=candidate.id,
            event_type="Payment Successful",
            description=f"Online payment of ₹{payment.amount} ({payment.payment_type}) via Razorpay verified by Webhook.",
            created_by="Razorpay Webhook"
        )
        db.add(evt_pay)
        
        await db.commit()
        
        # Generate PDF receipt and upload it
        try:
            await CandidateService.generate_and_upload_receipt(db, payment.id)
            await db.refresh(payment)
        except Exception as receipt_err:
            logger.error(f"Razorpay Webhook receipt generation failure: {receipt_err}")
            
        log_payment_audit(
            action="Webhook Payment Success",
            candidate_id=payment.candidate_id,
            caf_number=candidate.application_number if candidate else "N/A",
            order_id=order_id,
            payment_id=payment_id,
            amount=payment.amount,
            verification_result="SUCCESS",
            receipt_number=payment.receipt_number or "N/A",
            client_ip=client_ip
        )
        
    return {"success": True}

