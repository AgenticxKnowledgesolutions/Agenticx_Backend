import asyncio
import os
import sys

# Add project root to python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres.bkdursqkdyqmxhekcrau:Anjupramod*1984@aws-1-ap-south-1.pooler.supabase.com:6543/postgres")
os.environ.setdefault("SECRET_KEY", "agenticx-fastapi-secret-key-2024-please-change-in-production")

from app.core.database import AsyncSessionLocal
from app.models.candidate_application import CandidateApplication
from app.models.lead import Lead
from app.models.lead_token import LeadToken
from sqlalchemy import select, or_

async def main():
    async with AsyncSessionLocal() as db:
        # Get lead
        lead_id = "b555863a-e354-4509-a3bd-196ea56f4a07"
        stmt_l = select(Lead).where(Lead.id == lead_id)
        res_l = await db.execute(stmt_l)
        lead = res_l.scalar_one_or_none()
        if not lead:
            print("Lead not found")
            return
            
        print(f"Lead ID: {lead.id}")
        print(f"Name: {lead.name}")
        print(f"Email: {lead.email}")
        print(f"Phone: {lead.phone}")
        print(f"Status: {lead.status}")
        print(f"Is Deleted: {lead.is_deleted}")
        
        # Check CandidateApplication by lead_id
        stmt_c = select(CandidateApplication).where(CandidateApplication.lead_id == lead_id)
        res_c = await db.execute(stmt_c)
        candidates = res_c.scalars().all()
        print(f"\nCandidates with this lead_id ({len(candidates)}):")
        for c in candidates:
            print(f"  - ID: {c.id}, Name: {c.full_name}, Email: {c.email}, Phone: {c.phone}, is_deleted: {c.is_deleted}, DOB: {c.date_of_birth}")
            
        # Check CandidateApplication by email or phone
        stmt_cep = select(CandidateApplication).where(
            or_(
                CandidateApplication.email.ilike(lead.email),
                CandidateApplication.phone == lead.phone
            )
        )
        res_cep = await db.execute(stmt_cep)
        candidates_cep = res_cep.scalars().all()
        print(f"\nCandidates matching email or phone ({len(candidates_cep)}):")
        for c in candidates_cep:
            print(f"  - ID: {c.id}, Name: {c.full_name}, Email: {c.email}, Phone: {c.phone}, is_deleted: {c.is_deleted}, DOB: {c.date_of_birth}")

if __name__ == "__main__":
    asyncio.run(main())
