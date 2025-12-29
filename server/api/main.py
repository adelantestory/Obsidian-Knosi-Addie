"""
Knosi API - Knowledge base indexing and chat with Claude
https://knosi.ai
"""
import os
import hashlib
import base64
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import Column, String, DateTime, Integer, Text, select, delete, func, text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base
from pgvector.sqlalchemy import Vector
import anthropic
from sentence_transformers import SentenceTransformer

# Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY", "change-me-in-production")
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://knosi:knosi@localhost:5432/knosi")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "100"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "4000"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "200"))
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
EMBEDDING_DIM = 384  # Dimension for all-MiniLM-L6-v2

# Supported file types
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".org", ".rst", ".html", ".htm", ".docx"}

# Database setup
Base = declarative_base()


class Document(Base):
    """Document metadata table."""
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(500), unique=True, nullable=False, index=True)
    file_hash = Column(String(64), nullable=False)
    file_size = Column(Integer, nullable=False)
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


# Global instances
engine = None
async_session = None
claude_client = None
embedding_model = None


async def init_db():
    """Initialize database and create tables."""
    global engine, async_session
    
    engine = create_async_engine(DATABASE_URL, echo=False)
    async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with engine.begin() as conn:
        # Enable pgvector extension
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncSession:
    """Get database session."""
    async with async_session() as session:
        yield session


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    global claude_client, embedding_model
    
    # Initialize database
    await init_db()
    
    # Initialize Claude client
    if ANTHROPIC_API_KEY:
        claude_client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    else:
        print("WARNING: ANTHROPIC_API_KEY not set - chat and PDF parsing disabled")
    
    # Initialize embedding model
    print(f"Loading embedding model: {EMBEDDING_MODEL}...")
    embedding_model = SentenceTransformer(EMBEDDING_MODEL)
    print("Embedding model loaded")
    
    print(f"Knosi API started - https://knosi.ai")
    print(f"Max file size: {MAX_FILE_SIZE_MB}MB")
    print(f"API key auth: {'enabled' if API_SECRET_KEY != 'change-me-in-production' else 'disabled'}")
    
    yield
    
    await engine.dispose()
    print("Knosi API shutting down")


app = FastAPI(title="Knosi", lifespan=lifespan)

# CORS for web UI and remote clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Authentication
async def verify_api_key(x_api_key: Optional[str] = Header(None)):
    """Verify API key for protected endpoints."""
    if API_SECRET_KEY == "change-me-in-production":
        return True  # Auth disabled
    if not x_api_key or x_api_key != API_SECRET_KEY:
        raise HTTPException(status_code=401, detail="Invalid or missing API key")
    return True


# Pydantic models
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


# Helper functions
def compute_file_hash(content: bytes) -> str:
    """Compute SHA-256 hash of file content."""
    return hashlib.sha256(content).hexdigest()


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> List[str]:
    """Split text into overlapping chunks."""
    if not text or len(text) <= chunk_size:
        return [text] if text else []
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = start + chunk_size
        
        # Try to break at paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind('\n\n', start, end)
            if para_break > start + chunk_size // 2:
                end = para_break + 2
            else:
                # Look for sentence break
                for sep in ['. ', '.\n', '? ', '!\n', '! ']:
                    sent_break = text.rfind(sep, start, end)
                    if sent_break > start + chunk_size // 2:
                        end = sent_break + len(sep)
                        break
        
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        
        start = end - overlap
        if start >= len(text):
            break
    
    return chunks


