"""One-time script to seed the initial admin user in Supabase.
Run from fastapi_app/ directory:
    python seed_admin.py
"""
import asyncio
from app.core.database import AsyncSessionLocal
from app.services.auth_service import create_admin_user
from sqlalchemy import select
from app.models.user import User


async def main():
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.email == "agenticx@gmail.com"))
        existing = result.scalar_one_or_none()
        if existing:
            print("Admin user already exists — skipping.")
            return
        user = await create_admin_user(
            db,
            email="agenticx@gmail.com",
            username="agenticx",
            password="1234",
        )
        print(f"✅ Admin user created: {user.email} (id={user.id})")


if __name__ == "__main__":
    asyncio.run(main())
