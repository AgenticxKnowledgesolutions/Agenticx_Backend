import sys
import os
import asyncio
from datetime import datetime

# Add fastapi_app to sys.path
fastapi_app_path = "/home/fazilvk/Desktop/Agenticx-backend/fastapi_app"
sys.path.append(fastapi_app_path)

# Set dummy env variables
os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/db"
os.environ["SECRET_KEY"] = "secret"
os.environ["SUPABASE_URL"] = "https://mock.supabase.co"
os.environ["SUPABASE_SERVICE_KEY"] = "mockkey"

from unittest.mock import AsyncMock, MagicMock
from app.models.candidate_application import CandidateApplication
from app.models.program import Program
from app.services.certificate_service import CertificateService, get_course_details
import app.services.certificate_service as cs

async def test_extraction(course_name: str, program_type: str, file_name: str):
    # 1. Mock DB session
    mock_db = AsyncMock()
    
    # 2. Mock program
    program = Program(
        id=f"prog-{file_name}",
        name=course_name,
        program_type=program_type,
        certificate_template="participation" if program_type in ["FDP", "Workshop", "Webinar"] else "completion",
        duration="1 Week",
        mode="Online"
    )
    
    # 3. Mock candidate
    candidate = CandidateApplication(
        id=f"cand-{file_name}-id",
        application_number=f"CAF-2026-{file_name.upper()}",
        full_name="Fazil",
        email="fazil@example.com",
        phone="+919999999999",
        course_applied=course_name,
        program_type=program_type,
        program_id=program.id,
        course_start_date=datetime(2026, 6, 1),
        completed_at=datetime(2026, 6, 7),
        course_duration="1 Week",
        performance="Excellent",
        mode_of_learning="Online",
        gender="male",
        certificate_status="pending"
    )
    
    # 4. Mock the db.execute results to return the mock program when queried
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = program
    mock_db.execute.return_value = mock_result
    
    # 5. Mock the upload service to write the PDF locally
    pdf_path = f"/home/fazilvk/.gemini/antigravity/brain/309172f1-c87a-429f-a0f6-fbe44da5ce7b/{file_name}.pdf"
    
    async def mock_upload(self, file_content: bytes, candidate_id: str) -> str:
        with open(pdf_path, "wb") as f:
            f.write(file_content)
        print(f"Saved PDF to {pdf_path}")
        return f"file://{pdf_path}"
        
    cs.CertificateUploadService.upload_certificate = mock_upload
    
    # 6. Generate certificate
    await CertificateService.generate_and_save_certificate(mock_db, candidate)
    
    # 7. Print details
    details = get_course_details(course_name)
    print(f"Course Applied: {course_name}")
    print(f"  -> Resolved Domain: {details['domain']}")
    print(f"  -> Resolved Topics: {details['topics']}")
    print("-" * 60)

async def main():
    test_cases = [
        ("FDP in Cybersecurity", "FDP", "fdp_cybersecurity"),
        ("FDP in AI", "FDP", "fdp_ai"),
        ("FDP in Python", "FDP", "fdp_python"),
        ("FDP on Academic Writing", "FDP", "fdp_academic"),
        ("Workshop on Cloud Architecture", "Workshop", "workshop_cloud"),
        ("Unlisted Fallback Technology Course", "Course", "unlisted_course")
    ]
    
    for course, p_type, fname in test_cases:
        await test_extraction(course, p_type, fname)

if __name__ == "__main__":
    asyncio.run(main())
