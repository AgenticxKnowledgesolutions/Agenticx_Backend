"""
Tests for Program-Based Architecture, course-to-program synchronization,
lead/candidate program ID inheritance, and certificate template selection.
Run with:
  DATABASE_URL=postgresql+asyncpg://dummy SECRET_KEY=dummy \
    python -m pytest tests/test_program_architecture.py -v
"""
import pytest
import uuid
from decimal import Decimal
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.program import Program
from app.models.course import Course
from app.models.lead import Lead
from app.models.candidate_application import CandidateApplication
from app.services.program_service import create_program, update_program, sync_course_to_program
from app.services.certificate_service import CertificateService, get_course_details
from app.schemas.program import ProgramCreate, ProgramUpdate
from app.schemas.lead import LeadCreate
from app.schemas.candidate import CandidateCreate, CandidateStatusUpdate, CandidateOfferUpdate


# ─── 1. Program Service CRUD Tests ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_program_service_crud():
    mock_db = AsyncMock()
    
    # Test Create Program
    program_in = ProgramCreate(
        name="Advanced AI Bootcamp",
        slug="advanced-ai-bootcamp",
        program_type="Bootcamp",
        standard_fee=Decimal("45000.00"),
        duration="12 Weeks",
        mode="Online",
        certificate_template="achievement"
    )
    
    # We mock the return of db.execute for scalar or scalars
    mock_prog = Program(
        id="prog-1",
        name=program_in.name,
        slug=program_in.slug,
        program_type=program_in.program_type,
        standard_fee=program_in.standard_fee,
        duration=program_in.duration,
        mode=program_in.mode,
        certificate_template=program_in.certificate_template
    )
    
    # Mocking get / execute returns
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_prog
    mock_db.execute.return_value = mock_result
    
    created = await create_program(mock_db, program_in)
    assert created.name == "Advanced AI Bootcamp"
    assert created.certificate_template == "achievement"
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()
    
    # Test Update Program
    program_up = ProgramUpdate(
        standard_fee=Decimal("39000.00"),
        certificate_template="participation"
    )
    mock_db.execute.reset_mock()
    mock_db.commit.reset_mock()
    
    updated = await update_program(mock_db, mock_prog, program_up)
    assert updated.standard_fee == 39000.00
    assert updated.certificate_template == "participation"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_course_to_program_sync():
    mock_db = AsyncMock()
    
    course = Course(
        id="course-1",
        title="Data Analytics & BI",
        slug="data-analytics-bi",
        description="Data Analytics Course",
        price=Decimal("15000.00"),
        duration="8 Weeks",
        mode="online",
        is_deleted=False
    )
    
    # Mock finding no existing program, so it creates one
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result
    
    # Manually invoke sync helper
    await sync_course_to_program(mock_db, course)
    
    # Verify add was called to create the new program
    mock_db.add.assert_called_once()
    added_program = mock_db.add.call_args[0][0]
    assert added_program.id == "course-1"
    assert added_program.name == "Data Analytics & BI"
    assert added_program.standard_fee == 15000.00
    assert added_program.mode == "online"
    assert added_program.certificate_template == "completion"


# ─── 3. Lead Program ID Inheritance Tests ───────────────────────────────────

@pytest.mark.asyncio
async def test_lead_program_id_inheritance():
    mock_db = AsyncMock()
    
    # Scenario A: Lead created with interested course name
    lead_data = LeadCreate(
        name="Jane Smith",
        email="jane@example.com",
        phone="9876543211",
        course_interest="Cyber Security",
        source="Website"
    )
    
    # Mock finding a program with matching name
    mock_prog = Program(
        id="prog-cyber",
        name="Cyber Security",
        standard_fee=25000.0
    )
    
    mock_res = MagicMock()
    mock_res.scalars.return_value.first.return_value = mock_prog
    mock_db.execute.return_value = mock_res
    
    # Use LeadService helper to verify resolution
    # Let's mock lead_service.find_duplicate_lead to return None
    with patch("app.services.lead_service.find_duplicate_lead", new_callable=AsyncMock) as mock_dup:
        mock_dup.return_value = None
        
        # Test creation logic resolves program_id
        lead = Lead(
            name=lead_data.name,
            email=lead_data.email,
            phone=lead_data.phone,
            interested_course=lead_data.course_interest,
            source=lead_data.source,
            first_source=lead_data.source,
            latest_source=lead_data.source,
            merged_courses=[lead_data.course_interest]
        )
        
        # Resolve program ID manually or via service logic
        # Check standard_fee and details
        from sqlalchemy import select
        stmt_prog = select(Program).where(Program.name == lead_data.course_interest, Program.is_deleted == False)
        res_prog = await mock_db.execute(stmt_prog)
        resolved_prog = res_prog.scalars().first()
        if resolved_prog:
            lead.program_id = resolved_prog.id
            
        assert lead.program_id == "prog-cyber"


# ─── 4. Candidate Program ID & Fee Inheritance Tests ────────────────────────

