"""
Embedding generation service using Azure OpenAI
"""
import asyncio
from typing import List
from openai import AzureOpenAI
from core.config import (
    AZURE_OPENAI_ENDPOINT,
    AZURE_OPENAI_API_KEY,
    AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    AZURE_OPENAI_API_VERSION,
)
from utils.logging import log

# Global Azure OpenAI client
client = None


def init_embedding_model():
    """Initialize Azure OpenAI client."""
    global client
    log(f"🧠 Initializing Azure OpenAI embeddings client...")
    client = AzureOpenAI(
        azure_endpoint=AZURE_OPENAI_ENDPOINT,
        api_key=AZURE_OPENAI_API_KEY,
        api_version=AZURE_OPENAI_API_VERSION,
    )
    log(f"✅ Azure OpenAI client initialized")


def _get_embeddings_sync(texts: List[str]) -> List[List[float]]:
    """Synchronous embedding function to run in thread pool."""
    # Azure OpenAI supports batching - send all texts at once
    response = client.embeddings.create(
        input=texts,
        model=AZURE_OPENAI_EMBEDDING_DEPLOYMENT,
    )
    # Extract embeddings in order
    return [item.embedding for item in response.data]


async def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using Azure OpenAI.

    Runs the API call in a thread pool to avoid blocking the event loop.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    if not client:
        raise RuntimeError("Azure OpenAI client not initialized")

    # Run the blocking API call in a thread pool
    loop = asyncio.get_event_loop()
    embeddings = await loop.run_in_executor(None, _get_embeddings_sync, texts)
    return embeddings

