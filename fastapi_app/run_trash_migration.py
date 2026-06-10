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
    print(f"Connecting to database...")
    engine = create_async_engine(DATABASE_URL)
    queries = [
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;",
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE courses ADD COLUMN IF NOT EXISTS deleted_by VARCHAR(50);",
        
        "ALTER TABLE activities ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;",
        "ALTER TABLE activities ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE activities ADD COLUMN IF NOT EXISTS deleted_by VARCHAR(50);",
        
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS is_deleted BOOLEAN DEFAULT FALSE NOT NULL;",
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP WITH TIME ZONE;",
        "ALTER TABLE reviews ADD COLUMN IF NOT EXISTS deleted_by VARCHAR(50);"
    ]
    
    async with engine.begin() as conn:
        for q in queries:
            print(f"Executing: {q}")
            await conn.execute(text(q))
    print("Migration completed successfully!")

if __name__ == "__main__":
    asyncio.run(main())
