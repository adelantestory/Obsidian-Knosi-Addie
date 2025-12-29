# Knosi

**Your personal knowledge base, powered by AI.**

Knosi is a self-hosted platform for indexing and chatting with your documents. Upload PDFs, Markdown, and other files to get AI-powered answers grounded in your content.

🌐 **[knosi.ai](https://knosi.ai)**

> **📚 Project Documentation**
> 
> See the `docs/` folder for detailed context:
> - [CONTEXT.md](docs/CONTEXT.md) - Why this project exists, problems it solves
> - [ARCHITECTURE.md](docs/ARCHITECTURE.md) - Technical design and component details
> - [DECISIONS.md](docs/DECISIONS.md) - Key decisions and their rationale
> - [CURRENT_STATE.md](docs/CURRENT_STATE.md) - What's complete, what's not, next steps

## Architecture

```
┌─────────────────────────────────────┐      ┌──────────────────────────────────────────────┐
│          LOCAL MACHINE              │      │              REMOTE SERVER (Docker)          │
│                                     │      │                                              │
│  ┌───────────────────────────────┐  │      │  ┌────────────────────────────────────────┐ │
│  │  Obsidian Plugin              │  │      │  │         React Frontend (:48080)        │ │
│  │  - or -                       │  │      │  └───────────────────┬────────────────────┘ │
│  │  knosi-sync.py                │  │      │                      │                      │
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

## Services

| Service | Port | Description |
|---------|------|-------------|
| **Web** | 48080 | React frontend - chat UI, document management |
| **API** | 48550 | FastAPI backend - all business logic |
| **DB** | 5432 (internal) | PostgreSQL + pgvector |

## Client Options

| Client | Best For | Auto-start | Catches |
|--------|----------|------------|---------|
| **Obsidian Plugin** | Obsidian-only workflows | Built-in | Obsidian edits only |
| **Python Script** | Any editor, CLI, Finder | macOS/Windows | All filesystem changes |

## Quick Start

### 1. Deploy Server (on your VPS)

```bash
cd server

# Configure environment
cp .env.example .env
nano .env  # Add your ANTHROPIC_API_KEY, POSTGRES_PASSWORD, API_SECRET_KEY

# Optional: Configure block storage for PostgreSQL data
# If you want to use separate block storage (recommended for large document collections):
# 1. Find block device UUID: sudo blkid /dev/vdb
# 2. Add to /etc/fstab for auto-mount on reboot:
#    UUID=your-uuid  /mnt/knosi-data  ext4  defaults,nofail  0  2
# 3. Mount: sudo mkdir -p /mnt/knosi-data && sudo mount -a
# 4. Set ownership: sudo chown -R 999:999 /mnt/knosi-data
# 5. Add to .env: POSTGRES_DATA_PATH=/mnt/knosi-data

# Start services
docker compose up -d

# Check logs
docker compose logs -f api
```

Services will be available at:
- **Web UI**: `http://your-server:48080`
- **API**: `http://your-server:48550`

### 2. Install Client (choose one)

#### Option A: Obsidian Plugin

```bash
# Copy plugin to your vault
cp -r client/obsidian-plugin /path/to/your/vault/.obsidian/plugins/knosi-sync

# Build the plugin
cd /path/to/your/vault/.obsidian/plugins/knosi-sync
npm install
npm run build
```

Then enable in Obsidian: Settings → Community Plugins → Enable "Knosi Sync"

Configure in Settings → Knosi Sync:
- Set your server URL (API endpoint: `http://your-server:48550`)
- Set API key (if required)
- Enable auto-sync

#### Option B: Python Script (watches all filesystem changes)

```bash
cd client

# Create virtual environment (optional but recommended)
python3 -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows

# Install dependencies
pip install -r requirements.txt
```

### 3. Run Python Client (if using Option B)

```bash
# Basic usage
python knosi-sync.py --server http://your-server:48550 --vault ~/Documents/vault

# With API key
python knosi-sync.py \
  --server http://your-server:48550 \
  --vault ~/Documents/vault \
  --api-key your-api-secret-key

# Skip initial sync (if vault already synced)
python knosi-sync.py \
  --server http://your-server:48550 \
  --vault ~/Documents/vault \
  --no-initial-sync
```

### 4. Auto-start Python Client (Optional)

#### macOS

```bash
cd client/autostart
chmod +x setup-mac.sh
./setup-mac.sh
```

#### Windows (PowerShell)

```powershell
cd client\autostart

# With admin (uses Task Scheduler):
.\setup-windows.ps1

# Without admin (uses Startup folder):
.\setup-windows.ps1 -UseStartupFolder
```

See `client/autostart/README.md` for manual control commands.

## Configuration

### Server Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ANTHROPIC_API_KEY` | Yes | - | Claude API key |
| `POSTGRES_PASSWORD` | Yes | - | PostgreSQL password |
| `API_SECRET_KEY` | No | `change-me-in-production` | Client auth key (disabled if unchanged) |
| `MAX_FILE_SIZE_MB` | No | `100` | Max upload size |
| `CHUNK_SIZE` | No | `4000` | Characters per chunk |
| `CHUNK_OVERLAP` | No | `200` | Overlap between chunks |

### Client Options

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--server, -s` | Yes | - | API Server URL (port 48550) |
| `--vault, -v` | Yes | - | Local vault path |
| `--api-key, -k` | No | `$KNOSI_API_KEY` | API key |
| `--no-initial-sync` | No | `false` | Skip initial sync |
| `--debounce` | No | `2.0` | Debounce delay (seconds) |

## API Endpoints

Base URL: `http://your-server:48550`

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Server status and stats |
| `/api/documents` | GET | List indexed documents |
| `/api/upload` | POST | Upload and index a file |
| `/api/documents/{filename}` | DELETE | Remove from index |
| `/api/chat` | POST | Chat with documents |
| `/api/search?q=...` | GET | Search documents |

## Supported File Types

- PDF (parsed via Claude API)
- Markdown (.md)
- Plain text (.txt)
- Org-mode (.org)
- reStructuredText (.rst)
- HTML (.html, .htm)
- Word documents (.docx)

## Backups

PostgreSQL data is stored in a Docker volume. To backup:

```bash
# Backup
docker exec knosi-db pg_dump -U knosi knosi > backup.sql

# Restore
cat backup.sql | docker exec -i knosi-db psql -U knosi knosi
```

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
npm run dev  # Runs on http://localhost:3000, proxies API to :48550
```

## Troubleshooting

**"Connection failed - is server running?"**
- Check if API is accessible: `curl http://your-server:48550/api/status`
- Check firewall allows ports 48080 and 48550

**"Auth failed: Check API key"**
- Ensure `--api-key` matches server's `API_SECRET_KEY`

**Large PDFs timing out**
- Increase client timeout (edit knosi-sync.py)
- Check server logs: `docker compose logs api`

**Embeddings slow on first run**
- Model downloads on first container build (~90MB)
- Subsequent starts are fast (model cached in image)

---

Built with ❤️ by [Knosi](https://knosi.ai)
