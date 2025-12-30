"""
RAG chat service using Claude and pgvector search
"""
import asyncio
from functools import partial
from typing import List, Dict, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException
from models.document import Chunk
from services.embeddings import get_embeddings
from services import extraction  # Import module, not variable
from utils.logging import log


async def search_similar_chunks(
    query: str,
    session: AsyncSession,
    limit: int = 5
) -> List[tuple]:
    """
    Search for chunks similar to the query using vector similarity.

    Args:
        query: Search query text
        session: Database session
        limit: Maximum number of chunks to return

    Returns:
        List of tuples: (filename, content, chunk_index)
    """
    # Generate embedding for query
    query_embedding = (await get_embeddings([query]))[0]

    # Search for relevant chunks using pgvector
    result = await session.execute(
        select(Chunk.filename, Chunk.content, Chunk.chunk_index)
        .order_by(Chunk.embedding.cosine_distance(query_embedding))
        .limit(limit)
    )
    chunks = result.all()

    return chunks


async def chat_with_documents(
    message: str,
    session: AsyncSession,
    include_sources: bool = True
) -> Dict:
    """
    Chat with documents using RAG (Retrieval Augmented Generation).

    Args:
        message: User's question/message
        session: Database session
        include_sources: Whether to include source references in response

    Returns:
        Dictionary with 'response' and 'sources' keys
    """
    if not extraction.claude_client:
        raise HTTPException(status_code=500, detail="Claude API not configured")

    # Search for relevant chunks
    chunks = await search_similar_chunks(message, session, limit=5)

    if not chunks:
        return {
            "response": "No documents have been indexed yet. Upload some documents first.",
            "sources": []
        }

    # Build context from chunks
    context_parts = []
    sources = []

    for filename, content, chunk_index in chunks:
        context_parts.append(f"[Source: {filename}]\n{content}")
        if filename not in [s["filename"] for s in sources]:
            # Determine source type based on filename structure
            # Vault files have paths like "folder/file.md" without leading slashes
            # External files typically have absolute paths or were uploaded via web
            is_vault_file = not filename.startswith('/') and not filename.startswith('\\')
            sources.append({
                "filename": filename,
                "chunk_index": chunk_index,
                "source_type": "vault" if is_vault_file else "external"
            })

    context = "\n\n---\n\n".join(context_parts)

    # Query Claude with context
    system_prompt = """You are an interactive research assistant helping a user explore their personal knowledge base.

Your role is to:
1. Answer the user's question using the provided context
2. Proactively guide deeper exploration by asking follow-up questions
3. Identify gaps or related topics that might interest them
4. Act like a conversation partner, not just an information retrieval system

Guidelines:
- Be concise but thorough in your answers
- Always cite sources by mentioning filenames
- After answering, ask 2-3 thoughtful follow-up questions that:
  * Explore deeper aspects of the topic
  * Connect to related themes that might be in their library
  * Identify potential gaps in the available information
- If you notice the context is incomplete or raises interesting questions, point that out
- Be curious and engaging - guide the conversation like a research partner would

Example response structure:
[Your answer with citations]

**Want to explore further?**
- [Follow-up question 1 about a specific detail]
- [Follow-up question 2 connecting to related topics]
- [Follow-up question 3 or observation about gaps]"""

    try:
        # Run the blocking Claude API call in a thread pool to avoid blocking event loop
        loop = asyncio.get_event_loop()
        api_message = await loop.run_in_executor(
            None,
            partial(
                extraction.claude_client.messages.create,
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                system=system_prompt,
                messages=[{
                    "role": "user",
                    "content": f"Context from your documents:\n\n{context}\n\n---\n\nQuestion: {message}"
                }]
            )
        )

        return {
            "response": api_message.content[0].text,
            "sources": sources if include_sources else []
        }
    except Exception as e:
        log(f"❌ Chat error: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


async def search_documents(
    query: str,
    session: AsyncSession,
    limit: int = 10
) -> List[Dict]:
    """
    Search documents by semantic similarity.

    Args:
        query: Search query text
        session: Database session
        limit: Maximum number of results

    Returns:
        List of dictionaries with filename, content (truncated), and chunk_index
    """
    if not query.strip():
        raise HTTPException(status_code=400, detail="Query cannot be empty")

    chunks = await search_similar_chunks(query, session, limit=limit)

    return [
        {
            "filename": filename,
            "content": content[:500] + "..." if len(content) > 500 else content,
            "chunk_index": chunk_index
        }
        for filename, content, chunk_index in chunks
    ]
