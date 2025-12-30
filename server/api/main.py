"""
Knosi API - Knowledge base indexing and chat with Claude
https://knosi.ai

Refactored to follow SOLID principles and DRY pattern.
"""
import uuid
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional, List

import anthropic
import httpx
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Form, Query
from fastapi.responses import Response, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select, delete, func
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse

# Import our refactored modules
from core import (
    init_db, get_session, close_db, verify_api_key,
    ANTHROPIC_API_KEY, MAX_FILE_SIZE_MB, API_SECRET_KEY, SUPPORTED_EXTENSIONS
)
from models import Document, Chunk
from models.schemas import ChatRequest, ChatResponse, DocumentInfo, StatusResponse
from services import (
    init_claude_client, init_embedding_model,
    extract_text, get_embeddings,
    chat_with_documents, search_documents
)
from utils import (
    log, compute_file_hash, chunk_text,
    upload_progress, send_progress, init_upload_progress, cleanup_upload_progress
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Initialize database
    await init_db()

    # Initialize Claude client with custom timeout settings
    if ANTHROPIC_API_KEY:
        # Create custom HTTP client with connection timeout
        http_client = httpx.Client(
            timeout=httpx.Timeout(
                connect=30.0,  # 30s to establish connection
                read=300.0,    # 5 minutes to read response
                write=30.0,    # 30s to send request
                pool=30.0      # 30s to get connection from pool
            )
        )
        init_claude_client(ANTHROPIC_API_KEY, http_client)
    else:
        log("⚠️  WARNING: ANTHROPIC_API_KEY not set - chat and PDF parsing disabled")

    # Initialize embedding model
    init_embedding_model()

    log(f"🚀 Knosi API started - https://knosi.ai")
    log(f"📦 Max file size: {MAX_FILE_SIZE_MB}MB")
    log(f"🔐 API key auth: {'enabled' if API_SECRET_KEY != 'change-me-in-production' else 'disabled'}")

    yield

    # Cleanup
    await close_db()
    log("👋 Knosi API shutting down")


# Initialize FastAPI app
app = FastAPI(title="Knosi", lifespan=lifespan)

# CORS for web UI and remote clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# API ROUTES
# ============================================================================

@app.get("/api/status", response_model=StatusResponse)
async def get_status(session: AsyncSession = Depends(get_session)):
    """Get server status and index statistics."""
    doc_count = await session.scalar(select(func.count(Document.id)))
    chunk_count = await session.scalar(select(func.count(Chunk.id)))
    return StatusResponse(
        status="ok",
        document_count=doc_count or 0,
        chunk_count=chunk_count or 0
    )


@app.get("/api/upload/{upload_id}/progress")
async def upload_progress_stream(
    upload_id: str,
    api_key: Optional[str] = Query(None)
):
    """SSE endpoint for upload progress updates."""
    # Verify API key from query param (EventSource can't send custom headers)
    if API_SECRET_KEY != "change-me-in-production":
        if not api_key or api_key != API_SECRET_KEY:
            raise HTTPException(status_code=401, detail="Invalid or missing API key")

    async def event_generator():
        queue = asyncio.Queue()

        # Register this SSE client for progress updates
        if upload_id not in upload_progress:
            upload_progress[upload_id] = {"status": "waiting", "filename": "", "queues": []}
        upload_progress[upload_id]["queues"].append(queue)

        log(f"📡 SSE client connected for upload {upload_id}")

        try:
            while True:
                try:
                    # Wait for progress update with 30s timeout
                    data = await asyncio.wait_for(queue.get(), timeout=30.0)

                    # Format as SSE event with explicit newlines
                    event_data = f"event: progress\ndata: {data['status']}\n\n"
                    yield event_data.encode('utf-8')

                    # Close connection if upload is complete or failed
                    if data['status'].startswith('complete:') or data['status'].startswith('error:'):
                        break

                except asyncio.TimeoutError:
                    # Send keepalive comment to prevent buffering
                    yield f": keepalive\n\n".encode('utf-8')
                    continue

        finally:
            log(f"📡 SSE client disconnected for upload {upload_id}")
            # Remove this queue from the list
            if upload_id in upload_progress:
                try:
                    upload_progress[upload_id]["queues"].remove(queue)
                except ValueError:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
            "Connection": "keep-alive",
        }
    )


