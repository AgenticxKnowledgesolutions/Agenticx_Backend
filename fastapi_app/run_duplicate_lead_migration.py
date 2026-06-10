import os
import asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

# Load dotenv variables
env_path = "/home/fazilvk/Desktop/Agenticx-backend/fastapi_app/.env"
if os.path.exists(env_path):
    with open(env_path, "r") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("=", 1)
            if len(parts) == 2:
                os.environ[parts[0]] = parts[1]

DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL not found in environment!")

async def main():
    print("Connecting to database...")
    engine = create_async_engine(DATABASE_URL)
    queries = [
        # Alter table leads to add duplicate tracking & scoring columns
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS interaction_count INTEGER DEFAULT 1 NOT NULL;",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_interaction_at TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS first_source VARCHAR(100);",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS latest_source VARCHAR(100);",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS merged_courses JSONB DEFAULT '[]'::jsonb;",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS duplicate_hits INTEGER DEFAULT 0 NOT NULL;",
        "ALTER TABLE leads ADD COLUMN IF NOT EXISTS lead_score INTEGER DEFAULT 0 NOT NULL;",
        
        # Add indexes for performance optimization
        "CREATE INDEX IF NOT EXISTS ix_leads_phone ON leads (phone);",
        "CREATE INDEX IF NOT EXISTS ix_leads_created_at ON leads (created_at);",
        "CREATE INDEX IF NOT EXISTS ix_leads_is_deleted ON leads (is_deleted);",
        "CREATE INDEX IF NOT EXISTS ix_leads_last_interaction_at ON leads (last_interaction_at);",
        
        # Create lead_interactions table
        """
        CREATE TABLE IF NOT EXISTS lead_interactions (
            id VARCHAR PRIMARY KEY,
            lead_id VARCHAR NOT NULL REFERENCES leads (id) ON DELETE CASCADE,
            interaction_type VARCHAR(100) NOT NULL,
            source VARCHAR(100),
            course VARCHAR(255),
            notes TEXT,
            ip_address VARCHAR(45),
            created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
        );
        """,
        # Create index on lead_interactions lead_id for performance
        "CREATE INDEX IF NOT EXISTS ix_lead_interactions_lead_id ON lead_interactions (lead_id);"
    ]
    
    async with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q.strip()}")
            await conn.execute(text(q))
    print("Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
