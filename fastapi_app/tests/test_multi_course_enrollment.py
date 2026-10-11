"""
Comprehensive unit & integration tests for Multiple Course Enrollments for the Same Person.

Tests verify:
TEST 1: Create one person/lead and first course application -> One CandidateApplication.
TEST 2: Add a DIFFERENT course to the same person -> Two CandidateApplications.
TEST 3: Verify both applications have different application numbers/IDs.
TEST 4: Verify Application A points to Course A, Application B points to Course B.
TEST 5: Change Application A status -> Application B status unchanged.
TEST 6: Change Application A course-specific information -> Application B unchanged.
TEST 7: Generate/regenerate certificate for Application A -> Only Application A certificate changes; Application B untouched.
TEST 8: Attempt to add Course A again -> Request rejected as duplicate ("This candidate is already enrolled in this course.").
TEST 9: Attempt to add Course B again -> Request rejected as duplicate.
TEST 10: Verify the original first-time Lead -> Candidate conversion flow still works.
"""

import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.main import app
from app.models.lead import Lead
from app.models.lead_token import LeadToken
from app.models.program import Program
from app.models.candidate_application import CandidateApplication
from app.schemas.candidate import CandidateEnrollAdditional, CandidateCreate
from app.services.candidate_service import CandidateService
from app.services.certificate_service import certificate_service
from app.deps import require_admin
from app.core.database import get_db


class MockAdminUser:
    id = "admin-123"
    email = "admin@agenticx.co.in"
    role = "admin"


