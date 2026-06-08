from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from app.models.user import User
from app.core.security import verify_password, hash_password, create_access_token, create_refresh_token


async def authenticate_user(db: AsyncSession, identifier: str, password: str) -> User | None:
    """Accepts email or username — mirrors existing Django EmailBackend behaviour."""
    result = await db.execute(
        select(User).where(
            or_(
                User.email.ilike(identifier),
                User.username.ilike(identifier),
            )
        )
    )
    user = result.scalar_one_or_none()
    if not user or not verify_password(password, user.hashed_password):
        return None
    return user


async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_admin_user(db: AsyncSession, email: str, username: str, password: str) -> User:
    user = User(
        email=email,
        username=username,
        hashed_password=hash_password(password),
        role="admin",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


def build_tokens(user: User) -> dict:
    return {
        "access_token": create_access_token(subject=user.id, role=user.role.value),
        "refresh_token": create_refresh_token(subject=user.id),
        "token_type": "bearer",
    }
