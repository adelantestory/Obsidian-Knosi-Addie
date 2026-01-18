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
SUPPORTED_EXTENSIONS = {
    ".pdf", ".md", ".txt", ".org", ".rst", ".html", ".htm", ".docx",
    ".png", ".jpg", ".jpeg", ".gif", ".webp"  # Image formats
}

# Text Chunking Configuration
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "4000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))

# Azure OpenAI Embedding Configuration
AZURE_OPENAI_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
AZURE_OPENAI_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv("AZURE_OPENAI_EMBEDDING_DEPLOYMENT")
AZURE_OPENAI_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-01")

# Embedding dimension - must match the model's output dimension
# Common dimensions:
# - all-MiniLM-L6-v2: 384
# - all-mpnet-base-v2: 768
# - BAAI/bge-base-en-v1.5: 768
# - intfloat/e5-base-v2: 768
# - nomic-ai/nomic-embed-text-v1: 768
# WARNING: Changing this after indexing documents will cause dimension mismatches!
# You must clear the database when switching embedding models.
EMBEDDING_DIM = int(os.getenv("EMBEDDING_DIM", "1536"))

# PDF Processing Configuration
PDF_BATCH_SIZE = int(os.getenv("PDF_BATCH_SIZE", "20"))  # Pages per batch
PDF_BATCHES_PER_MINUTE = int(os.getenv("PDF_BATCHES_PER_MINUTE", "60"))  # Rate limit (0 = no limit)
# Optional: Limit number of batches for testing
PDF_MAX_BATCHES = int(os.getenv("PDF_MAX_BATCHES", "0")) if os.getenv("PDF_MAX_BATCHES") else None
