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
from sqlalchemy import select

async def main():
    async with AsyncSessionLocal() as db:
        # Get count of lead tokens
        stmt = select(LeadToken)
        res = await db.execute(stmt)
        tokens = res.scalars().all()
        print(f"Total lead tokens: {len(tokens)}")
        
        used_tokens = [t for t in tokens if t.used]
        unused_tokens = [t for t in tokens if not t.used]
        print(f"Used tokens: {len(used_tokens)}")
        print(f"Unused tokens: {len(unused_tokens)}")
        for t in unused_tokens[:10]:
            print(f"  - Token: {t.token}, Lead ID: {t.lead_id}, Used: {t.used}")

if __name__ == "__main__":
    asyncio.run(main())
