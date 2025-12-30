"""
Logging utilities
"""
from datetime import datetime


def log(message: str):
    """Print with timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}", flush=True)
