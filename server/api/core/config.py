"""
Configuration settings for Knosi API
"""
import os

# API Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "change-me-in-production")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://knosi:knosi@localhost:5432/knosi")

# File Upload Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".org", ".rst", ".html", ".htm", ".docx"}

# Text Chunking Configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "4000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Embedding Configuration
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # Dimension for all-MiniLM-L6-v2

# PDF Processing Configuration
PDF_BATCH_SIZE = int(os.getenv("PDF_BATCH_SIZE", "20"))  # Pages per batch
PDF_BATCHES_PER_MINUTE = int(os.getenv("PDF_BATCHES_PER_MINUTE", "60"))  # Rate limit (0 = no limit)
# Optional: Limit number of batches for testing
PDF_MAX_BATCHES = int(os.getenv("PDF_MAX_BATCHES", "0")) if os.getenv("PDF_MAX_BATCHES") else None
