"""Database access layer (Motor / MongoDB)."""

from backend.app.db.mongo import (
    close_mongo,
    ensure_indexes,
    get_database,
    init_mongo,
    ping_mongo,
)

__all__ = [
    "init_mongo",
    "close_mongo",
    "get_database",
    "ensure_indexes",
    "ping_mongo",
]