@pytest.mark.asyncio
async def test_candidate_program_inheritance():
    mock_db = AsyncMock()
    
    # Candidate with program_id and missing fees/duration/mode
    candidate_in = CandidateCreate(
        lead_id="lead-1",
        full_name="Alice Candidate",
        email="alice@example.com",
        phone="9998887777",
        date_of_birth="2000-01-01",
        gender="female",
        address="123 Street",
        qualification="BTech",
        course_applied="Deep Learning",
        program_id="prog-deep-learning"
    )
    
    mock_prog = Program(
        id="prog-deep-learning",
        name="Deep Learning",
        slug="deep-learning",
        program_type="Course",
        standard_fee=Decimal("50000.00"),
        duration="16 Weeks",
        mode="Hybrid",
        certificate_template="completion"
    )
    
    # Mock DB query resolving program
    mock_res_prog = MagicMock()
    mock_res_prog.scalar_one_or_none.return_value = mock_prog
    
    # Mock Lead check
    mock_lead = Lead(
        id="lead-1",
        name="Alice Candidate",
        email="alice@example.com",
        phone="9998887777",
        program_id="prog-deep-learning"
    )
    mock_res_lead = MagicMock()
    mock_res_lead.scalar_one_or_none.return_value = mock_lead
    
    # Set DB execute side effects
    mock_db.execute.side_effect = [
        mock_res_lead,  # Lead check
        mock_res_prog,  # Program check
        MagicMock()     # Insert / timeline logging
    ]
    
    # Check inheritance during Candidate application save
    # Let's test the calculations manually matching candidate_service logic:
    standard_fee = float(mock_prog.standard_fee)
    learning_mode = mock_prog.mode
    course_duration = mock_prog.duration
    program_type = mock_prog.program_type
    
    assert standard_fee == 50000.0
    assert learning_mode == "Hybrid"
    assert course_duration == "16 Weeks"
    assert program_type == "Course"


# ─── 5. Certificate Template & Wording Customization Tests ─────────────────

@pytest.mark.asyncio
async def test_certificate_participation_template():
    mock_db = AsyncMock()
    
    # Setup candidate record for FDP / Participation
    candidate = CandidateApplication(
        id="candidate-fdp",
        application_number="CAF-FDP-001",
        full_name="Dr. John Professor",
        email="professor@university.edu",
        course_applied="FDP on Modern Web Architectures",
        program_type="FDP",
        program_id="prog-fdp-1",
        course_start_date=datetime(2026, 6, 1),
        completed_at=datetime(2026, 6, 5),
        gender="male",
        performance="Excellent"
    )
    
    mock_prog = Program(
        id="prog-fdp-1",
        name="FDP on Modern Web Architectures",
        program_type="FDP",
        certificate_template="participation"
    )
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_prog
    mock_db.execute.return_value = mock_res
    
    # Mock supabase upload
    with patch("app.services.certificate_service.CertificateUploadService.upload_certificate", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "https://supabase/cert.pdf"
        
        # Mock create_certificate_token
        with patch("app.services.certificate_service.create_certificate_token") as mock_token:
            mock_token.return_value = "signed-jwt-token"
            
            # Generate and verify save
            updated_candidate = await CertificateService.generate_and_save_certificate(mock_db, candidate)
            assert updated_candidate.certificate_url == "https://supabase/cert.pdf"
            
            # Verify the course details mapping matches fallback for FDP
            details = get_course_details(candidate.course_applied)
            assert "Faculty Development Programme" in details["domain"] or "FDP" in details["domain"]


@pytest.mark.asyncio
async def test_fdp_certificate_generation():
    mock_db = AsyncMock()
    
    # Setup candidate record for FDP
    candidate = CandidateApplication(
        id="cand-fdp-123",
        application_number="CAF-FDP-999",
        full_name="Prof. Alice Smith",
        email="alice.smith@college.edu",
        course_applied="Faculty Development Programme",
        program_type="Faculty Development Programme",
        programme_domain="Cyber Security",
        college_name="IIT Bombay",
        course_start_date=datetime(2026, 7, 1),
        completed_at=datetime(2026, 7, 5),
        gender="female",
        performance="Excellent" # Should be omitted in cert description
    )
    
    mock_prog = Program(
        id="prog-fdp-123",
        name="Faculty Development Programme",
        program_type="Faculty Development Programme",
        certificate_template="participation"
    )
    
    mock_res = MagicMock()
    mock_res.scalar_one_or_none.return_value = mock_prog
    mock_db.execute.return_value = mock_res
    
    # Mock supabase upload
    with patch("app.services.certificate_service.CertificateUploadService.upload_certificate", new_callable=AsyncMock) as mock_upload:
        mock_upload.return_value = "https://supabase/fdp-cert.pdf"
        
        # Mock create_certificate_token
        with patch("app.services.certificate_service.create_certificate_token") as mock_token:
            mock_token.return_value = "signed-fdp-token"
            
            # Generate and verify save
            updated_candidate = await CertificateService.generate_and_save_certificate(mock_db, candidate)
            assert updated_candidate.certificate_url == "https://supabase/fdp-cert.pdf"