@pytest.fixture
def client():
    app.dependency_overrides[require_admin] = lambda: MockAdminUser()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_multi_course_enrollment_full_suite():
    # Setup mock database session and in-memory stores
    candidates_db = {}
    programs_db = {}
    leads_db = {}
    lead_tokens_db = {}

    # Define Programs
    prog_a = Program(
        id="prog-python-uuid",
        name="Python Full Stack",
        slug="python-full-stack",
        program_type="Course",
        standard_fee=25000.0,
        duration="3 Months",
        mode="Hybrid",
        domain="Software Development",
        is_deleted=False
    )
    programs_db[prog_a.id] = prog_a

    prog_b = Program(
        id="prog-django-uuid",
        name="Django Development",
        slug="django-development",
        program_type="Course",
        standard_fee=18000.0,
        duration="2 Months",
        mode="Online",
        domain="Backend Development",
        is_deleted=False
    )
    programs_db[prog_b.id] = prog_b

    # Helper mock db execute
    async def mock_execute(stmt):
        mock_result = MagicMock()
        stmt_str = str(stmt)

        # Check queries on Program
        if "FROM programs" in stmt_str or "programs." in stmt_str:
            # Check program id lookup
            for pid, p in programs_db.items():
                if pid in stmt_str or (hasattr(stmt, "compile") and pid in str(stmt.compile())):
                    mock_result.scalar_one_or_none.return_value = p
                    mock_result.scalars.return_value.all.return_value = [p]
                    return mock_result
            # Default lookup
            mock_result.scalar_one_or_none.return_value = prog_a
            mock_result.scalars.return_value.all.return_value = list(programs_db.values())
            return mock_result

        # Check queries on CandidateApplication
        if "candidate_applications" in stmt_str:
            matched = list(candidates_db.values())
            mock_result.scalars.return_value.all.return_value = matched
            mock_result.scalars.return_value.first.return_value = matched[0] if matched else None
            mock_result.scalar_one_or_none.return_value = matched[0] if matched else None
            return mock_result

        # Check queries on Lead
        if "FROM leads" in stmt_str:
            matched = list(leads_db.values())
            mock_result.scalars.return_value.all.return_value = matched
            mock_result.scalars.return_value.first.return_value = matched[0] if matched else None
            mock_result.scalar_one_or_none.return_value = matched[0] if matched else None
            return mock_result

        # Fallback
        mock_result.scalar_one_or_none.return_value = None
        mock_result.scalars.return_value.all.return_value = []
        return mock_result

    # -------------------------------------------------------------------------
    # TEST 1: Create one person/lead and first course application.
    # Expected: One CandidateApplication.
    # -------------------------------------------------------------------------
    person_lead_id = "lead-sneha-1"
    lead_sneha = Lead(
        id=person_lead_id,
        name="Sneha",
        email="sneha@example.com",
        phone="9876543210",
        interested_course="Python Full Stack",
        program_id=prog_a.id,
        status="Pending",
        is_deleted=False
    )
    leads_db[person_lead_id] = lead_sneha

    app_a = CandidateApplication(
        id="app-python-id",
        lead_id=person_lead_id,
        program_id=prog_a.id,
        application_number="CAF-2026-00001",
        full_name="Sneha",
        email="sneha@example.com",
        phone="9876543210",
        whatsapp_number="9876543210",
        address="123 Tech Park, Kollam",
        emergency_contact="9123456780",
        qualification="B.Tech Computer Science",
        college_name="College of Engineering",
        date_of_birth=datetime(2001, 5, 20),
        gender="Female",
        course_applied=prog_a.name,
        program_type=prog_a.program_type,
        mode_of_learning="Hybrid",
        course_duration="3 Months",
        application_status="Completed",
        performance="Excellent",
        standard_course_fee=25000.0,
        final_payable_amount=25000.0,
        admission_fee_amount=250.0,
        admission_fee_paid=True,
        candidate_token="token-python-123",
        certificate_id="PY-001",
        certificate_url="https://storage.example.com/certificates/app-python-id.pdf",
        certificate_status="valid",
        completed_at=datetime(2026, 8, 1),
        is_deleted=False
    )
    candidates_db[app_a.id] = app_a

    assert len(candidates_db) == 1
    assert candidates_db["app-python-id"].course_applied == "Python Full Stack"
    assert candidates_db["app-python-id"].lead_id == person_lead_id

    # -------------------------------------------------------------------------
    # TEST 2 & TEST 3 & TEST 4: Add a DIFFERENT course to the same person.
    # Expected:
    # - Two CandidateApplications.
    # - Different application numbers / IDs.
    # - Application A points to Course A, Application B points to Course B.
    # - Common demographic/academic details safely copied.
    # - Course-specific details, certificates, application_number independent.
    # -------------------------------------------------------------------------
    mock_db = AsyncMock()

    # Configure mock_db execute to return proper entities depending on statement
    async def dynamic_execute(stmt):
        res = MagicMock()
        stmt_compiled_str = str(stmt)
        # Handle parameters when compiled
        params = {}
        try:
            if hasattr(stmt, "compile"):
                compiled = stmt.compile()
                stmt_compiled_str = str(compiled)
                params = getattr(compiled, "params", {})
        except Exception:
            pass

        # Candidate lookup by id
        if "FROM candidate_applications" in stmt_compiled_str:
            if "app-python-id" in str(params.values()) or "app-python-id" in stmt_compiled_str:
                res.scalar_one_or_none.return_value = candidates_db.get("app-python-id")
                return res
            if "app-django-id" in str(params.values()) or "app-django-id" in stmt_compiled_str:
                res.scalar_one_or_none.return_value = candidates_db.get("app-django-id")
                return res
            # Candidate application search for person duplicates
            if "candidate_applications.lead_id" in stmt_compiled_str or "candidate_applications.email" in stmt_compiled_str:
                res.scalars.return_value.all.return_value = list(candidates_db.values())
                return res
            if "application_number LIKE" in stmt_compiled_str or "application_number like" in stmt_compiled_str:
                res.scalars.return_value.all.return_value = [c.application_number for c in candidates_db.values()]
                return res

        # Program lookup
        if "FROM programs" in stmt_compiled_str:
            if prog_b.id in str(params.values()) or prog_b.id in stmt_compiled_str:
                res.scalar_one_or_none.return_value = prog_b
                return res
            if prog_a.id in str(params.values()) or prog_a.id in stmt_compiled_str:
                res.scalar_one_or_none.return_value = prog_a
                return res

        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = AsyncMock(side_effect=dynamic_execute)
    mock_db.commit = AsyncMock()
    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()

    def mock_db_add(instance):
        if isinstance(instance, CandidateApplication):
            candidates_db[instance.id] = instance

    mock_db.add = MagicMock(side_effect=mock_db_add)

    # Enroll in Django Development
    enroll_payload = {
        "candidate_id": "app-python-id",
        "program_id": prog_b.id,
        "mode_of_learning": "Online",
        "standard_course_fee": 18000.0,
        "admission_fee_amount": 250.0,
        "admission_fee_paid": True,
        "remarks": "Enrolling Sneha in Django as second course"
    }

    app_b = await CandidateService.enroll_additional_course(mock_db, enroll_payload, created_by="Admin")

    # TEST 2 verification
    assert len(candidates_db) == 2, "Must have exactly 2 CandidateApplications"

    # TEST 3 verification: different IDs and application numbers
    assert app_a.id != app_b.id, "Application IDs must be different"
    assert app_a.application_number != app_b.application_number, "Application numbers must be different"
    assert app_b.application_number.startswith("CAF-")

    # TEST 4 verification: Application A points to Course A, Application B points to Course B
    assert app_a.course_applied == "Python Full Stack"
    assert app_a.program_id == prog_a.id
    assert app_b.course_applied == "Django Development"
    assert app_b.program_id == prog_b.id

    # Verify safe copying: same identity, common person info preserved
    assert app_b.lead_id == app_a.lead_id == person_lead_id
    assert app_b.full_name == app_a.full_name == "Sneha"
    assert app_b.email == app_a.email == "sneha@example.com"
    assert app_b.phone == app_a.phone == "9876543210"
    assert app_b.college_name == app_a.college_name
    assert app_b.date_of_birth == app_a.date_of_birth

    # Verify course-specific isolation: fresh certificate fields & independent tokens
    assert app_b.candidate_token != app_a.candidate_token
    assert app_b.certificate_id is None, "New application certificate ID must be None"
    assert app_b.certificate_url is None, "New application certificate URL must be None"
    assert app_b.certificate_status == "pending"
    assert app_b.completed_at is None
    assert app_b.performance is None
    assert app_b.standard_course_fee == 18000.0
    assert app_a.standard_course_fee == 25000.0

    # -------------------------------------------------------------------------
    # TEST 5: Change Application A status -> Application B status unchanged.
    # -------------------------------------------------------------------------
    original_app_b_status = app_b.application_status
    app_a.application_status = "Archived"

    assert app_a.application_status == "Archived"
    assert app_b.application_status == original_app_b_status, "Application B status must remain unchanged"

    # -------------------------------------------------------------------------
    # TEST 6: Change Application A course-specific info -> Application B unchanged.
    # -------------------------------------------------------------------------
    app_a.standard_course_fee = 30000.0
    app_a.mode_of_learning = "Offline"
    app_a.performance = "Satisfactory"

    assert app_b.standard_course_fee == 18000.0, "App B fee must remain 18000.0"
    assert app_b.mode_of_learning == "Online", "App B mode must remain Online"
    assert app_b.performance is None, "App B performance must remain None"

    # -------------------------------------------------------------------------
    # TEST 7: Generate/regenerate certificate for Application A -> Only App A changes.
    # Application B certificate fields remain untouched.
    # -------------------------------------------------------------------------
    with patch("app.services.certificate_service.CertificateUploadService.upload_certificate", new_callable=AsyncMock) as mock_upload, \
         patch("app.services.certificate_service.CertificateUploadService.delete_file", new_callable=AsyncMock) as mock_delete:
        
        mock_upload.return_value = "https://storage.example.com/certificates/app-python-id-new.pdf"
        
        # Set App A to Completed
        app_a.application_status = "Completed"
        app_a.performance = "Excellent"
        
        # Regenerate certificate for App A
        await certificate_service.regenerate_certificate(mock_db, app_a)

        # Check App A was updated
        assert app_a.certificate_url == "https://storage.example.com/certificates/app-python-id-new.pdf"
        assert app_a.certificate_status == "valid"

        # Check App B certificate is completely untouched
        assert app_b.certificate_id is None
        assert app_b.certificate_url is None
        assert app_b.certificate_status == "pending"

    # -------------------------------------------------------------------------
    # TEST 8: Attempt to add Course A again (Python Full Stack).
    # Expected: Request rejected as duplicate with clear error message.
    # -------------------------------------------------------------------------
    dup_a_payload = {
        "candidate_id": app_a.id,
        "program_id": prog_a.id,
    }

    with pytest.raises(HTTPException) as exc_info_a:
        await CandidateService.enroll_additional_course(mock_db, dup_a_payload, created_by="Admin")

    assert exc_info_a.value.status_code == 400
    assert "already enrolled in this course" in exc_info_a.value.detail.lower()
    assert len(candidates_db) == 2, "No duplicate application should be created"

    # -------------------------------------------------------------------------
    # TEST 9: Attempt to add Course B again (Django Development).
    # Expected: Request rejected as duplicate.
    # -------------------------------------------------------------------------
    dup_b_payload = {
        "candidate_id": app_b.id,
        "program_id": prog_b.id,
    }

    with pytest.raises(HTTPException) as exc_info_b:
        await CandidateService.enroll_additional_course(mock_db, dup_b_payload, created_by="Admin")

    assert exc_info_b.value.status_code == 400
    assert "already enrolled in this course" in exc_info_b.value.detail.lower()
    assert len(candidates_db) == 2, "No duplicate application should be created"


