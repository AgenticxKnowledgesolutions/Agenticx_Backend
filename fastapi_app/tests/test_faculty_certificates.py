import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

from app.models.faculty_certificate import FacultyCertificate
from app.schemas.faculty_certificate import FacultyCertificateCreate, FacultyCertificateUpdate
from app.services.faculty_certificate_service import FacultyCertificateService


def test_faculty_certificate_schema_valid_dates():
    # Valid start/end dates
    payload = {
        "faculty_name": "Dr. Sarah Connor",
        "faculty_email": "sarah@example.com",
        "start_date": datetime(2026, 8, 1),
        "end_date": datetime(2026, 8, 5),
        "duration": "5 Days",
        "programme_title": "Faculty Development Programme",
        "topic": "Artificial Intelligence & Machine Learning"
    }
    create_schema = FacultyCertificateCreate(**payload)
    assert create_schema.faculty_name == "Dr. Sarah Connor"


def test_faculty_certificate_schema_invalid_dates():
    # End date before start date
    payload = {
        "faculty_name": "Dr. Sarah Connor",
        "faculty_email": "sarah@example.com",
        "start_date": datetime(2026, 8, 5),
        "end_date": datetime(2026, 8, 1),
        "duration": "5 Days",
        "programme_title": "Faculty Development Programme",
        "topic": "Artificial Intelligence & Machine Learning"
    }
    with pytest.raises(ValidationError):
        FacultyCertificateCreate(**payload)


@pytest.mark.asyncio
async def test_faculty_certificate_number_generation():
    mock_db = AsyncMock()
    mock_res = MagicMock()
    mock_res.scalar.return_value = 5  # Already 5 certificates exist
    mock_db.execute.return_value = mock_res

    payload = FacultyCertificateCreate(
        faculty_name="Prof. Sarah Connor",
        faculty_email="sarah@example.com",
        designation="Professor",
        organization="MIT",
        programme_title="Faculty Development Programme",
        topic="Artificial Intelligence & Machine Learning",
        start_date=datetime(2026, 8, 1),
        end_date=datetime(2026, 8, 5),
        duration="5 Days",
        mode="Online"
    )

    cert = await FacultyCertificateService.create_certificate(mock_db, payload)
    
    # Assert generated certificate number matches FDP-{year}-00006
    current_year = datetime.now().year
    assert cert.certificate_number == f"FDP-{current_year}-00006"
    assert cert.status == "Draft"
    assert cert.faculty_name == "Prof. Sarah Connor"


@pytest.mark.asyncio
async def test_faculty_certificate_pdf_generation():
    cert = FacultyCertificate(
        id="cert-uuid-1",
        certificate_number="FDP-2026-00001",
        faculty_name="Dr. Sarah Connor",
        programme_title="Faculty Development Programme",
        topic="Artificial Intelligence & Machine Learning",
        start_date=datetime(2026, 8, 1),
        end_date=datetime(2026, 8, 5),
        duration="5 Days",
        mode="Online",
        organization_name="AgenticX Knowledge Solutions LLP",
        signatory_name="Anju Muraleedharan",
        signatory_designation="Managing Partner",
        status="Draft"
    )

    pdf_bytes = FacultyCertificateService.generate_pdf_bytes(cert)
    assert len(pdf_bytes) > 100  # Valid PDF output has header signature %PDF-
    assert pdf_bytes.startswith(b"%PDF")
