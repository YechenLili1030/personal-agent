from pydantic import BaseModel, Field


class SessionCreate(BaseModel):
    title: str = Field(default="新对话", max_length=256)
    mode: str = Field(default="normal", pattern="^(normal|rag)$")


class SessionUpdate(BaseModel):
    title: str | None = None
    status: str | None = Field(default=None, pattern="^(active|archived)$")


class SessionItem(BaseModel):
    session_id: str
    title: str
    mode: str
    message_count: int = 0
    created_at: str
    updated_at: str


class MessageItem(BaseModel):
    message_id: str
    role: str
    content: str
    metadata: dict | None = None
    created_at: str
