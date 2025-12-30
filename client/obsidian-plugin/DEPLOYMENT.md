# Obsidian Plugin Deployment Guide

The Knosi Sync plugin for Obsidian automatically syncs your vault to your Knosi server using a smart queue-based system.

**Best for:** Obsidian-only workflows, minimal setup, built-in auto-start

---

## Features

- ✅ **Queue-based sync** - Batches changes to reduce API calls
- ✅ **Configurable interval** - Sync every 1-60 minutes (default: 1 minute)
- ✅ **Sync on startup** - Optionally sync all files when Obsidian opens
- ✅ **Manual controls** - Sync current file immediately, process queue now, or sync entire vault
- ✅ **Status bar** - Shows sync status and pending file count
- ✅ **Smart deduplication** - Each file synced once even if modified multiple times

---

## Prerequisites

- Obsidian installed
- Knosi server already deployed and running
- Node.js and npm installed (for building the plugin)

---

## Installation

### Option 1: Build from Source (Current Method)

```bash
# Copy plugin to your vault
cp -r client/obsidian-plugin /path/to/your/vault/.obsidian/plugins/knosi-sync

# Build the plugin
cd /path/to/your/vault/.obsidian/plugins/knosi-sync
npm install
npm run build
```

### Option 2: Manual Install (Pre-built)

If someone provides you with pre-built files:

1. Create folder: `.obsidian/plugins/knosi-sync/`
2. Copy these files into it:
   - `main.js`
   - `manifest.json`
   - `styles.css` (if exists)

### Enable the Plugin

1. Open Obsidian
2. Go to **Settings** → **Community Plugins**
3. Turn off **Restricted Mode** (if enabled)
4. Click **Browse** or **Reload** plugins
5. Find **Knosi Sync** and click **Enable**

---

## Configuration

Open **Settings** → **Knosi Sync**:

| Setting | Description | Default |
|---------|-------------|---------|
| **Server URL** | Your Knosi API server URL | `http://localhost:48550` |
| **API Key** | Authentication key (if required) | empty |
| **Auto-sync** | Queue files automatically on change | ✅ enabled |
| **Sync interval** | Minutes between queue processing (1-60) | 1 minute |
| **Sync on startup** | Sync all files when Obsidian opens | ✅ enabled |
| **Supported extensions** | File types to sync | `.md, .txt, .pdf, .html, .htm, .org, .rst` |

### Getting Your Server URL

Your server URL should be the API endpoint (port **48550**, not 48080):

```
✅ Correct:   http://your-server:48550
✅ Correct:   https://your-domain.com/api  (if using reverse proxy)
❌ Wrong:     http://your-server:48080  (this is the web UI port)
```

### Getting Your API Key

Check your server's `.env` file:

```bash
# On your server
cat ~/knosi/server/.env | grep API_SECRET_KEY
```

If it's set to `change-me-in-production`, authentication is disabled (you can leave API key empty).

---

## How It Works

```
File modified → Added to queue → Queue processed every X minutes → Upload to server
                     │                        │
                     │                        └── Deduped: each file synced once
                     └── Status bar shows: 🕐 Knosi (3) = 3 files pending
```

**Why queue-based?**
- Obsidian's autosave can trigger 5-10 modifications per minute
- Without queuing, that's 5-10 API calls per file
- With queuing, all changes in 1 minute = 1 API call

**Example:**
1. You edit `note.md` at 10:00:00
2. Plugin adds it to queue → Status bar shows `🕐 Knosi (1)`
3. You edit it again at 10:00:30
4. Still in queue (no duplicate)
5. At 10:01:00, queue processes → File uploads once
6. Status bar shows `✅ Knosi` briefly, then `🔮 Knosi` (idle)

---

## Commands

Access via **Command Palette** (Cmd/Ctrl + P):

| Command | Description |
|---------|-------------|
| **Sync current file (immediate)** | Upload the currently open file right now (bypasses queue) |
| **Process sync queue now** | Sync all pending files without waiting for interval |
| **View pending sync queue** | See which files are waiting to sync |
| **Sync all files** | Upload all supported files in vault (bypasses queue) |
| **Check server status** | Test connection to server |

---

## Status Bar Icons

The status bar in the bottom-right shows sync status:

| Icon | Meaning |
|------|---------|
| 🔮 Knosi | Idle, nothing pending |
| 🕐 Knosi (3) | 3 files queued for next sync |
| 🔄 Knosi: 5 files | Syncing 5 files in progress |
| ✅ Knosi | Sync completed successfully |
| ❌ Knosi: 2 failed | Some files failed to sync |

---

## Supported File Types

By default, these extensions are synced:

- `.md` - Markdown
- `.txt` - Plain text
- `.pdf` - PDF documents
- `.html`, `.htm` - HTML
- `.org` - Org-mode
- `.rst` - reStructuredText

You can customize this in Settings → Knosi Sync → Supported extensions.

---

## Testing the Setup

### 1. Test Connection

1. Open Command Palette (Cmd/Ctrl + P)
2. Type "Knosi: Check server status"
3. You should see: `✅ Connected: 0 documents, 0 chunks`

If you see an error:
- ❌ `Cannot connect` → Check server URL and firewall
- ❌ `Authentication failed` → Check API key

### 2. Test Sync

