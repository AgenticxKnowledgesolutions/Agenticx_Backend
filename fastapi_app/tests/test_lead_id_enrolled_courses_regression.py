"""
Regression tests for ENROLLED COURSES lead_id scoping bug.

Verifies:
1. GET /api/v1/candidates/?lead_id=<id>&limit=100 correctly filters by lead_id.
2. Each candidate sees only their own enrolled courses.
3. Applications from unrelated candidates are never mixed.
4. Non-matching or unknown lead_id returns 0 records (never falls back to entire database).
5. Empty-string lead_id does not leak all candidate records.
6. CandidateService.get_applications correctly applies lead_id filtering in SQL.
"""
import uuid
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models.candidate_application import CandidateApplication
from app.services.candidate_service import CandidateService
from app.deps import require_admin
from app.core.database import get_db


class MockAdminUser:
    id = "admin-test-user-id"
    email = "admin@agenticx.co.in"
    role = "admin"


@pytest.fixture
def mock_admin_client():
    app.dependency_overrides[require_admin] = lambda: MockAdminUser()
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_get_applications_lead_id_filtering_via_endpoint(mock_admin_client):
    """
    Integration test for GET /api/v1/candidates/?lead_id=<id>&limit=100
    Verifies that FastAPI correctly accepts the lead_id query parameter
    and returns only records matching that lead_id.
    """
    lead_a = "lead-student-a-uuid"
    lead_b = "lead-student-b-uuid"

    # Candidate A enrolled in 2 courses
    app_a1 = CandidateApplication(
        id="app-a1",
        lead_id=lead_a,
        application_number="CAF-2026-00001",
        full_name="Student A",
        email="student.a@example.com",
        phone="9876543210",
        course_applied="Python Full Stack",
        application_status="Enrolled",
        is_deleted=False,
        created_at=datetime.utcnow(),
    )
    app_a2 = CandidateApplication(
        id="app-a2",
        lead_id=lead_a,
        application_number="CAF-2026-00002",
        full_name="Student A",
        email="student.a@example.com",
        phone="9876543210",
        course_applied="Django Development",
        application_status="Enrolled",
        is_deleted=False,
        created_at=datetime.utcnow(),
    )

    # Candidate B enrolled in 1 course
    app_b1 = CandidateApplication(
        id="app-b1",
        lead_id=lead_b,
        application_number="CAF-2026-00003",
        full_name="Student B",
        email="student.b@example.com",
        phone="9123456789",
        course_applied="React Development",
        application_status="Enrolled",
        is_deleted=False,
        created_at=datetime.utcnow(),
    )

    # Legacy Candidate C with NULL lead_id
    app_c1 = CandidateApplication(
        id="app-c1",
        lead_id=None,
        application_number="CAF-2026-00004",
        full_name="Student C",
        email="student.c@example.com",
        phone="9988776655",
        course_applied="Data Analytics",
        application_status="Enrolled",
        is_deleted=False,
        created_at=datetime.utcnow(),
    )

    all_apps = [app_a1, app_a2, app_b1, app_c1]

    async def override_get_db():
        mock_session = AsyncMock()

        async def mock_execute(stmt):
            res = MagicMock()
            stmt_str = str(stmt)

            # Extract lead_id filter if present in compiled statement
            # In SQLAlchemy, compiled statement params contain lead_id
            params = {}
            if hasattr(stmt, "compile"):
                compiled = stmt.compile()
                params = getattr(compiled, "params", {})

            # Filter applications
            filtered = [a for a in all_apps if not a.is_deleted]
            if "lead_id_1" in params:
                req_lead_id = params["lead_id_1"]
                filtered = [a for a in filtered if a.lead_id == req_lead_id]
            elif "lead_id" in stmt_str and "lead-student-a-uuid" in stmt_str:
                filtered = [a for a in filtered if a.lead_id == lead_a]
            elif "lead_id" in stmt_str and "lead-student-b-uuid" in stmt_str:
                filtered = [a for a in filtered if a.lead_id == lead_b]
            elif "lead_id" in stmt_str and "__none__" in stmt_str:
                filtered = []
            elif "lead_id" in stmt_str and "non-existent-lead" in stmt_str:
                filtered = []

            if "count(" in stmt_str.lower():
                res.scalar.return_value = len(filtered)
            else:
                res.scalars.return_value.all.return_value = filtered
            return res

        mock_session.execute = AsyncMock(side_effect=mock_execute)
        yield mock_session

    app.dependency_overrides[get_db] = override_get_db

    # 1. Test Querying for Student A
    res_a = mock_admin_client.get(f"/api/v1/candidates/?lead_id={lead_a}&limit=100")
    assert res_a.status_code == 200, f"Expected 200, got {res_a.status_code}"
    data_a = res_a.json()
    assert data_a["total"] == 2
    assert len(data_a["records"]) == 2
    record_ids_a = {r["id"] for r in data_a["records"]}
    assert "app-a1" in record_ids_a
    assert "app-a2" in record_ids_a
    assert "app-b1" not in record_ids_a
    assert "app-c1" not in record_ids_a

    # 2. Test Querying for Student B
    res_b = mock_admin_client.get(f"/api/v1/candidates/?lead_id={lead_b}&limit=100")
    assert res_b.status_code == 200
    data_b = res_b.json()
    assert data_b["total"] == 1
    assert len(data_b["records"]) == 1
    assert data_b["records"][0]["id"] == "app-b1"
    assert data_b["records"][0]["course_applied"] == "React Development"

    # 3. Test Querying for Non-existent Lead
    res_none = mock_admin_client.get("/api/v1/candidates/?lead_id=non-existent-lead&limit=100")
    assert res_none.status_code == 200
    data_none = res_none.json()
    assert data_none["total"] == 0
    assert len(data_none["records"]) == 0

    # 4. Test Querying with Empty String lead_id
    res_empty = mock_admin_client.get("/api/v1/candidates/?lead_id=&limit=100")
    assert res_empty.status_code == 200
    data_empty = res_empty.json()
    assert data_empty["total"] == 0
    assert len(data_empty["records"]) == 0


