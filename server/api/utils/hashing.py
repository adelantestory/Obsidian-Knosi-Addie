"""
File hashing utilities
"""
import hashlib


def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()