async def extract_text_from_pdf(content: bytes, filename: str) -> str:
    """Extract text from PDF using Claude's vision capability."""
    if not claude_client:
        raise HTTPException(status_code=500, detail="Claude API not configured")

    base64_pdf = base64.standard_b64encode(content).decode("utf-8")

    try:
        message = claude_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "document",
                        "source": {
                            "type": "base64",
                            "media_type": "application/pdf",
                            "data": base64_pdf,
                        },
                    },
                    {
                        "type": "text",
                        "text": "Extract all text content from this PDF document. Preserve the structure including headings, paragraphs, and lists. Output only the extracted text, no commentary."
                    }
                ],
            }],
        )

        return message.content[0].text
    except anthropic.BadRequestError as e:
        if "content filtering policy" in str(e):
            raise HTTPException(
                status_code=400,
                detail="PDF content was blocked by Claude's content filtering policy. This can happen with certain documents. Try a different PDF or contact support if this persists."
            )
        raise HTTPException(status_code=400, detail=f"Claude API error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"PDF extraction failed: {str(e)}")


async def extract_text_from_docx(content: bytes) -> str:
    """Extract text from DOCX file."""
    import zipfile
    import io
    from xml.etree import ElementTree
    
    text_parts = []
    
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        if 'word/document.xml' in zf.namelist():
            xml_content = zf.read('word/document.xml')
            tree = ElementTree.fromstring(xml_content)
            
            ns = {'w': 'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
            for para in tree.findall('.//w:p', ns):
                para_text = ''.join(node.text or '' for node in para.findall('.//w:t', ns))
                if para_text.strip():
                    text_parts.append(para_text)
    
    return '\n\n'.join(text_parts)


async def extract_text(content: bytes, filename: str) -> str:
    """Extract text from file based on extension."""
    ext = Path(filename).suffix.lower()
    
    if ext == '.pdf':
        return await extract_text_from_pdf(content, filename)
    elif ext == '.docx':
        return await extract_text_from_docx(content)
    elif ext in {'.md', '.txt', '.org', '.rst', '.html', '.htm'}:
        # Try common encodings
        for encoding in ['utf-8', 'latin-1', 'cp1252']:
            try:
                return content.decode(encoding)
            except UnicodeDecodeError:
                continue
        return content.decode('utf-8', errors='replace')
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for texts."""
    if not texts:
        return []
    embeddings = embedding_model.encode(texts, show_progress_bar=False)
    return embeddings.tolist()


# API Endpoints
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
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Upload and index a document."""
    # Use path if provided (from watcher), otherwise use filename
    filename = path or file.filename
    ext = Path(filename).suffix.lower()
    
    if ext not in SUPPORTED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Supported: {', '.join(SUPPORTED_EXTENSIONS)}"
        )
    
    # Read file content
    content = await file.read()
    file_size = len(content)
    
    if file_size > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=400,
            detail=f"File too large. Max size: {MAX_FILE_SIZE_MB}MB"
        )
    
    # Check if already indexed with same hash
    file_hash = compute_file_hash(content)
    existing = await session.execute(
        select(Document).where(Document.filename == filename)
    )
    existing_doc = existing.scalar_one_or_none()
    
    if existing_doc and existing_doc.file_hash == file_hash:
        return {"message": "Document already indexed", "filename": filename, "status": "unchanged"}
    
    # Extract text
    text = await extract_text(content, filename)
    
    if not text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from document")
    
    # Chunk text
    chunks = chunk_text(text)
    
    # Generate embeddings
    embeddings = get_embeddings(chunks)
    
    # Remove old document if exists
    if existing_doc:
        await session.execute(delete(Chunk).where(Chunk.document_id == existing_doc.id))
        await session.delete(existing_doc)
        await session.commit()
    
    # Create new document
    doc = Document(
        filename=filename,
        file_hash=file_hash,
        file_size=file_size,
        chunk_count=len(chunks)
    )
    session.add(doc)
    await session.flush()
    
    # Create chunks
    for i, (chunk_text_content, embedding) in enumerate(zip(chunks, embeddings)):
        chunk = Chunk(
            document_id=doc.id,
            filename=filename,
            chunk_index=i,
            content=chunk_text_content,
            embedding=embedding
        )
        session.add(chunk)
    
    await session.commit()
    
    return {
        "message": "Document indexed successfully",
        "filename": filename,
        "chunks": len(chunks),
        "status": "updated" if existing_doc else "created"
    }


@app.delete("/api/documents/{filename:path}")
async def delete_document(
    filename: str,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Delete a document from the index."""
    result = await session.execute(
        select(Document).where(Document.filename == filename)
    )
    doc = result.scalar_one_or_none()
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    await session.execute(delete(Chunk).where(Chunk.document_id == doc.id))
    await session.delete(doc)
    await session.commit()
    
    return {"message": "Document deleted", "filename": filename}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Chat with your documents using RAG."""
    if not claude_client:
        raise HTTPException(status_code=500, detail="Claude API not configured")
    
    # Generate embedding for query
    query_embedding = get_embeddings([request.message])[0]
    
    # Search for relevant chunks using pgvector
    result = await session.execute(
        select(Chunk.filename, Chunk.content, Chunk.chunk_index)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(5)
    )
    chunks = result.all()
    
    if not chunks:
        return ChatResponse(
            response="No documents have been indexed yet. Upload some documents first.",
            sources=[]
        )
    
    # Build context
    context_parts = []
    sources = []
    
    for filename, content, chunk_index in chunks:
        context_parts.append(f"[Source: {filename}]\n{content}")
        if filename not in [s["filename"] for s in sources]:
            sources.append({"filename": filename, "chunk_index": chunk_index})
    
    context = "\n\n---\n\n".join(context_parts)
    
    # Query Claude
    system_prompt = """You are a helpful assistant that answers questions based on the provided document context.
Use the context to answer the user's question. If the answer isn't in the context, say so.
Be concise but thorough. Cite sources when relevant by mentioning the filename."""
    
    message = claude_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=4096,
        system=system_prompt,
        messages=[{
            "role": "user",
            "content": f"Context from your documents:\n\n{context}\n\n---\n\nQuestion: {request.message}"
        }]
    )
    
    return ChatResponse(
        response=message.content[0].text,
        sources=sources if request.include_sources else []
    )


@app.get("/api/search")
async def search_documents(
    q: str,
    limit: int = 10,
    session: AsyncSession = Depends(get_session),
    _: bool = Depends(verify_api_key)
):
    """Search documents by semantic similarity."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")
    
    query_embedding = get_embeddings([q])[0]
    
    result = await session.execute(
        select(Chunk.filename, Chunk.content, Chunk.chunk_index)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    chunks = result.all()
    
    return [
        {
            "filename": filename,
            "content": content[:500] + "..." if len(content) > 500 else content,
            "chunk_index": chunk_index
        }
        for filename, content, chunk_index in chunks
    ]


@app.get("/")
async def root():
    """API root endpoint."""
    return {
        "name": "Knosi API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "/api/status"
    }