@pytest.mark.asyncio
async def test_candidate_service_get_applications_lead_id_clause():
    """
    Direct service unit test verifying that CandidateService.get_applications
    adds the exact lead_id filter to the SQLAlchemy statement.
    """
    mock_db = AsyncMock()
    executed_stmts = []

    async def mock_execute(stmt):
        executed_stmts.append(stmt)
        res = MagicMock()
        res.scalar.return_value = 1
        app_mock = CandidateApplication(
            id="app-1",
            lead_id="test-lead-id",
            application_number="CAF-2026-00001",
            full_name="Test Student",
            email="test@example.com",
            phone="9876543210",
            course_applied="Python Full Stack",
            application_status="Enrolled",
            is_deleted=False,
            created_at=datetime.utcnow(),
        )
        res.scalars.return_value.all.return_value = [app_mock]
        return res

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    result = await CandidateService.get_applications(mock_db, lead_id="test-lead-id", limit=100)
    assert len(result["records"]) == 1

    # Verify that the executed SELECT statements contain the lead_id constraint
    assert len(executed_stmts) == 2  # select query + count query
    for stmt in executed_stmts:
        compiled = stmt.compile()
        params = getattr(compiled, "params", {})
        assert "lead_id_1" in params
        assert params["lead_id_1"] == "test-lead-id"


@pytest.mark.asyncio
async def test_candidate_service_get_applications_empty_lead_id_safety():
    """
    Direct service unit test verifying that an empty-string or whitespace lead_id
    does not bypass filtering and never returns unconstrained candidate pool.
    """
    mock_db = AsyncMock()
    executed_stmts = []

    async def mock_execute(stmt):
        executed_stmts.append(stmt)
        res = MagicMock()
        res.scalar.return_value = 0
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = AsyncMock(side_effect=mock_execute)

    result = await CandidateService.get_applications(mock_db, lead_id="   ", limit=100)
    assert result["total"] == 0
    assert len(result["records"]) == 0

    # Verify that the executed statement filtered by sentinel "__none__"
    for stmt in executed_stmts:
        compiled = stmt.compile()
        params = getattr(compiled, "params", {})
        assert params.get("lead_id_1") == "__none__"


def test_enroll_additional_course_with_frontend_payload(mock_admin_client):
    """
    Regression: Frontend sends { lead_id, new_program_id }.
    Backend must accept this payload and NOT return HTTP 422 Unprocessable Content.
    """
    mock_app = CandidateApplication(
        id="new-enrolled-app-id",
        lead_id="lead-student-a-uuid",
        program_id="prog-django-id",
        application_number="CAF-2026-00099",
        full_name="Student A",
        email="student.a@example.com",
        phone="9876543210",
        course_applied="Django Development",
        application_status="Enrolled"
    )

    from unittest.mock import patch
    with patch("app.services.candidate_service.CandidateService.enroll_additional_course", new_callable=AsyncMock) as mock_enroll:
        mock_enroll.return_value = mock_app

        frontend_payload = {
            "lead_id": "lead-student-a-uuid",
            "new_program_id": "prog-django-id"
        }

        response = mock_admin_client.post("/api/v1/candidates/enroll-additional", json=frontend_payload)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert data["id"] == "new-enrolled-app-id"
        assert data["lead_id"] == "lead-student-a-uuid"
        assert data["application_number"] == "CAF-2026-00099"
        assert data["course_applied"] == "Django Development"
        assert data["program_id"] == "prog-django-id"

        # Verify that mock_enroll received the normalized payload
        called_payload = mock_enroll.call_args[0][1]
        assert called_payload["lead_id"] == "lead-student-a-uuid"
        assert called_payload["program_id"] == "prog-django-id"


