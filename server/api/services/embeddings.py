"""
Embedding generation service using sentence-transformers
"""
from typing import List
from sentence_transformers import SentenceTransformer
from core.config import EMBEDDING_MODEL
from utils.logging import log

# Global embedding model instance
embedding_model = None


def init_embedding_model():
    """Initialize sentence transformer model."""
    global embedding_model
    log(f"🧠 Loading embedding model: {EMBEDDING_MODEL}...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    log(f"✅ Embedding model loaded")


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for a list of texts.

    Args:
        texts: List of text strings to embed

    Returns:
        List of embedding vectors (each is a list of floats)
    """
    if not texts:
        return []

    if not embedding_model:
        raise RuntimeError("Embedding model not initialized")

    embeddings = embedding_model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()
