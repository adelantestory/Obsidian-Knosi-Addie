"""
Database models for documents and chunks
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, LargeBinary
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector

Base = declarative_base()

# Embedding dimension for all-MiniLM-L6-v2
EMBEDDING_DIM = 384


class Document(Base):
    """Document metadata table."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), unique=True, nullable=False, index=True)
    file_hash = Column(String(64), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_data = Column(LargeBinary, nullable=True)  # Store original file for download
    chunk_count = Column(Integer, nullable=False, default=0)
    indexed_at = Column(DateTime, default=datetime.utcnow)


class Chunk(Base):
    """Document chunks with embeddings."""
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    document_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(500), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(EMBEDDING_DIM))
