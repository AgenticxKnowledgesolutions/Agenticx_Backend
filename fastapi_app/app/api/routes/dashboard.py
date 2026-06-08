from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.services import dashboard_service
from app.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary")
async def get_summary(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Retrieve aggregated Business Intelligence and Analytics summary for the Admin dashboard.
    (Admin credentials required)
    """
    return await dashboard_service.get_dashboard_summary(db)
