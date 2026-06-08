import asyncio
import sys
from sqlalchemy import text
sys.path.append("/home/fazilvk/Desktop/Agenticx-backend/fastapi_app")

from app.core.database import engine

async def alter_table():
    print("Connecting to database engine...")
    async with engine.begin() as conn:
        print("Executing ALTER TABLE statements for leads table...")
        
        # Add last_contacted_at
        await conn.execute(text(
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS last_contacted_at TIMESTAMP WITH TIME ZONE;"
        ))
        
        # Add next_followup_date
        await conn.execute(text(
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS next_followup_date TIMESTAMP WITH TIME ZONE;"
        ))
        
        # Add followup_notes
        await conn.execute(text(
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS followup_notes TEXT;"
        ))
        
        # Add source
        await conn.execute(text(
            "ALTER TABLE leads ADD COLUMN IF NOT EXISTS source VARCHAR(50) DEFAULT 'Website';"
        ))
        
        print("Success! Alter commands executed.")

if __name__ == "__main__":
    asyncio.run(alter_table())
