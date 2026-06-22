import base64
import hashlib
import uuid
import openpyxl
import csv
import io
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from sqlalchemy import select, or_, and_, func
from sqlalchemy.orm import selectinload, Session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, UploadFile

from app.core.config import settings
from app.models.candidate_application import CandidateApplication, CandidateNote, CandidateTimelineEvent, CandidateImportBatch
from app.models.admin_notification import AdminNotification
from app.models.lead import Lead
from app.models.lead_interaction import LeadInteraction
from app.models.lead_timeline import LeadTimelineEvent as LeadTimelineEventModel
from app.services.upload_service import UploadService
from cryptography.fernet import Fernet

# -------------------------------------------------------------
# Aadhaar Cryptography Helpers
# -------------------------------------------------------------
def get_fernet() -> Fernet:
    # Deterministic Fernet key derived from settings.SECRET_KEY
    key = hashlib.sha256(settings.SECRET_KEY.encode()).digest()
    fernet_key = base64.urlsafe_b64encode(key)
    return Fernet(fernet_key)

def encrypt_aadhaar(aadhaar: str) -> Optional[str]:
    if not aadhaar or not aadhaar.strip():
        return None
    f = get_fernet()
    return f.encrypt(aadhaar.strip().encode()).decode()

def decrypt_aadhaar(encrypted_aadhaar: Optional[str]) -> Optional[str]:
    if not encrypted_aadhaar:
        return None
    f = get_fernet()
    try:
        return f.decrypt(encrypted_aadhaar.encode()).decode()
    except Exception:
        return "Decryption Error"

def mask_aadhaar(aadhaar: Optional[str]) -> Optional[str]:
    if not aadhaar:
        return None
    aadhaar_clean = "".join(filter(str.isdigit, aadhaar))
    if len(aadhaar_clean) >= 4:
        return f"XXXX XXXX {aadhaar_clean[-4:]}"
    return "XXXX XXXX XXXX"

# -------------------------------------------------------------
# Supabase Documents Upload Service
# -------------------------------------------------------------
class CandidateUploadService(UploadService):
    def __init__(self):
        super().__init__()
        self.bucket_name = "candidate-documents"

candidate_upload_service = CandidateUploadService()

