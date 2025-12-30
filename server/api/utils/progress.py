"""
SSE progress tracking for file uploads
"""
import asyncio
from utils.logging import log

# Progress tracking for uploads
# {upload_id: {"status": str, "filename": str, "queues": [asyncio.Queue]}}
upload_progress = {}


async def send_progress(upload_id: str, status: str):
    """Send progress update to all connected SSE clients."""
    if upload_id in upload_progress:
        progress_data = upload_progress[upload_id]
        progress_data["status"] = status
        queues = progress_data.get("queues", [])
        log(f"Sending progress to {len(queues)} SSE client(s): {status}")
        for queue in queues:
            try:
                await queue.put({"status": status, "filename": progress_data.get("filename", "")})
            except Exception as e:
                log(f"Failed to send progress to queue: {e}")
    else:
        log(f"WARNING: send_progress called for unknown upload_id: {upload_id}")


def init_upload_progress(upload_id: str, filename: str):
    """Initialize or update progress tracking entry, preserving existing queues."""
    if upload_id not in upload_progress:
        upload_progress[upload_id] = {
            "status": f"Uploading {filename}...",
            "filename": filename,
            "queues": []
        }
    else:
        # Update existing entry but keep the queues
        upload_progress[upload_id]["filename"] = filename
        upload_progress[upload_id]["status"] = f"Uploading {filename}..."


def cleanup_upload_progress(upload_id: str):
    """Clean up progress tracking for completed upload."""
    if upload_id in upload_progress:
        del upload_progress[upload_id]
