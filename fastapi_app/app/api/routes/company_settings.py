from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.company_settings import CompanySettingsUpdate, CompanySettingsResponse
from app.services import company_settings_service
from app.deps import require_admin
from app.models.user import User

router = APIRouter(prefix="/company-settings", tags=["company-settings"])


@router.get("", response_model=CompanySettingsResponse)
async def get_settings(db: AsyncSession = Depends(get_db)):
    """
    Get all public company and website settings.
    """
    return await company_settings_service.get_company_settings(db)


@router.put("", response_model=CompanySettingsResponse)
async def update_settings(
    data: CompanySettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_admin),
):
    """
    Update company and website settings (Admin only).
    """
    return await company_settings_service.update_company_settings(db, data)