def test_enroll_additional_course_with_backend_payload(mock_admin_client):
    """
    Regression: Backend callers and existing tests send { candidate_id, program_id }.
    Backend must continue to accept this format.
    """
    mock_app = CandidateApplication(
        id="new-enrolled-app-2",
        lead_id="lead-student-b-uuid",
        program_id="prog-react-id",
        application_number="CAF-2026-00100",
        full_name="Student B",
        email="student.b@example.com",
        phone="9123456789",
        course_applied="React Development",
        application_status="Enrolled"
    )

    from unittest.mock import patch
    with patch("app.services.candidate_service.CandidateService.enroll_additional_course", new_callable=AsyncMock) as mock_enroll:
        mock_enroll.return_value = mock_app

        backend_payload = {
            "candidate_id": "app-b1",
            "program_id": "prog-react-id",
            "mode_of_learning": "Online"
        }

        response = mock_admin_client.post("/api/v1/candidates/enroll-additional", json=backend_payload)

        assert response.status_code == 201, f"Expected 201, got {response.status_code}: {response.text}"
        data = response.json()
        assert data["success"] is True
        assert data["id"] == "new-enrolled-app-2"


def test_enroll_additional_course_schema_validation_rejects_missing_fields(mock_admin_client):
    """
    Validation test: If both candidate_id and lead_id are missing, or program_id and new_program_id
    are missing, HTTP 422 is returned.
    """
    # Missing candidate/lead identifier
    res1 = mock_admin_client.post("/api/v1/candidates/enroll-additional", json={"program_id": "prog-1"})
    assert res1.status_code == 422

    # Missing program identifier
    res2 = mock_admin_client.post("/api/v1/candidates/enroll-additional", json={"lead_id": "lead-1"})
    assert res2.status_code == 422


@pytest.mark.asyncio
async def test_enroll_additional_course_service_lead_id_resolution():
    """
    Direct service test: Verify enroll_additional_course finds the base candidate by lead_id.
    """
    from app.models.program import Program
    from fastapi import HTTPException

    base_candidate = CandidateApplication(
        id="app-existing-id",
        lead_id="lead-existing-uuid",
        application_number="CAF-2026-00001",
        full_name="Sneha",
        email="sneha@example.com",
        phone="9876543210",
        course_applied="Python Full Stack",
        program_id="prog-python-id",
        is_deleted=False
    )
    new_program = Program(
        id="prog-django-id",
        name="Django Development",
        program_type="Course",
        standard_fee=18000.0,
        is_deleted=False
    )
    python_program = Program(
        id="prog-python-id",
        name="Python Full Stack",
        program_type="Course",
        standard_fee=15000.0,
        is_deleted=False
    )

    mock_db = AsyncMock()

    async def mock_execute(stmt):
        res = MagicMock()
        stmt_str = str(stmt)
        if "FROM programs" in stmt_str:
            compiled = stmt.compile()
            params = getattr(compiled, "params", {})
            prog_id = params.get("id_1") or params.get("param_1")
            if prog_id == "prog-python-id" or "prog-python-id" in stmt_str:
                res.scalar_one_or_none.return_value = python_program
            else:
                res.scalar_one_or_none.return_value = new_program
            return res
        if "candidate_applications.lead_id" in stmt_str or "candidate_applications.id" in stmt_str:
            # Return base candidate
            res.scalar_one_or_none.return_value = base_candidate
            res.scalars.return_value.first.return_value = base_candidate
            res.scalars.return_value.all.return_value = [base_candidate]
            return res
        res.scalar_one_or_none.return_value = None
        res.scalars.return_value.all.return_value = []
        return res

    mock_db.execute = AsyncMock(side_effect=mock_execute)
    mock_db.flush = AsyncMock()
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.add = MagicMock()

    # Call with lead_id & new_program_id (frontend payload)
    new_app = await CandidateService.enroll_additional_course(
        mock_db,
        {"lead_id": "lead-existing-uuid", "new_program_id": "prog-django-id"},
        created_by="Admin"
    )

    assert new_app.lead_id == "lead-existing-uuid"
    assert new_app.course_applied == "Django Development"
    assert new_app.program_id == "prog-django-id"
    assert new_app.full_name == "Sneha"
    assert new_app.email == "sneha@example.com"
    assert new_app.phone == "9876543210"

    # Attempt duplicate enrollment -> must raise HTTPException 400
    with pytest.raises(HTTPException) as exc_info:
        await CandidateService.enroll_additional_course(
            mock_db,
            {"lead_id": "lead-existing-uuid", "new_program_id": "prog-python-id"},  # Already enrolled
            created_by="Admin"
        )
    assert exc_info.value.status_code == 400
    assert "already enrolled in this course" in exc_info.value.detail.lower()
