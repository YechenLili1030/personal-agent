from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=64, examples=["admin"])
    password: str = Field(..., min_length=1, max_length=128, examples=["admin123"])


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class UserInfo(BaseModel):
    id: str
    username: str
    nickname: str | None = None
    avatar: str | None = None

    class Config:
        from_attributes = True


class ApiResponse(BaseModel):
    code: int = 0
    data: dict | list | str | None = None
    message: str = "ok"
