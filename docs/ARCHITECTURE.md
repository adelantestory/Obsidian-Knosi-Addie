# Knosi - Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              LOCAL MACHINE                                  │
│                                                                             │
│  ┌─────────────────────────────┐     ┌─────────────────────────────────┐   │
│  │     Obsidian Plugin         │     │      Python knosi-sync.py       │   │
│  │     (TypeScript)            │     │      (watchdog)                 │   │
│  │                             │     │                                 │   │
│  │  - Queue-based sync         │     │  - Filesystem-level watching    │   │
│  │  - Configurable interval    │     │  - Catches ALL file changes     │   │
│  │  - Obsidian edits only      │     │  - Debounced uploads            │   │
│  │  - Status bar UI            │     │  - Auto-start scripts           │   │
│  └──────────────┬──────────────┘     └───────────────┬─────────────────┘   │
│                 │                                     │                     │
│                 │         HTTP POST /api/upload       │                     │
│                 └──────────────────┬──────────────────┘                     │
│                                    │                                        │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
                                     ▼
┌────────────────────────────────────────────────────────────────────────────┐
│                           REMOTE SERVER (Docker)                            │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     React Frontend (:48080)                          │  │
│  │  - Chat interface                                                    │  │
│  │  - Document management                                               │  │
│  │  - Settings/configuration                                            │  │
│  └──────────────────────────────────┬───────────────────────────────────┘  │
│                                     │                                       │
│  ┌──────────────────────────────────▼───────────────────────────────────┐  │
│  │                     FastAPI Backend (:48550)                         │  │
│  │                                                                      │  │
│  │  Endpoints:                                                          │  │
│  │  - GET  /api/status        → Index statistics                       │  │
│  │  - GET  /api/documents     → List indexed documents                 │  │
│  │  - POST /api/upload        → Upload and index file                  │  │
│  │  - DELETE /api/documents/* → Remove from index                      │  │
│  │  - POST /api/chat          → RAG chat with documents                │  │
│  │  - GET  /api/search        → Semantic search                        │  │
│  └───────────────┬────────────────────────────────────┬─────────────────┘  │
│                  │                                    │                     │
│                  ▼                                    ▼                     │
│  ┌───────────────────────────────┐    ┌─────────────────────────────────┐  │
│  │   PostgreSQL + pgvector       │    │        Claude API               │  │
│  │                               │    │                                 │  │
│  │  Tables:                      │    │  Used for:                      │  │
│  │  - documents (metadata)       │    │  - PDF text extraction          │  │
│  │  - chunks (content+vectors)   │    │  - RAG chat responses           │  │
│  │                               │    │                                 │  │
│  │  Vector search via pgvector   │    │  Model: claude-sonnet-4-20250514│  │
│  └───────────────────────────────┘    └─────────────────────────────────┘  │
│                                                                             │
│  ┌───────────────────────────────┐                                         │
│  │   sentence-transformers       │                                         │
│  │   (all-MiniLM-L6-v2)         │                                         │
│  │                               │                                         │
│  │   Local embeddings - no API   │                                         │
│  └───────────────────────────────┘                                         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Component Details

### Server Components

#### React Frontend (`server/web/`)

Modern React application built with Vite:
- **Chat interface** - Conversational RAG with source citations
- **Document management** - Upload, list, delete documents
- **Settings** - API key configuration, connection testing

Technology stack:
- React 18 + TypeScript
- Tailwind CSS for styling
- Vite for build tooling
- nginx for production serving

#### FastAPI Backend (`server/api/main.py`)

The main application handles:
- **File upload and processing** - Receives files, extracts text, chunks, embeds, stores
- **Text extraction** - Routes to appropriate extractor based on file type
- **Chunking** - Splits documents into overlapping chunks for better retrieval
- **Embedding generation** - Uses sentence-transformers locally
- **Vector storage** - Stores chunks and embeddings in PostgreSQL/pgvector
- **RAG chat** - Retrieves relevant chunks and queries Claude

#### PostgreSQL + pgvector

**Why PostgreSQL over ChromaDB:**
- Production-ready with decades of reliability
- Easy backup/restore with standard tools (`pg_dump`)
- Can be managed with standard database tools
- Scales better for larger document collections
- pgvector extension provides efficient vector similarity search

**Schema:**
```sql
-- Document metadata
documents (
    id SERIAL PRIMARY KEY,
    filename VARCHAR(500) UNIQUE,
    file_hash VARCHAR(64),      -- SHA-256 for deduplication
    file_size INTEGER,
    chunk_count INTEGER,
    indexed_at TIMESTAMP
)

-- Document chunks with embeddings
chunks (
    id SERIAL PRIMARY KEY,
    document_id INTEGER,
    filename VARCHAR(500),
    chunk_index INTEGER,
    content TEXT,
    embedding VECTOR(384)       -- 384 dimensions for all-MiniLM-L6-v2
)
```

#### sentence-transformers

**Why local embeddings:**
- No additional API key required
- No per-request cost for embeddings
- Fast enough for document indexing
- `all-MiniLM-L6-v2` is compact (80MB) and effective

**Trade-off:** Embedding model is downloaded during Docker build (~90MB), making first build slower but subsequent starts fast.

#### Claude API

**Used for two purposes:**

1. **PDF Text Extraction** - Claude's native PDF support handles:
   - Password-protected/locked PDFs
   - Scanned documents (via vision)
   - Complex layouts
   - This was proven early in the session when we successfully extracted text from a locked Christian History Magazine PDF

2. **RAG Chat** - Generates responses using retrieved context:
   - System prompt instructs Claude to use provided context
   - Cites sources in responses
   - Admits when information isn't in the documents

### Client Components

#### Obsidian Plugin (`client/obsidian-plugin/`)

**Architecture:**
- TypeScript, built with esbuild
- Registers vault event listeners (create, modify, delete, rename)
- Queue-based sync with configurable interval
- Settings stored in Obsidian's data.json

**Key design decision - Queue-based sync:**

The original implementation used debouncing (2 second delay after each change). This failed for Obsidian's autosave pattern where a user might:
1. Edit a file
2. Wait 5-10 seconds
3. Edit again
4. Wait 5-10 seconds
5. Edit again

With debouncing, each pause would trigger a sync. With queue-based approach:
- All changes are collected in a Set (automatically deduplicated)
- Queue is processed every X minutes (default: 1, configurable 1-60)
- Multiple edits to same file = 1 API call

**Status bar states:**
- `🔮 Knosi` - Idle
- `🕐 Knosi (3)` - 3 files queued
- `🔄 Knosi: 5 files` - Syncing
- `✅ Knosi` - Success
- `❌ Knosi: 2 failed` - Errors

#### Python Watcher (`client/knosi-sync.py`)

**When to use instead of Obsidian plugin:**
- Files added via Finder/Explorer
- Files edited in VS Code, Vim, or other editors
- Batch file operations
- Non-Obsidian workflows

**Architecture:**
- Uses `watchdog` library for filesystem events
- Debounced uploads (2 second delay for rapid changes)
- Hash-based change detection
- Initial sync on startup (can be skipped)

#### Auto-start Scripts (`client/autostart/`)

**macOS (`setup-mac.sh`):**
- Creates launchd plist in `~/Library/LaunchAgents/`
- Interactive setup prompts for server URL, vault path, API key
- Auto-restart on crash
- Logs to `/tmp/knosi-sync.log`

**Windows (`setup-windows.ps1`):**
- Two modes:
  1. Task Scheduler (requires admin) - more robust
  2. Startup folder (no admin) - simpler
- Interactive setup prompts
- Uninstall support via `-Uninstall` flag

## Data Flow

### Document Indexing Flow

```
1. File changed (Obsidian edit OR filesystem change)
           │
           ▼
2. Client detects change
   - Obsidian: Added to queue
   - Python: Debounced, then uploaded
           │
           ▼
3. HTTP POST /api/upload
   - File content + path sent to server
           │
           ▼
4. Server processing:
   a. Compute file hash (SHA-256)
   b. Check if already indexed with same hash → skip if unchanged
   c. Extract text:
      - PDF → Claude API with base64 document
      - DOCX → XML parsing
      - MD/TXT/HTML → Direct decode
   d. Chunk text (4000 chars, 200 overlap)
   e. Generate embeddings (sentence-transformers)
   f. Store in PostgreSQL:
      - Delete old chunks if updating
      - Insert document metadata
      - Insert chunks with embeddings
           │
           ▼
5. Response: {status: "created"|"updated"|"unchanged", chunks: N}
```

### RAG Chat Flow

```
1. User sends message via Web UI or API
           │
           ▼
2. POST /api/chat {message: "...", include_sources: true}
           │
           ▼
3. Server processing:
   a. Generate embedding for query
   b. Vector search: Find top 5 most similar chunks
   c. Build context from retrieved chunks
   d. Query Claude with system prompt + context + question
           │
           ▼
4. Response: {response: "...", sources: [{filename, chunk_index}]}
```

## Configuration

### Server Environment Variables

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API access |
| `POSTGRES_PASSWORD` | Yes | - | Database password |
| `API_SECRET_KEY` | No | `change-me-in-production` | Client auth (disabled if default) |
| `MAX_FILE_SIZE_MB` | No | `100` | Upload limit |
| `CHUNK_SIZE` | No | `4000` | Characters per chunk |
| `CHUNK_OVERLAP` | No | `200` | Overlap between chunks |

### Obsidian Plugin Settings

| Setting | Default | Purpose |
|---------|---------|---------|
| Server URL | `http://localhost:48550` | Server endpoint |
| API Key | empty | Authentication |
| Auto-sync | enabled | Queue files on change |
| Sync interval | 1 minute | Queue processing frequency |
| Sync on startup | enabled | Full sync when Obsidian opens |
| Supported extensions | `.md, .txt, .pdf...` | File types to sync |

## File Support

| Extension | Extraction Method |
|-----------|-------------------|
| `.pdf` | Claude API (handles locked/scanned) |
| `.docx` | XML parsing (python-docx style) |
| `.md` | Direct text |
| `.txt` | Direct text |
| `.org` | Direct text |
| `.rst` | Direct text |
| `.html/.htm` | Direct text |

## Security Considerations

- **API Key Auth** - Optional but recommended for remote access
- **No user management** - Single-user system, simplifies security model
- **CORS enabled** - Required for web UI, consider restricting in production
- **No HTTPS in Docker** - Expects reverse proxy (nginx, Caddy) for TLS
