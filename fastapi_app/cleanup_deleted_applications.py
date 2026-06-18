import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.job import JobApplication
from app.services.upload_service import upload_service


async def main():
    print("Starting cleanup of soft-deleted job applications...")
    async with AsyncSessionLocal() as db:
        # Query all applications where is_deleted is True
        result = await db.execute(
            select(JobApplication).where(JobApplication.is_deleted == True)
        )
        deleted_apps = result.scalars().all()

        if not deleted_apps:
            print("No soft-deleted applications found. Cleanup complete.")
            return

        print(f"Found {len(deleted_apps)} soft-deleted applications to prune.")
        count = 0
        for app in deleted_apps:
            # 1. Delete physical resume from Supabase Storage
            if app.resume_url:
                print(f"Deleting CV for {app.name} from storage...")
                success = await upload_service.delete_file(app.resume_url)
                if not success:
                    print(f"⚠️ Warning: Failed to delete CV file: {app.resume_url}")
            
            # 2. Delete database record
            print(f"Deleting application record for {app.name} (ID: {app.id})...")
            await db.delete(app)
            count += 1

        await db.commit()
        print(f"✅ Successfully pruned {count} soft-deleted applications and CV file attachments.")


if __name__ == "__main__":
    asyncio.run(main())
