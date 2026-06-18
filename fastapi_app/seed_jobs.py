import asyncio
from app.core.database import AsyncSessionLocal
from sqlalchemy import select
from app.models.job import Job


async def main():
    async with AsyncSessionLocal() as db:
        # Check if any jobs exist
        result = await db.execute(select(Job))
        existing_jobs = result.scalars().all()
        if existing_jobs:
            print("Jobs already exist in the database — skipping seeding.")
            return

        jobs = [
            Job(
                title="AI Agent Solutions Architect",
                description="We are looking for a senior architect to design and deploy enterprise-level AI agent frameworks. You will work with LangGraph, LangChain, AutoGen, and custom multi-agent orchestration layers. Experience with FastAPI, vector databases (PGVector, Pinecone), and streaming architectures is highly desired."
            ),
            Job(
                title="Frontend Engineer (React / Three.js)",
                description="Join us in crafting stunning, premium user interfaces for our AI tools. You will lead the design and implementation of modern React components, complex state management using Zustand, and interactive data/network visualizations using Three.js and Canvas elements."
            ),
            Job(
                title="Full-Stack Developer",
                description="Looking for a versatile developer who can bridge the gap between high-performance FastAPI backends and responsive React applications. You will be responsible for end-to-end feature delivery, designing secure APIs, optimizing database queries, and styling clean minimal UIs."
            )
        ]

        for job in jobs:
            db.add(job)
        await db.commit()
        print(f"✅ Successfully seeded {len(jobs)} active job positions.")


if __name__ == "__main__":
    asyncio.run(main())
