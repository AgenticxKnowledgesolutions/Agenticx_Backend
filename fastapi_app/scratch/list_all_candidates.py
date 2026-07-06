import asyncio
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres.bkdursqkdyqmxhekcrau:Anjupramod*1984@aws-1-ap-south-1.pooler.supabase.com:6543/postgres")
os.environ.setdefault("SECRET_KEY", "agenticx-fastapi-secret-key-2024-please-change-in-production")

from app.core.database import AsyncSessionLocal
from app.models.candidate_application import CandidateApplication
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        stmt = select(CandidateApplication)
        res = await db.execute(stmt)
        candidates = res.scalars().all()
        print(f"Total: {len(candidates)}")
        for c in candidates:
            print(f"ID: {c.id}, Name: {c.full_name}, Email: {c.email}, Phone: {c.phone}, Deleted: {c.is_deleted}")

if __name__ == "__main__":
    asyncio.run(main())