# -------------------------------------------------------------
# Service Core Class
# -------------------------------------------------------------
class CandidateService:
    @staticmethod
    def calculate_document_status(candidate: CandidateApplication) -> str:
        """Calculates status based on completed document fields."""
        fields = [candidate.cv_url, candidate.photo_url, candidate.aadhaar_url]
        filled_count = sum(1 for f in fields if f)
        if filled_count == len(fields):
            return "Complete"
        elif filled_count > 0:
            return "Partial"
        return "Missing Documents"

    @staticmethod
    async def generate_application_number(db: AsyncSession) -> str:
        """Generates a unique application number formatted like CAF-YYYY-XXXXX."""
        current_year = datetime.utcnow().year
        
        # Get count of candidate records created in current year
        year_start = datetime(current_year, 1, 1)
        year_end = datetime(current_year + 1, 1, 1)
        
        stmt = select(func.count(CandidateApplication.id)).where(
            and_(
                CandidateApplication.created_at >= year_start,
                CandidateApplication.created_at < year_end
            )
        )
        res = await db.execute(stmt)
        count = res.scalar() or 0
        
        # Format with 5 digits sequence
        seq_num = count + 1
        return f"CAF-{current_year}-{seq_num:05d}"

    @classmethod
    async def create_candidate_application(
        cls, db: AsyncSession, data: Dict[str, Any], created_by: Optional[str] = "Website"
    ) -> CandidateApplication:
        # Check if email or phone already exists in candidate table to prevent duplicates
        email = data.get("email", "").strip().lower()
        phone = data.get("phone", "").strip()
        
        stmt = select(CandidateApplication).where(
            or_(
                CandidateApplication.email.ilike(email),
                CandidateApplication.phone == phone
            )
        )
        existing_res = await db.execute(stmt)
        existing = existing_res.scalars().first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Candidate with email/phone already registered (App Ref: {existing.application_number})"
            )

        app_num = await cls.generate_application_number(db)
        
        # Aadhaar Encryption
        aadhaar_plain = data.get("aadhaar_number")
        encrypted_aadhaar = encrypt_aadhaar(aadhaar_plain) if aadhaar_plain else None
        
        # Extract fields
        candidate = CandidateApplication(
            id=str(uuid.uuid4()),
            lead_id=data.get("lead_id"),
            application_number=app_num,
            full_name=data.get("full_name"),
            email=email,
            phone=phone,
            whatsapp_number=data.get("whatsapp_number"),
            address=data.get("address"),
            emergency_contact=data.get("emergency_contact"),
            qualification=data.get("qualification"),
            blood_group=data.get("blood_group"),
            course_applied=data.get("course_applied"),
            mode_of_learning=data.get("mode_of_learning"),
            college_name=data.get("college_name"),
            date_of_birth=data.get("date_of_birth"),
            gender=data.get("gender"),
            reference_details=data.get("reference_details"),
            languages_known=data.get("languages_known"),
            parent_guardian_name=data.get("parent_guardian_name"),
            parent_guardian_occupation=data.get("parent_guardian_occupation"),
            aadhaar_number_encrypted=encrypted_aadhaar,
            registration_transaction_id=data.get("registration_transaction_id"),
            application_status=data.get("application_status", "Submitted"),
            document_status=data.get("document_status", "Missing Documents"),
            candidate_source=data.get("candidate_source", "Website"),
            remarks=data.get("remarks"),
            import_tag=data.get("import_tag"),
            next_followup_at=data.get("next_followup_at"),
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        # Calculate document status
        candidate.document_status = cls.calculate_document_status(candidate)

        db.add(candidate)
        
        # Update associated lead to Converted status if lead_id is provided
        lead_id = data.get("lead_id")
        if lead_id:
            from app.services.lead_service import add_timeline_event as add_lead_timeline_event
            lead_stmt = select(Lead).where(Lead.id == lead_id)
            lead_res = await db.execute(lead_stmt)
            lead = lead_res.scalars().first()
            if lead and lead.status != "Converted":
                lead.status = "Converted"
                await add_lead_timeline_event(
                    db,
                    lead_id=lead_id,
                    event_type="Converted",
                    description="Lead converted to candidate via admission form submission.",
                    created_by="System"
                )
                
        await db.flush()

        # Log timeline event
        await cls.add_timeline_event(
            db,
            candidate.id,
            "Submitted",
            f"Candidate application submitted successfully by {created_by}.",
            created_by
        )

        # Trigger internal admin notification
        notification = AdminNotification(
            id=str(uuid.uuid4()),
            title="New Candidate Application",
            message=f"New application {app_num} received from {candidate.full_name} for course {candidate.course_applied}.",
            notification_type="new_application",
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.add(notification)
        await db.commit()
        await db.refresh(candidate)
        return candidate

    @staticmethod
    async def add_timeline_event(
        db: AsyncSession, candidate_id: str, event_type: str, description: str, created_by: Optional[str] = "Admin"
    ) -> Optional[CandidateTimelineEvent]:
        # Disabled: Timeline Events feature removed
        return None

    @staticmethod
    async def add_candidate_note(
        db: AsyncSession, candidate_id: str, content: str, created_by: Optional[str] = "Admin"
    ) -> CandidateNote:
        note = CandidateNote(
            id=str(uuid.uuid4()),
            candidate_id=candidate_id,
            content=content,
            created_by=created_by,
            created_at=datetime.utcnow()
        )
        db.add(note)
        await db.flush()
        return note

    @classmethod
    async def upload_document(
        cls, db: AsyncSession, candidate_id: str, doc_type: str, file_bytes: bytes, original_filename: str, mime_type: str, user_email: Optional[str] = "Admin"
    ) -> CandidateApplication:
        stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id)
        res = await db.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

        # Map document type to fields
        field_mapping = {
            "cv": "cv_url",
            "photo": "photo_url",
            "aadhaar": "aadhaar_url",
            "college-id": "college_id_url",
            "confirmation-letter": "confirmation_letter_url"
        }
        
        field_name = field_mapping.get(doc_type)
        if not field_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid document type")

        # Upload file to Supabase in structured folder
        folder = f"{doc_type}/{candidate.id}"
        public_url = await candidate_upload_service.upload_file(file_content=file_bytes, folder=folder, original_filename=original_filename, mime_type=mime_type)

        # Update candidate URL field
        setattr(candidate, field_name, public_url)
        candidate.document_status = cls.calculate_document_status(candidate)
        candidate.updated_at = datetime.utcnow()
        
        # Add timeline event
        await cls.add_timeline_event(
            db,
            candidate.id,
            "Document Uploaded",
            f"Uploaded {doc_type.replace('-', ' ').title()} document: {original_filename}",
            user_email
        )
        await db.commit()
        await db.refresh(candidate)
        return candidate

    @classmethod
    async def get_applications(
        cls,
        db: AsyncSession,
        status_filter: Optional[str] = None,
        course_filter: Optional[str] = None,
        qualification_filter: Optional[str] = None,
        search_query: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        skip: int = 0,
        limit: int = 50,
        is_deleted: bool = False
    ) -> Dict[str, Any]:
        stmt = select(CandidateApplication)
        count_stmt = select(func.count(CandidateApplication.id))
        
        conditions = [CandidateApplication.is_deleted == is_deleted]
        if status_filter:
            conditions.append(CandidateApplication.application_status == status_filter)
        if course_filter:
            conditions.append(CandidateApplication.course_applied == course_filter)
        if qualification_filter:
            conditions.append(CandidateApplication.qualification.ilike(f"%{qualification_filter}%"))
        if start_date:
            conditions.append(CandidateApplication.created_at >= start_date)
        if end_date:
            conditions.append(CandidateApplication.created_at <= end_date)
            
        if search_query:
            q = f"%{search_query}%"
            conditions.append(
                or_(
                    CandidateApplication.full_name.ilike(q),
                    CandidateApplication.email.ilike(q),
                    CandidateApplication.phone.ilike(q),
                    CandidateApplication.application_number.ilike(q)
                )
            )

        if conditions:
            stmt = stmt.where(and_(*conditions))
            count_stmt = count_stmt.where(and_(*conditions))

        # Order by created_at desc
        stmt = stmt.order_by(CandidateApplication.created_at.desc()).offset(skip).limit(limit)
        
        # Execute queries
        records_res = await db.execute(stmt)
        records = records_res.scalars().all()
        
        total_res = await db.execute(count_stmt)
        total = total_res.scalar() or 0

        # Format output (mask Aadhaar for all records in the list view)
        formatted_records = []
        for r in records:
            r_dict = {c.name: getattr(r, c.name) for c in r.__table__.columns}
            r_dict["aadhaar_number_masked"] = mask_aadhaar(decrypt_aadhaar(r.aadhaar_number_encrypted))
            formatted_records.append(r_dict)

        return {"total": total, "records": formatted_records}

    @classmethod
    async def get_application_by_id(cls, db: AsyncSession, candidate_id: str) -> Dict[str, Any]:
        stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id).options(
            selectinload(CandidateApplication.notes),
            selectinload(CandidateApplication.timeline_events)
        )
        res = await db.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate application not found")

        r_dict = {c.name: getattr(candidate, c.name) for c in candidate.__table__.columns}
        decrypted = decrypt_aadhaar(candidate.aadhaar_number_encrypted)
        r_dict["aadhaar_number_decrypted"] = decrypted
        r_dict["aadhaar_number_masked"] = mask_aadhaar(decrypted)
        
        # Serialize notes and timeline events
        r_dict["notes"] = [
            {"id": n.id, "content": n.content, "created_by": n.created_by, "created_at": n.created_at} for n in candidate.notes
        ]
        r_dict["timeline_events"] = [
            {"id": t.id, "event_type": t.event_type, "description": t.description, "created_by": t.created_by, "created_at": t.created_at} for t in candidate.timeline_events
        ]
        return r_dict

    @classmethod
    async def soft_delete_application(
        cls, db: AsyncSession, candidate_id: str, user_email: Optional[str] = "Admin"
    ) -> bool:
        stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id, CandidateApplication.is_deleted == False)
        res = await db.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            return False
        
        candidate.is_deleted = True
        candidate.deleted_at = datetime.utcnow()
        
        # Log timeline event
        await cls.add_timeline_event(
            db,
            candidate.id,
            "Deleted",
            f"Candidate application moved to trash by {user_email}.",
            user_email
        )
        await db.commit()
        return True

    @classmethod
    async def restore_application(
        cls, db: AsyncSession, candidate_id: str, user_email: Optional[str] = "Admin"
    ) -> bool:
        stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id, CandidateApplication.is_deleted == True)
        res = await db.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            return False
        
        candidate.is_deleted = False
        candidate.deleted_at = None
        
        # Log timeline event
        await cls.add_timeline_event(
            db,
            candidate.id,
            "Restored",
            f"Candidate application restored from trash by {user_email}.",
            user_email
        )
        await db.commit()
        return True

    @classmethod
    async def hard_delete_application(
        cls, db: AsyncSession, candidate_id: str
    ) -> bool:
        stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id)
        res = await db.execute(stmt)
        candidate = res.scalar_one_or_none()
        if not candidate:
            return False
        
        await db.delete(candidate)
        await db.commit()
        return True

    @classmethod
    async def update_application_status(
        cls,
        db: AsyncSession,
        candidate_id: str,
        new_status: str,
        remarks: Optional[str] = None,
        course_start_date: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        course_duration: Optional[str] = None,
        user_email: Optional[str] = "Admin"
    ) -> CandidateApplication:
        try:
            stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id)
            res = await db.execute(stmt)
            candidate = res.scalar_one_or_none()
            if not candidate:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")

            # Lowercase incoming status
            status_val = new_status.lower()
            old_status = candidate.application_status
            candidate.application_status = status_val
            
            if remarks:
                candidate.remarks = remarks

            # Update course start/end dates and duration
            if course_start_date is not None:
                candidate.course_start_date = course_start_date
            if completed_at is not None:
                candidate.completed_at = completed_at
            if course_duration is not None:
                candidate.course_duration = course_duration

            candidate.updated_at = datetime.utcnow()

            # Add timeline event
            desc = f"Application status changed from '{old_status}' to '{status_val}'."
            if remarks:
                desc += f" Remarks: {remarks}"
            await cls.add_timeline_event(db, candidate.id, status_val, desc, user_email)

            # Update DB FIRST and commit status change
            await db.commit()
            await db.refresh(candidate)

            # Trigger certificate generation if status updated to Completed
            if status_val == "completed" and candidate.certificate_status != "generated":
                try:
                    # Validate required fields
                    if not candidate.full_name:
                        raise Exception("Missing name")
                    if not candidate.course_applied:
                        raise Exception("Missing course")
                    if not candidate.date_of_birth:
                        raise Exception("Missing DOB")

                    from app.services.certificate_service import certificate_service
                    await certificate_service.generate_and_save_certificate(db, candidate)
                    await db.commit()
                    await db.refresh(candidate)
                except Exception as ce:
                    print("CERTIFICATE ERROR:", str(ce))
                    # DO NOT break status update

            return candidate
        except HTTPException:
            # Re-raise standard FastAPI HTTPExceptions
            raise
        except Exception as e:
            print("STATUS UPDATE ERROR:", str(e))
            raise HTTPException(status_code=500, detail=str(e))

    # -------------------------------------------------------------
    # Excel/CSV Import Parser Methods
    # -------------------------------------------------------------
    @staticmethod
    def parse_file_headers(file_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Reads file headers and returns the first 20 rows for layout mapping previews."""
        headers = []
        rows = []
        
        if filename.endswith(".csv"):
            try:
                content = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = file_bytes.decode("latin-1")
            
            reader = csv.reader(io.StringIO(content))
            for i, r in enumerate(reader):
                if i == 0:
                    headers = [h.strip() for h in r]
                else:
                    rows.append(r)
                    if len(rows) >= 20:
                        break
        else:
            # openpyxl for xlsx files
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), read_only=True, data_only=True)
            sheet = wb.active
            for i, r in enumerate(sheet.iter_rows(values_only=True)):
                # Skip empty lines
                if not any(r):
                    continue
                if not headers:
                    headers = [str(h).strip() if h is not None else "" for h in r]
                else:
                    rows.append([str(v) if v is not None else "" for v in r])
                    if len(rows) >= 20:
                        break
                        
        return {"headers": headers, "preview_rows": rows}

    @classmethod
    async def process_import_batch(
        cls,
        db: AsyncSession,
        file_bytes: bytes,
        filename: str,
        column_mapping: Dict[str, str],
        mode: str,  # "candidate_only", "lead_only", "lead_candidate"
        upload_user: str,
        tag: Optional[str] = None
    ) -> Dict[str, Any]:
        """Parses entire sheet and imports records following selected mode and CRM duplicate check rules."""
        # Check mapping contains basic fields
        # Note: mapping is: { "full_name": "Excel Column Name", "email": "Excel Column Name" }
        inverse_mapping = {v: k for k, v in column_mapping.items() if v}
        
        rows = []
        if filename.endswith(".csv"):
            try:
                content = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                content = file_bytes.decode("latin-1")
            reader = csv.DictReader(io.StringIO(content))
            for r in reader:
                rows.append({inverse_mapping.get(k.strip(), k.strip()): v for k, v in r.items()})
        else:
            wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
            sheet = wb.active
            headers = []
            for r in sheet.iter_rows(values_only=True):
                if not any(r):
                    continue
                if not headers:
                    headers = [str(h).strip() if h is not None else "" for h in r]
                else:
                    row_data = {}
                    for col_idx, val in enumerate(r):
                        if col_idx < len(headers):
                            h_name = headers[col_idx]
                            mapped_field = inverse_mapping.get(h_name)
                            if mapped_field:
                                row_data[mapped_field] = str(val) if val is not None else ""
                    if row_data:
                        rows.append(row_data)

        # Batch creation stats
        batch = CandidateImportBatch(
            id=str(uuid.uuid4()),
            file_name=filename,
            uploaded_by=upload_user,
            total_rows=len(rows),
            new_records=0,
            updated_records=0,
            duplicate_records=0,
            failed_records=0,
            created_at=datetime.utcnow()
        )
        db.add(batch)
        await db.flush()

        for idx, row in enumerate(rows):
            # Read mapped values
            email = row.get("email", "").strip().lower()
            phone = row.get("phone", "").strip()
            name = row.get("full_name", "").strip()
            
            # Basic validation
            if not email and not phone:
                batch.failed_records += 1
                continue

            # Format/clean fields
            whatsapp = row.get("whatsapp_number", "").strip()
            address = row.get("address", "").strip()
            emergency = row.get("emergency_contact", "").strip()
            qualification = row.get("qualification", "").strip()
            blood = row.get("blood_group", "").strip()
            course = row.get("course_applied", "").strip()
            mode_learning = row.get("mode_of_learning", "").strip()
            college = row.get("college_name", "").strip()
            dob_str = row.get("date_of_birth", "").strip()
            gender = row.get("gender", "").strip()
            reference = row.get("reference_details", "").strip()
            languages = row.get("languages_known", "").strip()
            parent = row.get("parent_guardian_name", "").strip()
            parent_occ = row.get("parent_guardian_occupation", "").strip()
            aadhaar = row.get("aadhaar_number", "").strip()
            remarks = row.get("remarks", "").strip()
            
            dob = None
            if dob_str:
                for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S", "%d/%m/%Y", "%m/%d/%Y"):
                    try:
                        dob = datetime.strptime(dob_str.split()[0], fmt)
                        break
                    except Exception:
                        continue

            # -------------------------------------------------------------
            # Mode processing
            # -------------------------------------------------------------
            
            # MODE: LEAD ONLY or LEAD + CANDIDATE
            lead_id = None
            if mode in ("lead_only", "lead_candidate"):
                # Check for existing lead using standard CRM rules
                lead_stmt = select(Lead).where(
                    and_(
                        Lead.is_deleted == False,
                        or_(
                            Lead.email.ilike(email) if email else False,
                            Lead.phone == phone if phone else False
                        )
                    )
                )
                lead_res = await db.execute(lead_stmt)
                existing_lead = lead_res.scalars().first()
                
                if existing_lead:
                    # Duplicate Lead detected
                    existing_lead.duplicate_hits += 1
                    existing_lead.interaction_count += 1
                    existing_lead.last_interaction_at = datetime.utcnow()
                    existing_lead.latest_source = f"Excel Import - {batch.file_name}"
                    
                    # Merge course
                    if course:
                        merged = existing_lead.merged_courses or []
                        if course not in merged:
                            merged.append(course)
                        existing_lead.merged_courses = merged
                    
                    # Update empty lead fields
                    if name and not existing_lead.name:
                        existing_lead.name = name
                    if email and not existing_lead.email:
                        existing_lead.email = email
                    
                    # Log timeline and interaction
                    it = LeadInteraction(
                        id=str(uuid.uuid4()),
                        lead_id=existing_lead.id,
                        interaction_type="Import Duplicate",
                        source=f"Excel Import",
                        course=course or existing_lead.interested_course,
                        notes=f"Duplicate lead detected during batch import (Batch tag: {tag or 'None'}).",
                        created_at=datetime.utcnow()
                    )
                    db.add(it)
                    
                    lt = LeadTimelineEventModel(
                        id=str(uuid.uuid4()),
                        lead_id=existing_lead.id,
                        event_type="Import Updated",
                        description=f"Lead interaction merged from batch import '{filename}'.",
                        created_by=upload_user,
                        created_at=datetime.utcnow()
                    )
                    db.add(lt)
                    lead_id = existing_lead.id
                    batch.duplicate_records += 1
                else:
                    # Create new Lead
                    new_lead = Lead(
                        id=str(uuid.uuid4()),
                        name=name or "Unknown Candidate",
                        email=email or "",
                        phone=phone or "",
                        interested_course=course or "",
                        source=f"Excel Import - {batch.file_name}",
                        status="Pending",
                        duplicate_hits=0,
                        interaction_count=1,
                        last_interaction_at=datetime.utcnow(),
                        first_source=f"Excel Import",
                        latest_source=f"Excel Import",
                        created_at=datetime.utcnow()
                    )
                    db.add(new_lead)
                    await db.flush()
                    
                    lt = LeadTimelineEventModel(
                        id=str(uuid.uuid4()),
                        lead_id=new_lead.id,
                        event_type="Import Created",
                        description=f"Lead created via batch import '{filename}'.",
                        created_by=upload_user,
                        created_at=datetime.utcnow()
                    )
                    db.add(lt)
                    lead_id = new_lead.id
                    batch.new_records += 1

            # MODE: CANDIDATE ONLY or LEAD + CANDIDATE
            if mode in ("candidate_only", "lead_candidate"):
                # Duplicate check inside Candidate table
                cand_stmt = select(CandidateApplication).where(
                    or_(
                        CandidateApplication.email.ilike(email) if email else False,
                        CandidateApplication.phone == phone if phone else False
                    )
                )
                cand_res = await db.execute(cand_stmt)
                existing_candidate = cand_res.scalars().first()
                
                if existing_candidate:
                    # Update missing fields in candidate
                    if name and not existing_candidate.full_name:
                        existing_candidate.full_name = name
                    if whatsapp and not existing_candidate.whatsapp_number:
                        existing_candidate.whatsapp_number = whatsapp
                    if address and not existing_candidate.address:
                        existing_candidate.address = address
                    if emergency and not existing_candidate.emergency_contact:
                        existing_candidate.emergency_contact = emergency
                    if qualification and not existing_candidate.qualification:
                        existing_candidate.qualification = qualification
                    if blood and not existing_candidate.blood_group:
                        existing_candidate.blood_group = blood
                    if course and not existing_candidate.course_applied:
                        existing_candidate.course_applied = course
                    if mode_learning and not existing_candidate.mode_of_learning:
                        existing_candidate.mode_of_learning = mode_learning
                    if college and not existing_candidate.college_name:
                        existing_candidate.college_name = college
                    if dob and not existing_candidate.date_of_birth:
                        existing_candidate.date_of_birth = dob
                    if gender and not existing_candidate.gender:
                        existing_candidate.gender = gender
                    if reference and not existing_candidate.reference_details:
                        existing_candidate.reference_details = reference
                    if languages and not existing_candidate.languages_known:
                        existing_candidate.languages_known = languages
                    if parent and not existing_candidate.parent_guardian_name:
                        existing_candidate.parent_guardian_name = parent
                    if parent_occ and not existing_candidate.parent_guardian_occupation:
                        existing_candidate.parent_guardian_occupation = parent_occ
                    if aadhaar and not existing_candidate.aadhaar_number_encrypted:
                        existing_candidate.aadhaar_number_encrypted = encrypt_aadhaar(aadhaar)
                    if remarks:
                        existing_candidate.remarks = (existing_candidate.remarks or "") + f"\n[Import update]: {remarks}"
                    
                    existing_candidate.updated_at = datetime.utcnow()
                    
                    # Track import batch
                    existing_candidate.import_batch_id = batch.id
                    existing_candidate.import_tag = tag
                    
                    # Add notes and timeline
                    await cls.add_timeline_event(
                        db,
                        existing_candidate.id,
                        "Import Merged",
                        f"Candidate details updated during Excel batch import '{filename}' (Mode: {mode}).",
                        upload_user
                    )
                    
                    if mode == "candidate_only":
                        batch.duplicate_records += 1
                    else:
                        batch.updated_records += 1
                else:
                    # Create new Candidate Application
                    app_num = await cls.generate_application_number(db)
                    
                    new_candidate = CandidateApplication(
                        id=str(uuid.uuid4()),
                        lead_id=lead_id,
                        application_number=app_num,
                        full_name=name or "Unknown Candidate",
                        email=email or "",
                        phone=phone or "",
                        whatsapp_number=whatsapp,
                        address=address,
                        emergency_contact=emergency,
                        qualification=qualification,
                        blood_group=blood,
                        course_applied=course,
                        mode_of_learning=mode_learning or "Offline",
                        college_name=college,
                        date_of_birth=dob,
                        gender=gender,
                        reference_details=reference,
                        languages_known=languages,
                        parent_guardian_name=parent,
                        parent_guardian_occupation=parent_occ,
                        aadhaar_number_encrypted=encrypt_aadhaar(aadhaar) if aadhaar else None,
                        application_status="Submitted",
                        document_status="Missing Documents",  # Since Excel import has no docs initially
                        candidate_source="Excel Import",
                        remarks=remarks,
                        import_batch_id=batch.id,
                        import_tag=tag,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow()
                    )
                    
                    db.add(new_candidate)
                    await db.flush()
                    
                    await cls.add_timeline_event(
                        db,
                        new_candidate.id,
                        "Submitted",
                        f"Candidate application created during Excel batch import '{filename}' (Mode: {mode}).",
                        upload_user
                    )
                    
                    if mode == "candidate_only":
                        batch.new_records += 1

        await db.commit()
        return {
            "batch_id": batch.id,
            "total_rows": batch.total_rows,
            "new_records": batch.new_records,
            "updated_records": batch.updated_records,
            "duplicate_records": batch.duplicate_records,
            "failed_records": batch.failed_records
        }
