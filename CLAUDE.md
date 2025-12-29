# CLAUDE.md - Project Context for Claude Code

## What is Knosi?

**Knosi** (from Greek *gnosis* - knowledge) is a self-hosted knowledge base platform. It lets you:
1. Upload/sync documents (PDFs, Markdown, text files, etc.)
2. Have them automatically indexed with vector embeddings
3. Chat with your documents using Claude

🌐 **Website**: [knosi.ai](https://knosi.ai)

## Why was it built?

It's author (Joshua) needed to index large theological PDFs for his ministry work. Existing solutions failed:
- **Khoj** - 10MB file size limit, complex auth requirements
- **Claude Projects** - No API for automation, manual uploads only

Knosi is a minimal alternative that:
- Has no file size limit (default 100MB, configurable)
- Uses Claude's native PDF parsing (handles locked/protected PDFs)
- Is simple to deploy and maintain (~500 lines of Python)

## Project Structure

```
knosi/
├── server/
│   ├── docker-compose.yml      # Orchestrates all services
│   ├── .env.example
│   ├── api/                    # FastAPI backend (port 48550)
│   │   ├── Dockerfile
│   │   ├── requirements.txt
│   │   └── main.py
│   └── web/                    # React frontend (port 48080)
│       ├── Dockerfile
│       ├── nginx.conf
│       ├── package.json
│       └── src/
├── client/
│   ├── knosi-sync.py           # Python filesystem watcher
│   ├── obsidian-plugin/        # Obsidian integration
│   └── autostart/              # Mac/Windows auto-start scripts
└── docs/                       # Detailed documentation
```

## Key Technical Decisions

1. **PostgreSQL + pgvector** over ChromaDB - production-ready, easy backups
2. **Claude API for PDF parsing** - proven to work on locked PDFs
3. **sentence-transformers for embeddings** - no extra API key needed
4. **Queue-based Obsidian sync** - batches changes to reduce API calls
5. **API key auth** - simple, optional, single-user focused
6. **React + Vite frontend** - extensible, modern tooling

## Current State

- **Server**: Ready for deployment, needs testing
- **Obsidian plugin**: Code complete, needs build (`npm install && npm run build`)
- **Python watcher**: Ready for testing
- **Auto-start scripts**: Ready for testing

## How to Test

### Server
```bash
cd server
cp .env.example .env
# Edit .env with ANTHROPIC_API_KEY, POSTGRES_PASSWORD, API_SECRET_KEY
docker compose up -d
curl http://localhost:48550/api/status  # API
open http://localhost:48080              # Web UI
```

### Obsidian Plugin
```bash
cd client/obsidian-plugin
npm install
npm run build
# Copy to .obsidian/plugins/knosi-sync/ in a test vault
```

## Key Files

| File | Purpose |
|------|---------|
| `server/api/main.py` | FastAPI application - all backend logic |
| `server/web/src/App.tsx` | React app entry point |
| `server/web/src/api.ts` | API client for frontend |
| `server/docker-compose.yml` | Service orchestration |
| `client/knosi-sync.py` | Python filesystem watcher |
| `client/obsidian-plugin/main.ts` | Obsidian plugin |
| `docs/DECISIONS.md` | Why things are built the way they are |

## API Endpoints

Base URL: `http://your-server:48550`

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/status` | GET | Health check, document/chunk counts |
| `/api/documents` | GET | List all indexed documents |
| `/api/upload` | POST | Upload and index a file |
| `/api/documents/{path}` | DELETE | Remove document from index |
| `/api/chat` | POST | Chat with documents (RAG) |
| `/api/search` | GET | Semantic search |

## Environment Variables (Server)

| Variable | Required | Default | Purpose |
|----------|----------|---------|---------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API |
| `POSTGRES_PASSWORD` | Yes | - | Database |
| `API_SECRET_KEY` | No | `change-me-in-production` | Auth |
| `MAX_FILE_SIZE_MB` | No | `100` | Upload limit |

## User Context

Joshua (the user) is:
- CEO of Discipled Church, a nonprofit ministry
- Self-hosts on Vultr VPS
- Uses Obsidian for document management
- Works with theological documents and PDFs
- Values reliability and cost-effectiveness

## What Might Need Work

1. No tests written yet
2. No HTTPS (expects reverse proxy)
3. Large PDFs cost significant tokens to index
4. Obsidian plugin not tested in real environment
5. Windows scripts not tested on Windows
