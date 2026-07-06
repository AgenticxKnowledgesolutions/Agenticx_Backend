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
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        # Get count of candidate applications
        stmt = select(CandidateApplication)
        res = await db.execute(stmt)
        candidates = res.scalars().all()
        print(f"Total candidate applications: {len(candidates)}")
        
        deleted_candidates = [c for c in candidates if c.is_deleted]
        print(f"Soft-deleted candidates: {len(deleted_candidates)}")
        for c in deleted_candidates[:10]:
            print(f"  - ID: {c.id}, Email: {c.email}, Phone: {c.phone}, App Num: {c.application_number}")
            
        print("\nLeads status counts:")
        stmt_l = select(Lead)
        res_l = await db.execute(stmt_l)
        leads = res_l.scalars().all()
        print(f"Total leads: {len(leads)}")
        
        status_counts = {}
        for l in leads:
            status_counts[l.status] = status_counts.get(l.status, 0) + 1
        print(status_counts)

if __name__ == "__main__":
    asyncio.run(main())
