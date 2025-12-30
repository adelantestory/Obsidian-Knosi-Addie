"""
FastAPI dependencies (authentication, etc.)
"""
from typing import Optional
from fastapi import Header, HTTPException
from core.config import API_SECRET_KEY


async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key if authentication is enabled."""
    if API_SECRET_KEY and API_SECRET_KEY != "change-me-in-production":
        if not x_api_key or x_api_key != API_SECRET_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")
