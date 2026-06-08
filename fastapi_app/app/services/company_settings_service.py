from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.company_settings import CompanySettings
from app.schemas.company_settings import CompanySettingsUpdate


async def get_company_settings(db: AsyncSession) -> CompanySettings:
    """
    Get the singleton CompanySettings record. If it doesn't exist,
    create it with default seed values.
    """
    result = await db.execute(select(CompanySettings).where(CompanySettings.id == 1))
    settings = result.scalars().first()

    if not settings:
        # Create default settings
        settings = CompanySettings(
            id=1,
            company_name="AgenticX Knowledge Solutions",
            company_tagline="Bridging Education and Industry",
            company_description=(
                "Transforming fresh graduates into industry-ready professionals through "
                "effective career coaching and comprehensive graduate training."
            ),
            primary_phone="+91 9496552094",
            secondary_phone="+91 9496852094",
            primary_email="anju.muraleedharan@agenticx.co.in",
            secondary_email="agenticxknowledgesolutions@gmail.com",
            website_url="https://agenticx.co.in",
            address_line_1="3rd Floor, Raj Plaza",
            address_line_2="Town Limit",
            city="Kollam",
            state="Kerala",
            country="India",
            postal_code="691001",
            google_maps_url=(
                "https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d246.36208069536437!"
                "2d76.61254242851638!3d8.898800762722871!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!"
                "4f13.1!3m3!1m2!1s0x3b05fd109874a36b%3A0x26d35fe01fea3245!2sAgenticX%20Knowledge"
                "%20Solutions%20LLP!5e0!3m2!1sen!2sin!4v1779083931591!5m2!1sen!2sin"
            ),
            placement_assistance_percentage=100,
            college_partners_count=20,
            graduates_trained_count=250,
            students_trained_count=100,
            core_services_count=5,
            linkedin_url="https://linkedin.com/company/agenticx",
            instagram_url="https://instagram.com/agenticx",
            facebook_url="https://facebook.com/agenticx",
            youtube_url="https://youtube.com/agenticx",
            whatsapp_number="+919496552094",
            hero_title="Decode Data. Develop Systems. Drive Business.",
            hero_description=(
                "Transforming fresh graduates into industry-ready professionals through "
                "effective career coaching and comprehensive graduate training."
            ),
            hero_primary_cta_text="Explore Courses",
            hero_secondary_cta_text="Book Free Demo",
            meta_title="AgenticX | AI-Optimized Graduate Training & Placements",
            meta_description=(
                "Bridging the gap between education and industry through HTD "
                "(Hire-Train-Deploy) models and custom curriculum."
            ),
            meta_keywords="AI, Machine Learning, Data Science, MERN stack, Python, HTD, Placements"
        )
        db.add(settings)
        await db.commit()
        await db.refresh(settings)

    return settings


async def update_company_settings(
    db: AsyncSession, settings_data: CompanySettingsUpdate
) -> CompanySettings:
    """
    Update the singleton CompanySettings record.
    """
    settings = await get_company_settings(db)
    
    update_data = settings_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(settings, field, value)
        
    db.add(settings)
    await db.commit()
    await db.refresh(settings)
    return settings