@app.get("/api/documents", response_model=List[DocumentInfo])
async def list_documents(
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """List all indexed documents."""
    result = await session.execute(
        select(Document).order_by(Document.indexed_at.desc())
    )
    docs = result.scalars().all()

    return [
        DocumentInfo(
            filename=doc.filename,
            file_size=doc.file_size,
            chunk_count=doc.chunk_count,
            indexed_at=doc.indexed_at.isoformat()
        )
        for doc in docs
    ]


@app.post("/api/upload")
async def upload_document(
    file: UploadFile = File(...),
    path: Optional[str] = Form(None),
    upload_id: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Upload and index a document."""
    # Generate upload ID if not provided (for SSE progress tracking)
    if not upload_id:
        upload_id = str(uuid.uuid4())

    try:
        log(f"DEBUG: Upload endpoint called, upload_id={upload_id}")
        log(f"DEBUG: file.filename={file.filename}, path={path}")

        # Use path if provided (from watcher), otherwise use filename
        filename = path or file.filename
        log(f"DEBUG: Using filename={filename}")

        # Initialize or update progress tracking (preserve existing queues from SSE)
        init_upload_progress(upload_id, filename)
        await send_progress(upload_id, f"Uploading {filename}...")

        ext = Path(filename).suffix.lower()
        log(f"DEBUG: File extension={ext}")

        if ext not in SUPPORTED_EXTENSIONS:
            await send_progress(upload_id, f"error:Unsupported file type: {ext}")
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
            )

        log(f"📤 Upload started: {filename}")

        # Read file content
        log(f"DEBUG: About to read file content")
        content = await file.read()
        file_size = len(content)
        file_size_mb = file_size / (1024 * 1024)
        log(f"📦 File read: {file_size_mb:.1f}MB")

        if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
            await send_progress(upload_id, f"error:File too large")
            raise HTTPException(
                status_code=400,
                detail=f"File too large. Max size: {MAX_FILE_SIZE_MB}MB"
            )

        # Check if already indexed with same hash
        log(f"DEBUG: Computing file hash")
        file_hash = compute_file_hash(content)
        existing = await session.execute(
            select(Document).where(Document.filename == filename)
        )
        existing_doc = existing.scalar_one_or_none()

        if existing_doc and existing_doc.file_hash == file_hash:
            await send_progress(upload_id, f"complete:Already indexed")
            return {"message": "Document already indexed", "filename": filename, "status": "unchanged", "upload_id": upload_id}

        # Extract text
        await send_progress(upload_id, f"Extracting text from {filename}...")
        log(f"📄 Extracting text from {filename}...")
        text = await extract_text(content, filename, upload_id)

        if not text.strip():
            await send_progress(upload_id, f"error:Could not extract text")
            raise HTTPException(status_code=400, detail="Could not extract text from document")

        await send_progress(upload_id, f"Chunking text from {filename}...")
        log(f"✂️  Chunking text ({len(text)} characters)...")
        # Chunk text
        chunks = chunk_text(text)
        log(f"📊 Created {len(chunks)} chunks")

        # Generate embeddings
        await send_progress(upload_id, f"Generating embeddings for {filename}...")
        log(f"🧠 Generating embeddings for {len(chunks)} chunks...")
        embeddings = get_embeddings(chunks)
        log(f"✅ Embeddings complete")

        # Delete existing document if re-indexing
        if existing_doc:
            log(f"🗑️  Removing old version of {filename}...")
            await session.execute(delete(Chunk).where(Chunk.document_id == existing_doc.id))
            await session.execute(delete(Document).where(Document.id == existing_doc.id))

        # Store document
        await send_progress(upload_id, f"Saving to database...")
        log(f"💾 Saving to database...")
        doc = Document(
            filename=filename,
            file_hash=file_hash,
            file_size=file_size,
            file_data=content,
            chunk_count=len(chunks)
        )
        session.add(doc)
        await session.flush()

        # Store chunks with embeddings
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            chunk_obj = Chunk(
                document_id=doc.id,
                filename=filename,
                chunk_index=i,
                content=chunk,
                embedding=embedding
            )
            session.add(chunk_obj)

        await session.commit()

        log(f"✅ {filename} indexed successfully ({len(chunks)} chunks)")
        await send_progress(upload_id, f"complete:{filename} uploaded successfully.")

        return {
            "message": "Document indexed successfully",
            "filename": filename,
            "chunks": len(chunks),
            "status": "indexed",
            "upload_id": upload_id
        }

    except HTTPException:
        raise
    except Exception as e:
        log(f"❌ Upload failed: {str(e)}")
        await send_progress(upload_id, f"error:{str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Clean up progress tracking after a delay
        async def cleanup_later():
            await asyncio.sleep(5)
            cleanup_upload_progress(upload_id)
        asyncio.create_task(cleanup_later())


@app.get("/api/documents/{filename:path}/download")
async def download_document(
    filename: str,
    api_key: Optional[str] = Query(None),
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Download original document file."""
    result = await session.execute(
        select(Document).where(Document.filename == filename)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    if not doc.file_data:
        raise HTTPException(status_code=404, detail="Original file not available")

    # Determine content type from extension
    ext = Path(filename).suffix.lower()
    content_types = {
        '.pdf': 'application/pdf',
        '.md': 'text/markdown',
        '.txt': 'text/plain',
        '.html': 'text/html',
        '.htm': 'text/html',
        '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
        '.org': 'text/plain',
        '.rst': 'text/plain'
    }
    content_type = content_types.get(ext, 'application/octet-stream')

    return Response(
        content=doc.file_data,
        media_type=content_type,
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@app.delete("/api/documents/{filename:path}")
async def delete_document(
    filename: str,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Delete a document and its chunks from the index."""
    result = await session.execute(
        select(Document).where(Document.filename == filename)
    )
    doc = result.scalar_one_or_none()

    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    # Delete chunks
    await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    # Delete document
    await session.execute(delete(Document).where(Document.id == doc.id))
    await session.commit()

    log(f"🗑️  Deleted: {filename}")
    return {"message": "Document deleted", "filename": filename}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Chat with your documents using RAG."""
    result = await chat_with_documents(
        request.message,
        session,
        request.include_sources
    )
    return ChatResponse(**result)


@app.get("/api/search")
async def search(
    q: str,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Search documents by semantic similarity."""
    return await search_documents(q, session, limit)


@app.get("/")
async def root():
    """API root - redirect to documentation."""
    return {
        "name": "Knosi",
        "version": "1.0.0",
        "docs": "/docs",
        "website": "https://knosi.ai"
    }
