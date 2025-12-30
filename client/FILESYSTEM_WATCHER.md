# Filesystem Watcher Deployment Guide

The Python filesystem watcher monitors a folder and automatically syncs any new or modified documents to your Knosi server.

**Best for:** Any editor/workflow, catches all filesystem changes (not just Obsidian edits)

---

## Prerequisites

- Python 3.8 or later
- Knosi server already deployed and running
- Server URL and API key (if authentication is enabled)

---

## Installation

### 1. Install Dependencies

```bash
cd client

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# or
venv\Scripts\activate  # Windows

# Install required packages
pip install -r requirements.txt
```

---

## Usage

### Basic Usage

```bash
python knosi-sync.py --server http://your-server:48550 --vault ~/Documents/vault
```

### With API Key

```bash
python knosi-sync.py \
  --server http://your-server:48550 \
  --vault ~/Documents/vault \
  --api-key your-api-secret-key
```

### Skip Initial Sync

If your vault is already synced and you just want to watch for new changes:

```bash
python knosi-sync.py \
  --server http://your-server:48550 \
  --vault ~/Documents/vault \
  --no-initial-sync
```

### All Options

| Flag | Required | Default | Description |
|------|----------|---------|-------------|
| `--server, -s` | Yes | - | Knosi API server URL (port 48550) |
| `--vault, -v` | Yes | - | Local vault/folder path to watch |
| `--api-key, -k` | No | `$KNOSI_API_KEY` env var | API key for authentication |
| `--no-initial-sync` | No | `false` | Skip syncing existing files on startup |
| `--debounce` | No | `2.0` | Seconds to wait after file change before syncing |

---

## Auto-Start on Boot

### macOS (LaunchAgent)

```bash
cd autostart
chmod +x setup-mac.sh
./setup-mac.sh
```

The script will:
1. Create a LaunchAgent plist file
2. Configure it to start on login
3. Load the agent immediately

**Manual control:**
```bash
# Start
launchctl load ~/Library/LaunchAgents/ai.knosi.sync.plist

# Stop
launchctl unload ~/Library/LaunchAgents/ai.knosi.sync.plist

# View logs
tail -f ~/Library/Logs/knosi-sync.log
```

### Windows (Task Scheduler or Startup Folder)

**Option A: Task Scheduler (recommended, runs as service)**

```powershell
cd autostart

# Run with admin privileges
.\setup-windows.ps1
```

**Option B: Startup Folder (simpler, requires login)**

```powershell
cd autostart
.\setup-windows.ps1 -UseStartupFolder
```

**Manual control:**
```powershell
# Start (Task Scheduler method)
Start-ScheduledTask -TaskName "Knosi Sync"

# Stop
Stop-ScheduledTask -TaskName "Knosi Sync"

# Disable
Disable-ScheduledTask -TaskName "Knosi Sync"

# View logs
Get-Content $env:USERPROFILE\knosi-sync.log -Tail 50 -Wait
```

---

## Supported File Types

The watcher syncs files with these extensions:

- `.md` - Markdown
- `.txt` - Plain text
- `.pdf` - PDF documents
- `.html`, `.htm` - HTML
- `.org` - Org-mode
- `.rst` - reStructuredText
- `.docx` - Word documents

Files are filtered server-side, so unsupported types will be rejected.

---

## How It Works

```
┌─────────────────────────────────────────────┐
│  Your Vault/Folder                          │
│  ~/Documents/vault/                         │
│                                             │
│  ┌──────────────────────────────────────┐   │
│  │  Python Watcher (knosi-sync.py)      │   │
│  │  - Monitors filesystem changes       │   │
│  │  - Debounces rapid edits             │   │
│  │  - Queues uploads                    │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │
                  │ HTTP POST
                  ▼
         ┌────────────────────┐
         │  Knosi Server      │
         │  :48550/api/upload │
         └────────────────────┘
```

**Debouncing:**
- File changes trigger a 2-second timer
- If file changes again within 2s, timer resets
- File only uploads after 2s of no changes
- Prevents multiple uploads during rapid edits/autosaves

---

## Troubleshooting

### "Connection failed - is server running?"

```bash
# Test server connectivity
curl http://your-server:48550/api/status

# Check firewall allows port 48550
# Check SERVER_URL in server's .env is correct
```

### "Auth failed: Check API key"

```bash
# Ensure API key matches server's .env
cat ~/knosi/server/.env | grep API_SECRET_KEY

# Pass via environment variable
export KNOSI_API_KEY="your-key-here"
python knosi-sync.py --server ... --vault ...
```

### Files not syncing

```bash
# Check watcher logs
# macOS:
tail -f ~/Library/Logs/knosi-sync.log

# Windows:
Get-Content $env:USERPROFILE\knosi-sync.log -Tail 50 -Wait

# Run in foreground to see errors
python knosi-sync.py --server ... --vault ...
```

### Large PDFs timing out

```bash
# Server may need more time to process
# Check server logs:
cd ~/knosi/server
sudo docker compose logs -f api

# Increase MAX_FILE_SIZE_MB in server .env if needed
```

### Watcher using too much CPU

```bash
# Increase debounce delay to reduce processing frequency
python knosi-sync.py \
  --server http://your-server:48550 \
  --vault ~/Documents/vault \
  --debounce 5.0  # Wait 5 seconds instead of 2
```

---

## Comparison: Watcher vs Obsidian Plugin

| Feature | Filesystem Watcher | Obsidian Plugin |
|---------|-------------------|-----------------|
| **Catches edits from** | Any app (Finder, VSCode, etc.) | Obsidian only |
| **Auto-start** | macOS/Windows scripts | Built into Obsidian |
| **Setup complexity** | Medium | Easy |
| **CPU usage** | Higher (monitors all files) | Lower (event-based) |
| **Best for** | Multi-editor workflows | Obsidian-only workflows |
| **Sync queue** | No (immediate with debounce) | Yes (batched every N minutes) |

**Recommendation:**
- Use **Obsidian Plugin** if you only edit in Obsidian
- Use **Filesystem Watcher** if you use multiple editors or add files via Finder/Explorer

---

## Advanced Configuration

### Custom Debounce for Large Vaults

If you have a large vault with frequent changes:

```bash
python knosi-sync.py \
  --server http://your-server:48550 \
  --vault ~/Documents/vault \
  --debounce 10.0  # Wait 10 seconds
```

### Multiple Vaults

Run multiple instances with different configurations:

```bash
# Terminal 1: Work vault
python knosi-sync.py -s http://server:48550 -v ~/Work -k key1

# Terminal 2: Personal vault
python knosi-sync.py -s http://server:48550 -v ~/Personal -k key1
```

For auto-start, duplicate the LaunchAgent/Task with different names.

---

## Security Notes

- API key is passed as command-line argument (visible in process list)
- For better security, use environment variable:
  ```bash
  export KNOSI_API_KEY="your-key"
  python knosi-sync.py -s ... -v ...  # No -k flag needed
  ```
- Never commit `.env` or config files with API keys to git
- Use firewall to restrict access to Knosi server ports

---

## Next Steps

1. **Test the watcher**: Make a change to a file in your vault
2. **Check server**: Visit `http://your-server:48080` to see uploaded files
3. **Set up auto-start**: Use the scripts in `autostart/`
4. **Monitor logs**: Ensure syncing works reliably
5. **Try chatting**: Use the web UI to chat with your documents

---

Built with ❤️ by [Knosi](https://knosi.ai)
