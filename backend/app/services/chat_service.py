"""Compatibility facade for chat services.

New code should import from the narrower modules:
- chat_session_service.py
- chat_context_builder.py
- chat_agent_runner.py
"""

from .chat_agent_runner import generate_title, run_chat_agent
from .chat_context_builder import build_context
from .chat_session_service import (
    create_session,
    delete_session,
    get_history,
    get_session,
    list_sessions,
    save_message,
    update_session,
)

__all__ = [
    "build_context",
    "create_session",
    "delete_session",
    "generate_title",
    "get_history",
    "get_session",
    "list_sessions",
    "run_chat_agent",
    "save_message",
    "update_session",
]
