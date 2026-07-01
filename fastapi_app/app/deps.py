from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import decode_token
from app.services.auth_service import get_user_by_id
from app.models.user import User

bearer_scheme = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    token = credentials.credentials
    payload = decode_token(token)
    user_id: str = payload.get("sub", "")
    if not user_id or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    user = await get_user_by_id(db, user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found")
    return user


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role.value != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


from sqlalchemy import select
from app.models.candidate_application import CandidateApplication

async def get_current_candidate(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> CandidateApplication:
    token = credentials.credentials
    payload = decode_token(token)
    candidate_id: str = payload.get("sub", "")
    role: str = payload.get("role", "")
    if not candidate_id or payload.get("type") != "access" or role != "candidate":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    stmt = select(CandidateApplication).where(CandidateApplication.id == candidate_id, CandidateApplication.is_deleted == False)
    res = await db.execute(stmt)
    candidate = res.scalar_one_or_none()
    if not candidate:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Candidate not found")
    return candidate
