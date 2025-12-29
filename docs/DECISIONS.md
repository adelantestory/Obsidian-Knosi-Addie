# Knosi - Decision Log

This document captures key decisions made during the development of Knosi, including both technical implementation decisions and user-driven feature decisions.

---

## Decision 001: Build Custom Solution vs Extend Khoj

**Date:** 2024-12-24  
**Type:** Strategic  
**Decision:** Build a minimal custom solution rather than fork/extend Khoj

**Context:**
- Khoj has a 10MB file size limit
- Khoj's codebase is complex (multi-user, multiple auth methods, web search, etc.)
- User needs were simple: index documents, chat with them

**Alternatives Considered:**
1. Fork Khoj and modify the limit
2. Request feature change from Khoj maintainers
3. Build minimal alternative

**Rationale:**
- Modifying Khoj would require understanding a large codebase
- A minimal solution (~500 lines) is easier to maintain and customize
- Single-user focus eliminates auth complexity
- Can optimize for the specific use case

**Consequences:**
- Less features than Khoj (no web search, no multi-user)
- Easier to understand and modify
- Full control over the implementation

---

## Decision 002: PostgreSQL + pgvector over ChromaDB

**Date:** 2024-12-24  
**Type:** Technical  
**Decision:** Use PostgreSQL with pgvector extension instead of ChromaDB

**Context:**
- Initial v1 prototype used ChromaDB
- User asked about PostgreSQL for the datastore

**Alternatives Considered:**
1. ChromaDB (embedded, simpler setup)
2. PostgreSQL + pgvector (production database)
3. Pinecone/Weaviate (managed services)

**Rationale:**
- PostgreSQL is battle-tested for production use
- Easy backup/restore with standard tools (`pg_dump`)
- pgvector provides efficient vector similarity search
- User already familiar with PostgreSQL
- No vendor lock-in to managed services

**Consequences:**
- Slightly more complex Docker setup (two containers)
- Requires pgvector extension
- More robust for long-term use

---

## Decision 003: Claude API for PDF Extraction

**Date:** 2024-12-24  
**Type:** Technical  
**Decision:** Use Claude's native PDF support for text extraction

**Context:**
- Earlier in the session, we successfully extracted text from a locked Christian History Magazine PDF using Claude
- Other OCR tools failed on this PDF
- Need reliable extraction for theological documents

**Alternatives Considered:**
1. PyPDF2/pdfplumber (free, local)
2. Tesseract OCR (free, local)
3. Claude API (paid, but proven)
4. Commercial OCR services

**Rationale:**
- Claude already proven to work on problematic PDFs
- Handles locked/protected documents
- Handles scanned documents via vision
- Single API for both extraction and chat
- Quality of extraction is high

**Trade-offs:**
- PDF extraction consumes tokens (cost)
- Requires API call per document
- But: extraction is one-time per document, not per query

**Consequences:**
- Higher upfront cost for indexing large PDFs
- Very reliable extraction
- No separate OCR pipeline to maintain

---

## Decision 004: Local Embeddings with sentence-transformers

**Date:** 2024-12-24  
**Type:** Technical  
**Decision:** Generate embeddings locally using sentence-transformers

**Context:**
- Need to convert text chunks to vectors for similarity search
- Options: OpenAI embeddings, Cohere, local models

**Alternatives Considered:**
1. OpenAI text-embedding-ada-002 (API)
2. Cohere embeddings (API)
3. sentence-transformers all-MiniLM-L6-v2 (local)

**Rationale:**
- No additional API key required
- No per-request cost
- Fast enough for document indexing (not real-time)
- all-MiniLM-L6-v2 is compact (80MB) and effective
- Reduces external dependencies

**Trade-offs:**
- Slightly larger Docker image
- Model downloads on first build
- Local model may be less accurate than latest API models

**Consequences:**
- Zero marginal cost for embeddings
- Works offline after initial setup
- Simpler API key management

---

## Decision 005: Split Architecture (Remote Server + Local Client)

**Date:** 2024-12-24  
**Type:** Architectural  
**Decision:** Server runs on VPS, client runs locally and syncs via HTTP

**Context:**
- User originally asked about watchdog watching files
- But also wanted to deploy on Vultr (remote server)
- How to bridge local files with remote server?

**Alternatives Considered:**
1. All-local (Docker on Mac)
2. All-remote with file upload UI only
3. Split: server remote, client local

**Rationale:**
- Server on Vultr can run 24/7, handles heavy processing
- Local client watches files, lightweight
- HTTP API bridges the gap
- Can access from multiple devices

**Consequences:**
- Need network connectivity for sync
- Server maintains state, clients are stateless
- Can have multiple client types (plugin, script, web UI)

---

## Decision 006: Multiple Client Options

**Date:** 2024-12-24  
**Type:** Feature  
**Decision:** Provide Obsidian plugin AND Python script as sync options

**Context:**
- User primarily uses Obsidian
- But wanted to share on GitHub for others
- Some users may not use Obsidian

**User's Words:**
> "I only edit in Obsidian, but I'd like both. That way, if I choose to share on GitHub, folks can use it without needing Obsidian."

**Alternatives Considered:**
1. Obsidian plugin only
2. Python script only
3. Both (chosen)

**Rationale:**
- Obsidian plugin: best for Obsidian-only workflows
- Python script: catches all filesystem changes, editor-agnostic
- Both options make the project more accessible
- They're independent - users choose one

