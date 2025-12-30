# Knosi

**Your personal knowledge base, powered by AI.**

Knosi is a self-hosted platform for indexing and chatting with your documents. Upload PDFs, Markdown, and other files to get AI-powered answers grounded in your content.

🌐 **[knosi.ai](https://knosi.ai)**

---

## Quick Overview

```
┌─────────────────────────────────────┐      ┌──────────────────────────────────────────────┐
│          LOCAL MACHINE              │      │              REMOTE SERVER (Docker)          │
│                                     │      │                                              │
│  ┌───────────────────────────────┐  │      │  ┌────────────────────────────────────────┐ │
│  │  Obsidian Plugin              │  │      │  │         React Frontend (:48080)        │ │
│  │  - or -                       │  │      │  └───────────────────┬────────────────────┘ │
│  │  Filesystem Watcher           │  │      │                      │                      │
│  └───────────────┬───────────────┘  │      │                      ▼                      │
│                  │                  │ HTTP │  ┌────────────────────────────────────────┐ │
│                  └──────────────────┼─────►│  │      FastAPI Backend (:48550)          │ │
│                                     │      │  └───────────────────┬────────────────────┘ │
│  ┌───────────────────────────────┐  │      │           ┌──────────┴──────────┐           │
│  │        Your Vault             │  │      │           ▼                     ▼           │
│  │        (Documents)            │  │      │  ┌─────────────────┐   ┌─────────────────┐  │
│  └───────────────────────────────┘  │      │  │   PostgreSQL    │   │   Claude API    │  │
│                                     │      │  │   + pgvector    │   │                 │  │
└─────────────────────────────────────┘      │  └─────────────────┘   └─────────────────┘  │
                                             └──────────────────────────────────────────────┘
```

---

## Features

- 🔒 **Complete Privacy** - Self-hosted, your data never leaves your control
- 📄 **No File Limits** - Upload PDFs of any size (default 100MB, configurable)
- ⚡ **Powered by Claude** - State-of-the-art PDF parsing and RAG chat
- 🔍 **Semantic Search** - Advanced vector search with pgvector
- 🔄 **Auto-Sync** - Obsidian plugin and filesystem watcher for automatic uploads
- ⚙️ **Fully Configurable** - Customize embedding models, chunk sizes, and more

---

## Documentation

📚 **Deployment Guides:**
- **[Server Deployment](DEPLOYMENT.md)** - Deploy Knosi on a VPS with Docker
- **[Obsidian Plugin](client/obsidian-plugin/DEPLOYMENT.md)** - Sync your Obsidian vault
- **[Filesystem Watcher](client/FILESYSTEM_WATCHER.md)** - Watch any folder for changes

📖 **Additional Documentation:**
- [CONTEXT.md](docs/CONTEXT.md) - Why this project exists, problems it solves
- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Technical design and component details
- [DECISIONS.md](docs/DECISIONS.md) - Key decisions and their rationale
- [CURRENT_STATE.md](docs/CURRENT_STATE.md) - What's complete, what's not, next steps

---

## Quick Start

### 1. Deploy the Server

Follow the **[Server Deployment Guide](DEPLOYMENT.md)** to:
- Set up Docker on your VPS
- Configure environment variables
- Start the Knosi services

Services will be available at:
- **Web UI**: `http://your-server:48080`
- **API**: `http://your-server:48550`

### 2. Choose a Client

Pick one based on your workflow:

| Client | Best For | Guide |
|--------|----------|-------|
| **Obsidian Plugin** | Obsidian-only workflows | [Obsidian Deployment Guide](client/obsidian-plugin/DEPLOYMENT.md) |
| **Filesystem Watcher** | Any editor, catches all filesystem changes | [Watcher Deployment Guide](client/FILESYSTEM_WATCHER.md) |

### 3. Start Syncing

- **Obsidian**: Enable plugin, configure server URL, files sync automatically
- **Watcher**: Run `python knosi-sync.py --server ... --vault ...`

### 4. Chat with Your Documents

Visit `http://your-server:48080` and start asking questions!

---

## Supported File Types

- 📕 PDF (parsed via Claude API - handles locked PDFs)
- 📝 Markdown (.md)
- 📄 Plain text (.txt)
- 🌐 HTML (.html, .htm)
- 📋 Org-mode (.org)
- 📜 reStructuredText (.rst)
- 📘 Word documents (.docx)

---

## Architecture

| Service | Port | Description |
|---------|------|-------------|
| **Web** | 48080 | React frontend - chat UI, document management |
| **API** | 48550 | FastAPI backend - indexing, search, chat |
| **DB** | 5432 (internal) | PostgreSQL + pgvector for embeddings |

### Client Comparison

| Client | Auto-start | Catches | Sync Strategy |
|--------|------------|---------|---------------|
| **Obsidian Plugin** | Built-in | Obsidian edits only | Queue-based (batched) |
| **Filesystem Watcher** | macOS/Windows scripts | All filesystem changes | Immediate (debounced) |

**Recommendation:**
- Use **Obsidian Plugin** for Obsidian-only workflows (simpler setup)
- Use **Filesystem Watcher** for multi-editor workflows or external file changes

---

## Configuration

### Server Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key for PDF parsing and chat |
| `POSTGRES_PASSWORD` | Yes | - | PostgreSQL database password |
| `API_SECRET_KEY` | No | `change-me-in-production` | Client authentication key |
| `MAX_FILE_SIZE_MB` | No | `100` | Maximum upload size in MB |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `EMBEDDING_DIM` | No | `384` | Embedding dimension (must match model) |

See **[Server Deployment Guide](DEPLOYMENT.md)** for full configuration details.

### Embedding Models

| Model | Dimensions | Accuracy | Best For |
|-------|------------|----------|----------|
| `all-MiniLM-L6-v2` (default) | 384 | 78.1% | General use, fast |
| `BAAI/bge-base-en-v1.5` | 768 | 84.7% | High-quality retrieval |
| `all-mpnet-base-v2` | 768 | Higher | Best quality, slower |

⚠️ **IMPORTANT:** Changing embedding models requires clearing the database and re-indexing documents. See [Server Deployment Guide](DEPLOYMENT.md) for details.

---

## API Endpoints

Base URL: `http://your-server:48550`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Server status and document count |
| `/api/documents` | GET | List indexed documents |
| `/api/upload` | POST | Upload and index a file |
| `/api/documents/{filename}` | DELETE | Remove document from index |
| `/api/chat` | POST | Chat with documents (RAG) |
| `/api/search?q=...` | GET | Semantic search |

---

## Backups

PostgreSQL data is stored in a Docker volume or block storage. To backup:

```bash
# Backup database
docker exec knosi-db pg_dump -U knosi knosi > backup-$(date +%Y%m%d).sql

# Restore database
cat backup.sql | docker exec -i knosi-db psql -U knosi knosi
```

For block storage backups, see [Server Deployment Guide](DEPLOYMENT.md).

---

## Development

### Running Locally

```bash
cd server

# Start database only
docker compose up -d db

# Run API locally (with hot reload)
cd api
pip install -r requirements.txt
DATABASE_URL=postgresql+asyncpg://knosi:password@localhost:5432/knosi \
ANTHROPIC_API_KEY=sk-ant-xxx \
uvicorn main:app --reload --port 48550

# Run web locally (with hot reload)
cd ../web
npm install
npm run dev  # Runs on http://localhost:3000
```

### Building Obsidian Plugin

```bash
cd client/obsidian-plugin
npm install
npm run build  # Output: main.js
```

---

## Troubleshooting

### Server Issues

**"Cannot connect to server"**
```bash
# Check if API is accessible
curl http://your-server:48550/api/status

# Check logs
cd ~/knosi/server
docker compose logs -f api
```

**"Auth failed: Check API key"**
- Ensure client's API key matches server's `API_SECRET_KEY` in `.env`

### Client Issues

**Obsidian Plugin:**
- See [Obsidian Deployment Guide](client/obsidian-plugin/DEPLOYMENT.md#troubleshooting)

**Filesystem Watcher:**
- See [Watcher Deployment Guide](client/FILESYSTEM_WATCHER.md#troubleshooting)

---

## Security Checklist

- ✅ Changed default `POSTGRES_PASSWORD`
- ✅ Changed default `API_SECRET_KEY`
- ✅ Firewall configured (ports 48080, 48550)
- ✅ HTTPS enabled (if public-facing)
- ✅ Regular backups configured
- ✅ Keep system updated: `sudo apt update && sudo apt upgrade`

---

## Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

---

## License

MIT License - See [LICENSE](LICENSE) file for details.

---

## Links

- 🌐 Website: [knosi.ai](https://knosi.ai)
- 📦 GitHub: [github.com/a11smiles/knosi](https://github.com/a11smiles/knosi)
- 📖 Documentation: See `docs/` folder
- 🐛 Issues: [github.com/a11smiles/knosi/issues](https://github.com/a11smiles/knosi/issues)

---

Built with ❤️ by [Knosi](https://knosi.ai)
