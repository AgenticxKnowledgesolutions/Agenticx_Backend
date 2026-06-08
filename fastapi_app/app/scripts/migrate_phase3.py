import asyncio
import os
import sys

# Ensure app is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import engine
from sqlalchemy import text

async def migrate():
    statements = [
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS priority VARCHAR(20) NOT NULL DEFAULT 'Cold'",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS assigned_to VARCHAR(50) NULL",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN NOT NULL DEFAULT FALSE",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ NULL",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS deleted_by VARCHAR(50) NULL",
        """
        CREATE TABLE IF NOT EXISTS lead_notes (
            id VARCHAR PRIMARY KEY,
            lead_id VARCHAR NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            content TEXT NOT NULL,
            created_by VARCHAR NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS lead_timeline (
            id VARCHAR PRIMARY KEY,
            lead_id VARCHAR NOT NULL REFERENCES leads(id) ON DELETE CASCADE,
            event_type VARCHAR(50) NOT NULL,
            description TEXT NOT NULL,
            created_by VARCHAR NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_lead_notes_lead_id ON lead_notes(lead_id)",
        "CREATE INDEX IF NOT EXISTS idx_lead_timeline_lead_id ON lead_timeline(lead_id)"
    ]
    
    print("Running database migration for CRM Phase 3...")
    async with engine.begin() as conn:
        for stmt in statements:
            stmt = stmt.strip()
            if stmt:
                await conn.execute(text(stmt))
    print("Migration completed successfully!")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(migrate())
