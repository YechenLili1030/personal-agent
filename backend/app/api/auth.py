from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from ..core.database import get_db
from ..schemas.user import LoginRequest, LoginResponse, UserInfo, ApiResponse
from ..services.auth import authenticate_user, create_access_token

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=ApiResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    user = await authenticate_user(db, req.username, req.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    token = create_access_token(user.id, user.username)

    return ApiResponse(
        code=0,
        data=LoginResponse(
            access_token=token,
            user=UserInfo(
                id=user.id,
                username=user.username,
                nickname=user.nickname,
                avatar=user.avatar,
            ),
        ).model_dump(),
        message="登录成功",
    )
