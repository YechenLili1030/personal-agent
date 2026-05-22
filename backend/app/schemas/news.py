from datetime import date
from pydantic import BaseModel, Field


class NewsKeywordsUpdate(BaseModel):
    keywords: list[str] = Field(default_factory=list, max_length=20)


class NewsKeywordsResponse(BaseModel):
    keywords: list[str]


class NewsItem(BaseModel):
    title: str
    summary: str
    tags: list[str]
    source_url: str | None = None
    source_name: str | None = None


class BriefingResponse(BaseModel):
    id: str
    date: str
    title: str | None = None
    news_items: list[NewsItem]
    keywords_used: list[str]
    status: str
    created_at: str

    class Config:
        from_attributes = True


class BriefingListItem(BaseModel):
    id: str
    date: str
    title: str | None = None
    status: str
    created_at: str

    class Config:
        from_attributes = True


class BriefingListResponse(BaseModel):
    items: list[BriefingListItem]
    total: int


class GenerateRequest(BaseModel):
    date: str = Field(..., description="日期，格式 YYYY-MM-DD")