**Consequences:**
- Two codebases to maintain (TypeScript + Python)
- More flexibility for users
- Clear documentation needed on when to use which

---

## Decision 007: Windows Support for Auto-start

**Date:** 2024-12-24  
**Type:** Feature  
**Decision:** Add Windows auto-start scripts alongside macOS

**Context:**
- Initial auto-start only supported macOS (launchd)
- User wanted to share on GitHub

**User's Words:**
> "I'd also ask that you create a script for Windows users, not just Mac."

**Implementation:**
- PowerShell script for Windows
- Two modes: Task Scheduler (admin) or Startup folder (no admin)
- Interactive setup like macOS script

**Consequences:**
- Broader audience can use the tool
- Need to test on Windows
- PowerShell has different error handling than bash

---

## Decision 008: Queue-Based Sync for Obsidian Plugin

**Date:** 2024-12-24  
**Type:** Technical  
**Decision:** Replace debounce-based sync with queue-based batch sync

**Context:**
- Original plugin used 2-second debounce
- Obsidian autosaves frequently
- User pointed out: edit, wait 5 seconds, edit again = 2 syncs

**User's Words:**
> "Let's say I make a change to a file, wait 5-10 seconds, then make another change. That means the file is 'synced' twice within a handful of seconds. This could be very costly."

**Original Approach:**
```
Edit → 2s debounce → Sync
Edit → 2s debounce → Sync  (another sync!)
```

**New Approach:**
```
Edit → Add to queue (Set, deduplicated)
Edit → Already in queue (no-op)
Every X minutes → Process entire queue
```

**Implementation:**
- `pendingUploads: Set<string>` for deduplication
- Configurable interval: 1-60 minutes (default: 1)
- "View Queue" command to see pending files
- "Sync Now" command for immediate processing

**Consequences:**
- Much more cost-effective for active editing sessions
- Small delay before files are indexed (up to sync interval)
- User has control over the trade-off via settings

---

## Decision 009: API Key Authentication (Optional)

**Date:** 2024-12-24  
**Type:** Security  
**Decision:** Support API key auth but make it optional

**Context:**
- Server will be exposed on the internet (Vultr)
- Need some protection for upload/delete endpoints
- But also want easy local testing

**Implementation:**
- `API_SECRET_KEY` environment variable
- If set to default (`change-me-in-production`), auth is disabled
- If set to custom value, all protected endpoints require `X-API-Key` header

**Rationale:**
- Simple to implement and use
- No complex auth flows (magic links, OAuth)
- Single-user system doesn't need user management
- Easy to disable for local development

**Consequences:**
- Not suitable for multi-user deployment
- API key must be kept secret
- Should use HTTPS in production (via reverse proxy)

---

## Decision 010: Configurable File Size Limit

**Date:** 2024-12-24  
**Type:** Feature  
**Decision:** Make file size limit configurable, default 100MB

**Context:**
- Khoj's 10MB limit was the original pain point
- But unlimited could cause issues (memory, timeout)

**Implementation:**
- `MAX_FILE_SIZE_MB` environment variable
- Default: 100MB (10x Khoj's limit)
- Validated on upload, returns 400 if exceeded

**Rationale:**
- 100MB handles most documents
- Can increase for specific needs
- Prevents accidental massive uploads

**Consequences:**
- Very large PDFs still work
- Server needs sufficient memory for processing
- Claude API has its own limits (~100 page recommendation)

---

## Decision 011: Separate Frontend and Backend

**Date:** 2024-12-24  
**Type:** Architectural  
**Decision:** Split into React frontend and FastAPI backend

**Context:**
- Original implementation had HTML embedded in FastAPI
- User requested separation for future extensibility

**User's Words:**
> "Is it possible to have a React front-end and a Python backend? The docker compose could spin up two endpoints... This would allow us to expand the capabilities of the app later."

**Implementation:**
- React frontend on port 48080
- FastAPI backend on port 48550
- Centralized API client in frontend
- Docker Compose orchestrates both

**Consequences:**
- Better separation of concerns
- Frontend can evolve independently
- Easier to add features like routing, state management
- Slightly more complex deployment

---

## Decision 012: Brand Name "Knosi"

**Date:** 2024-12-24  
**Type:** Branding  
**Decision:** Name the product "Knosi"

**Context:**
- User wanted a SaaS-ready name
- Had to be unique and not in use
- Explored Greek roots for "knowledge"

**Options Considered:**
- Episteme variations (Epistra, Epistio)
- Gnosis variations (Gnosica, Gnosia)
- Modern variations (Knosi)

**User's Words:**
> "landed on knosi"

**Rationale:**
- From Greek "gnosis" (knowledge)
- "K" spelling modernizes it
- Avoids religious connotations
- Short, memorable, brandable
- knosi.ai domain available

**Consequences:**
- Strong brand identity
- Clear meaning (knowledge)
- Easy to pronounce and spell

---

## Future Considerations

These are not decisions made, but topics to consider for future development:

1. **Incremental PDF updates** - Currently re-indexes entire document on change
2. **Multiple embedding models** - Allow swapping sentence-transformers models
3. **Chat history** - Persist conversations for context
4. **Multi-user support** - If needed, would require auth redesign
5. **Hybrid search** - Combine vector search with keyword search
6. **Document preview** - Show source documents in web UI
7. **Mobile client** - iOS/Android app for access on the go
8. **Obsidian chat interface** - Query documents directly from Obsidian
