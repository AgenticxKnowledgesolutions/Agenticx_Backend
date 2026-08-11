import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from app.models.candidate_application import CandidateApplication
from app.services.candidate_export_service import CandidateExportService


@pytest.mark.asyncio
async def test_csv_generation():
    rows = [
        [
            "CAF-2026-001", "John Doe", "John", "john@example.com", "9876543210",
            "9876543210", "Male", "2000-01-01", "B.Tech", "KTU", "GEC", "8.5", "2022",
            "Passed Out", "2", "TechCorp", "Python, React", "Full Stack Web Development",
            "Course", "Offline", "Enrolled", "XXXX XXXX 1234", "ABCDE1234F", "Kochi",
            "Ernakulam", "Ernakulam", "Kerala", 50000.0, 5000.0, "Yes", 45000.0, 0.0,
            "2026-08-01 10:00"
        ]
    ]

    content, filename, media_type = CandidateExportService._generate_csv(rows, "20260811")
    assert media_type == "text/csv"
    assert filename.endswith(".csv")
    decoded = content.decode("utf-8-sig")
    assert "Application No" in decoded
    assert "CAF-2026-001" in decoded
    assert "john@example.com" in decoded


@pytest.mark.asyncio
async def test_excel_generation():
    rows = [
        [
            "CAF-2026-002", "Jane Smith", "Jane", "jane@example.com", "9123456789",
            "9123456789", "Female", "2001-05-15", "B.Sc", "Calicut Univ", "Farook College", "80%", "2023",
            "Passed Out", "0", "", "Python, SQL", "AI and Machine Learning",
            "Course", "Online", "Submitted", "XXXX XXXX 5678", "", "Calicut",
            "Kozhikode", "Kozhikode", "Kerala", 40000.0, 0.0, "No", 5000.0, 35000.0,
            "2026-08-05 14:30"
        ]
    ]

    content, filename, media_type = CandidateExportService._generate_excel(rows, "20260811")
    assert media_type == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert filename.endswith(".xlsx")
    assert len(content) > 100  # Valid binary zip/xlsx output


@pytest.mark.asyncio
async def test_export_candidates_service():
    mock_db = AsyncMock()
    c1 = CandidateApplication(
        id="cand-1",
        application_number="CAF-2026-001",
        full_name="Alice Brown",
        email="alice@example.com",
        phone="9988776655",
        course_applied="Full Stack Web Development",
        application_status="Submitted",
        created_at=datetime.now(timezone.utc)
    )

    mock_res = MagicMock()
    mock_res.scalars.return_value.all.return_value = [c1]
    mock_db.execute.return_value = mock_res

    # Test scope == 'all', format == 'csv'
    csv_bytes, csv_name, csv_mime = await CandidateExportService.export_candidates(
        db=mock_db, scope="all", format_type="csv"
    )
    assert csv_mime == "text/csv"
    assert "CAF-2026-001" in csv_bytes.decode("utf-8-sig")

    # Test scope == 'filtered' with date bounds, format == 'xlsx'
    xlsx_bytes, xlsx_name, xlsx_mime = await CandidateExportService.export_candidates(
        db=mock_db,
        scope="filtered",
        status_filter="Submitted",
        start_date=datetime(2026, 1, 1),
        end_date=datetime(2026, 12, 31),
        format_type="xlsx"
    )
    assert xlsx_mime == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert len(xlsx_bytes) > 100