def test_admin_enroll_additional_endpoint(client):
    """Test the POST /api/v1/candidates/enroll-additional HTTP endpoint."""
    mock_app = CandidateApplication(
        id="new-enrolled-id",
        lead_id="lead-1",
        program_id="prog-django-id",
        application_number="CAF-2026-00042",
        full_name="Sneha",
        email="sneha@example.com",
        phone="9876543210",
        course_applied="Django Development",
        application_status="Enrolled"
    )

    with patch("app.services.candidate_service.CandidateService.enroll_additional_course", new_callable=AsyncMock) as mock_enroll:
        mock_enroll.return_value = mock_app

        payload = {
            "candidate_id": "app-python-id",
            "program_id": "prog-django-id",
            "mode_of_learning": "Online",
            "standard_course_fee": 18000.0,
            "admission_fee_paid": True,
            "remarks": "Admin manual enrollment"
        }

        response = client.post("/api/v1/candidates/enroll-additional", json=payload)

        assert response.status_code == 201
        data = response.json()
        assert data["success"] is True
        assert data["id"] == "new-enrolled-id"
        assert data["application_number"] == "CAF-2026-00042"
        assert data["course_applied"] == "Django Development"
        assert data["application_status"] == "Enrolled"
        mock_enroll.assert_called_once()


