"""Compatibility facade for knowledge services.

New code should import from the narrower modules:
- knowledge_document_service.py
- knowledge_chunk_service.py
- knowledge_indexing.py
- knowledge_chunking.py
- knowledge_llm.py
"""

from .knowledge_chunk_service import delete_chunk, merge_chunks
from .knowledge_document_service import (
    delete_document,
    finalize_document,
    process_document,
    save_upload,
)

__all__ = [
    "delete_chunk",
    "delete_document",
    "finalize_document",
    "merge_chunks",
    "process_document",
    "save_upload",
]
