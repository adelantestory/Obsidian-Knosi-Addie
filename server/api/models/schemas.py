"""
Pydantic schemas for API requests and responses
"""
from typing import List
from pydantic import BaseModel


class ChatRequest(BaseModel):
    message: str
    include_sources: bool = True


class ChatResponse(BaseModel):
    response: str
    sources: List[dict] = []


class DocumentInfo(BaseModel):
    filename: str
    file_size: int
    chunk_count: int
    indexed_at: str


class StatusResponse(BaseModel):
    status: str
    document_count: int
    chunk_count: int
