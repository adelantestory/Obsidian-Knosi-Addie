"""
Core configuration and dependencies
"""
from .config import *
from .database import init_db, get_session, close_db
from .deps import verify_api_key

__all__ = [
    # Config
    "ANTHROPIC_API_KEY",
    "API_SECRET_KEY",
    "DATABASE_URL",
    "MAX_FILE_SIZE_MB",
    "SUPPORTED_EXTENSIONS",
    "CHUNK_SIZE",
    "CHUNK_OVERLAP",
    "EMBEDDING_MODEL",
    "EMBEDDING_DIM",
    "PDF_BATCH_SIZE",
    "PDF_BATCHES_PER_MINUTE",
    "PDF_MAX_BATCHES",
    # Database
    "init_db",
    "get_session",
    "close_db",
    # Dependencies
    "verify_api_key",
]
