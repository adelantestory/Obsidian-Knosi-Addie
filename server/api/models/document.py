"""
Database models for documents and chunks
"""
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Integer, Text, LargeBinary
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector
from core.config import EMBEDDING_DIM

Base = declarative_base()


class Document(Base):
    """Document metadata table."""
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), unique=True, nullable=False, index=True)
    file_hash = Column(String(64), nullable=False)
    file_size = Column(Integer, nullable=False)
    file_data = Column(LargeBinary, nullable=True)  # Store original file for download
    chunk_count = Column(Integer, nullable=False, default=0)
    vault_name = Column(String(200), nullable=True, index=True)  # For Obsidian vault tracking
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
    vault_name = Column(String(200), nullable=True, index=True)  # For Obsidian vault tracking
