# Knosi - Current State & Next Steps

## Project Status: POC/Early MVP

As of December 24, 2024, Knosi is a functional proof-of-concept approaching MVP status.

### What's Complete

#### Server (Ready for Deployment)
- [x] FastAPI backend with all core endpoints
- [x] React frontend with chat, documents, settings
- [x] PostgreSQL + pgvector for vector storage
- [x] Claude API integration for PDF parsing and chat
- [x] Local embeddings with sentence-transformers
- [x] Docker Compose configuration
- [x] API key authentication (optional)
- [x] File hash-based deduplication

#### Obsidian Plugin (Ready for Testing)
- [x] Queue-based sync with configurable interval
- [x] Settings UI for all configuration options
- [x] Status bar with queue count
- [x] Commands: sync current, sync all, view queue, process now
- [x] Build configuration (esbuild, TypeScript)
- [ ] Not yet built - needs `npm install && npm run build`
- [ ] Not tested in actual Obsidian environment

#### Python Watcher (Ready for Testing)
- [x] Filesystem watching with watchdog
- [x] Debounced uploads
- [x] Initial sync on startup
- [x] Hash-based change detection
- [ ] Not tested on Windows

#### Auto-start Scripts (Ready for Testing)
- [x] macOS launchd setup script
- [x] Windows PowerShell setup script (Task Scheduler + Startup folder modes)
- [ ] Not tested on actual systems

### What's NOT Complete

1. **No HTTPS** - Server assumes reverse proxy handles TLS
2. **No rate limiting** - Could be overwhelmed by rapid requests
3. **No chat history** - Each chat is stateless
4. **No document preview** - Can't view source documents in web UI
5. **No Obsidian chat** - Must use web UI or API for queries
6. **No tests** - No unit or integration tests written

### Known Issues / Risks

1. **Large PDF token cost** - Extracting 50+ page PDFs uses significant Claude tokens
2. **Sync on startup** - If vault is large, initial sync could be slow/expensive
3. **No offline mode** - Obsidian plugin requires server connectivity
4. **Docker build time** - First build downloads embedding model (~90MB)

## Files in This Project

```
knosi/
├── README.md                          # Main documentation
├── CLAUDE.md                          # Claude Code context
├── docs/
│   ├── CONTEXT.md                     # Origin story and rationale
│   ├── ARCHITECTURE.md                # Technical design
│   ├── DECISIONS.md                   # Decision log
│   └── CURRENT_STATE.md               # This file
├── server/
│   ├── docker-compose.yml             # Container orchestration
│   ├── .env.example                   # Environment template
│   ├── api/
│   │   ├── Dockerfile                 # API container
│   │   ├── requirements.txt           # Python dependencies
│   │   └── main.py                    # FastAPI application
│   └── web/
│       ├── Dockerfile                 # Web container (nginx)
│       ├── nginx.conf                 # nginx configuration
│       ├── package.json               # Node dependencies
│       └── src/                       # React source files
│           ├── App.tsx
│           ├── api.ts
│           └── components/
└── client/
    ├── knosi-sync.py                  # Python filesystem watcher
    ├── requirements.txt               # Python dependencies
    ├── obsidian-plugin/
    │   ├── manifest.json              # Plugin metadata
    │   ├── main.ts                    # Plugin code
    │   ├── package.json               # Node dependencies
    │   └── README.md                  # Plugin documentation
    └── autostart/
        ├── setup-mac.sh               # macOS launchd setup
        ├── setup-windows.ps1          # Windows Task Scheduler setup
        └── README.md                  # Auto-start documentation
```

## Deployment Checklist

### Server (Vultr VPS)

1. [ ] SSH into VPS
2. [ ] Install Docker and Docker Compose
3. [ ] Clone/copy `server/` directory
4. [ ] Copy `.env.example` to `.env`
5. [ ] Configure `.env`:
   - [ ] Set `ANTHROPIC_API_KEY`
   - [ ] Set `POSTGRES_PASSWORD`
   - [ ] Set `API_SECRET_KEY` (generate secure random string)
6. [ ] Run `docker compose up -d`
7. [ ] Verify API: `curl http://localhost:48550/api/status`
8. [ ] Verify Web: `curl http://localhost:48080`
9. [ ] (Optional) Set up reverse proxy with HTTPS

### Obsidian Plugin

1. [ ] Copy `client/obsidian-plugin/` to vault's `.obsidian/plugins/knosi-sync/`
2. [ ] Run `npm install`
3. [ ] Run `npm run build`
4. [ ] Enable plugin in Obsidian settings
5. [ ] Configure server URL and API key
6. [ ] Test with "Check server status" command
7. [ ] Run initial sync with "Sync all files"

### Python Watcher (Alternative to Plugin)

1. [ ] Install Python 3.8+
2. [ ] Run `pip install -r client/requirements.txt`
3. [ ] Run: `python client/knosi-sync.py --server http://SERVER:48550 --vault ~/vault --api-key KEY`
4. [ ] (Optional) Configure auto-start with scripts in `client/autostart/`

## Suggested Next Steps for Claude Code

When continuing development in Claude Code:

1. **Test the server**
   - Build and run Docker containers
   - Upload test documents
   - Verify chat functionality

2. **Build and test Obsidian plugin**
   - Run `npm install && npm run build`
   - Install in test vault
   - Verify sync behavior

3. **Add error handling improvements**
   - Better error messages for common failures
   - Retry logic for transient errors

4. **Consider adding tests**
   - Unit tests for text extraction
   - Unit tests for chunking
   - Integration tests for API endpoints

5. **Performance optimization**
   - Profile large document processing
   - Consider async/parallel chunk embedding

6. **Documentation**
   - API documentation (OpenAPI/Swagger)
   - Troubleshooting guide
   - Video walkthrough

## Session History Reference

The full conversation history is preserved in:
`/mnt/transcripts/2025-12-24-08-35-56-khoj-setup-knosi-build.txt`

Key milestones in that transcript:
1. Khoj self-hosted setup and troubleshooting
2. Discovery of 10MB limit
3. Claude Projects exploration
4. Puppeteer automation attempt
5. Decision to build Knosi v1 (ChromaDB)
6. Pivot to v2 (PostgreSQL + pgvector)
7. Addition of Obsidian plugin
8. Queue-based sync implementation
9. Auto-start scripts for Mac/Windows
