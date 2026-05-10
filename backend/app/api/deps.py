"""共享依赖注入"""

from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..models.user import User
from ..services.auth import get_current_user


async def require_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, detail="未提供有效的认证令牌")
    user = await get_current_user(db, authorization[7:])
    if not user:
        raise HTTPException(401, detail="认证令牌无效或已过期")
    return user
