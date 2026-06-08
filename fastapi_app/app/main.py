from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.api.api_router import api_router
from app.api.routes import health


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown: dispose connection pool
    from app.core.database import engine
    await engine.dispose()


app = FastAPI(
    title="AgenticX API",
    description="FastAPI backend for AgenticX Knowledge Solutions",
    version="2.0.0",
    lifespan=lifespan,
)

# CORS — allow React dev server and production origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
app.include_router(health.router)
