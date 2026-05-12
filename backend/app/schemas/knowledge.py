from pydantic import BaseModel, Field


class MergeRequest(BaseModel):
    source_chunk_id: str = Field(..., min_length=1)
    target_chunk_id: str = Field(..., min_length=1)
    selected_text: str | None = None  # 仅合并选中文本，为空则合并整个 chunk


class ChunkItem(BaseModel):
    chunk_id: str
    chunk_index: int
    content: str
    char_count: int