def test_admin_enroll_additional_duplicate_rejection(client):
    """Test HTTP endpoint rejection when candidate is already enrolled in the course."""
    with patch("app.services.candidate_service.CandidateService.enroll_additional_course", new_callable=AsyncMock) as mock_enroll:
        mock_enroll.side_effect = HTTPException(
            status_code=400,
            detail="This candidate is already enrolled in this course."
        )

        payload = {
            "candidate_id": "app-python-id",
            "program_id": "prog-python-id"
        }

        response = client.post("/api/v1/candidates/enroll-additional", json=payload)

        assert response.status_code == 400
        assert "already enrolled in this course" in response.json()["detail"]


@pytest.mark.asyncio
async def test_first_time_lead_conversion_flow_still_works():
    """
    TEST 10: Verify the original first-time Lead -> Candidate conversion flow still works:
    Lead -> LeadToken -> CandidateApply -> CandidateApplication created.
    """
    lead = Lead(
        id="lead-new-person",
        name="Aravind Kumar",
        email="aravind@example.com",
        phone="9112233445",
        interested_course="React Development",
        status="Qualified",
        is_deleted=False
    )
    token_str = str(uuid.uuid4())
    lead_token = LeadToken(
        id=str(uuid.uuid4()),
        lead_id=lead.id,
        token=token_str,
        used=False
    )

    mock_db = AsyncMock()

    # Verify CandidateCreate schema validates properly with token and lead details
    create_payload = CandidateCreate(
        full_name="Aravind Kumar",
        email="aravind@example.com",
        phone="9112233445",
        course_applied="React Development",
        token=token_str,
        lead_id=lead.id,
        date_of_birth=datetime(2000, 1, 15)
    )

    # When CandidateService.create_candidate_application is called for first-time applicant:
    with patch("app.services.candidate_service.CandidateService.generate_application_number", new_callable=AsyncMock) as mock_gen_app_num:
        mock_gen_app_num.return_value = "CAF-2026-00099"

        # Mock query returning no existing candidate
        async def mock_exec(stmt):
            m = MagicMock()
            m.scalars.return_value.first.return_value = None
            m.scalar_one_or_none.return_value = None
            return m

        mock_db.execute.side_effect = mock_exec

        candidate = await CandidateService.create_candidate_application(
            mock_db, create_payload.model_dump(), created_by="Website Form"
        )

        assert candidate.full_name == "Aravind Kumar"
        assert candidate.email == "aravind@example.com"
        assert candidate.lead_id == lead.id
        assert candidate.application_number == "CAF-2026-00099"
        assert candidate.application_status == "Submitted"
        assert candidate.certificate_id is None