1. Create a new note: `test-sync.md`
2. Write some content
3. Watch status bar → Should show `🕐 Knosi (1)`
4. Wait 1 minute (or run "Process sync queue now")
5. Status bar should show `🔄 Knosi: 1 file` then `✅ Knosi`
6. Check web UI at `http://your-server:48080` → Document should appear

---

## Troubleshooting

### "Cannot connect to server"

```bash
# Test server from terminal
curl http://your-server:48550/api/status

# Should return: {"status":"ok","document_count":0,"chunk_count":0}
```

**If curl fails:**
- Check server is running: `docker compose ps`
- Check firewall allows port 48550
- Check you're using API port (48550) not web port (48080)

### "Authentication failed - check API key"

1. Check server's `.env` file:
   ```bash
   cat ~/knosi/server/.env | grep API_SECRET_KEY
   ```
2. Copy the value to Obsidian Settings → Knosi Sync → API Key
3. Restart Obsidian (optional but recommended)

### Files not syncing

1. Check status bar → Should show pending count
2. View queue: Command Palette → "View pending sync queue"
3. Manually trigger: Command Palette → "Process sync queue now"
4. Check Obsidian console: View → Toggle Developer Tools → Console tab

### "Restart Obsidian for auto-sync changes to take effect"

If you toggle Auto-sync or change sync interval, you need to restart Obsidian for changes to apply.

### Queue growing too large

If you have hundreds of pending files:

1. Reduce sync interval: Settings → Knosi Sync → Sync interval → Set to 1 minute
2. Manually process: Command Palette → "Process sync queue now"
3. Or sync all at once: Command Palette → "Sync all files"

---

## Important Notes

### What the Plugin Catches

✅ **Plugin catches:**
- Creating new files in Obsidian
- Editing files in Obsidian
- Renaming files in Obsidian
- Deleting files in Obsidian

❌ **Plugin does NOT catch:**
- Files added via Finder/Explorer
- Files edited in other apps (VSCode, etc.)
- Files moved/renamed outside Obsidian

**Solution:** After adding files externally, run "Sync all files" command.

### For External File Changes

If you frequently add/edit files outside Obsidian, consider using the **Python filesystem watcher** instead:
- See: `client/FILESYSTEM_WATCHER.md`
- Catches all filesystem changes, not just Obsidian edits

---

## Advanced Configuration

### Aggressive Sync (Every 1 Minute)

```
Settings → Knosi Sync:
- Sync interval: 1 minute
- Auto-sync: enabled
- Sync on startup: enabled
```

**Trade-offs:**
- ✅ Near real-time sync
- ❌ More API calls
- ❌ Slightly higher battery usage

### Conservative Sync (Every 30 Minutes)

```
Settings → Knosi Sync:
- Sync interval: 30 minutes
- Auto-sync: enabled
- Sync on startup: enabled
```

**Trade-offs:**
- ✅ Fewer API calls
- ✅ Lower battery usage
- ❌ Changes take up to 30 min to sync

**Recommendation:** Use conservative sync with manual "Sync current file" for urgent notes.

### Sync Specific File Types Only

```
Settings → Knosi Sync:
- Supported extensions: .md, .pdf
```

This will only sync Markdown and PDF files, ignoring everything else.

---

## Uninstalling

1. Settings → Community Plugins
2. Find **Knosi Sync**
3. Click **Disable** then **Uninstall**
4. Or manually delete: `.obsidian/plugins/knosi-sync/`

This will:
- Stop syncing new changes
- Remove the plugin from Obsidian
- **NOT** delete documents from server (they remain indexed)

To also remove documents from server, use the web UI at `http://your-server:48080`.

---

## Development

For plugin developers:

```bash
# Install dependencies
npm install

# Build for development (with watch)
npm run dev

# Build for production
npm run build

# The output main.js will be in the plugin folder
```

---

## Future: Obsidian Community Plugin Store

Once tested and stable, this plugin will be submitted to the Obsidian Community Plugin Store for one-click installation.

For now, manual installation is required.

---

## Comparison: Plugin vs Filesystem Watcher

| Feature | Obsidian Plugin | Filesystem Watcher |
|---------|----------------|-------------------|
| **Catches edits from** | Obsidian only | Any app (Finder, VSCode, etc.) |
| **Auto-start** | Built into Obsidian | macOS/Windows scripts needed |
| **Setup complexity** | Easy (Settings UI) | Medium (command-line) |
| **CPU usage** | Lower (event-based) | Higher (monitors all files) |
| **Best for** | Obsidian-only workflows | Multi-editor workflows |
| **Sync strategy** | Batched (queued) | Immediate (debounced) |
| **Status visibility** | Status bar in Obsidian | Terminal/log file |

**Recommendation:**
- Use **Obsidian Plugin** if you only edit in Obsidian (simpler, better UX)
- Use **Filesystem Watcher** if you use VSCode, Typora, or add files via Finder

---

## Next Steps

1. ✅ Install and enable plugin
2. ✅ Configure server URL and API key
3. ✅ Test connection
4. ✅ Create a test note and verify it syncs
5. ✅ Adjust sync interval to your preference
6. ✅ Use the web UI to chat with your notes

---

Built with ❤️ by [Knosi](https://knosi.ai)
