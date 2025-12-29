# Knosi Sync - Obsidian Plugin

Automatically sync your Obsidian vault to Knosi for AI-powered document search and chat.

## Features

- **Queue-based sync**: Files are queued on change, then batch-synced at a configurable interval (saves API calls)
- **Configurable interval**: Sync every 1-60 minutes (default: 1 minute)
- **Sync on startup**: Optionally sync all files when Obsidian opens
- **Manual controls**: Sync current file immediately, process queue now, or sync entire vault
- **Status bar**: Shows sync status and queue count
- **Configurable**: Set server URL, API key, sync interval, and file types

## How It Works

```
File modified → Added to queue → Queue processed every X minutes → Upload to server
                     │                        │
                     │                        └── Deduped: each file synced once
                     └── Status bar shows: 🕐 Knosi (3) = 3 files pending
```

This prevents excessive API calls when Obsidian's autosave triggers multiple modifications in quick succession.

## Installation

### From Source

1. Clone/copy this folder to your vault's `.obsidian/plugins/knosi-sync/`
2. Install dependencies and build:
   ```bash
   cd .obsidian/plugins/knosi-sync
   npm install
   npm run build
   ```
3. Enable the plugin in Obsidian Settings → Community Plugins

### Manual Install (Pre-built)

1. Create folder: `.obsidian/plugins/knosi-sync/`
2. Copy these files into it:
   - `main.js` (after building)
   - `manifest.json`
3. Enable the plugin in Obsidian Settings → Community Plugins

## Configuration

Open Settings → Knosi Sync:

| Setting | Description | Default |
|---------|-------------|---------|
| Server URL | Your Knosi API server URL | `http://localhost:48550` |
| API Key | Authentication key (if required) | empty |
| Auto-sync | Queue files automatically on change | enabled |
| Sync interval | Minutes between queue processing (1-60) | 1 |
| Sync on startup | Sync all files when Obsidian opens | enabled |
| Supported extensions | File types to sync | `.md, .txt, .pdf, .html, .htm, .org, .rst` |

## Commands

Access via Command Palette (Cmd/Ctrl + P):

- **Sync current file (immediate)**: Upload the currently open file right now
- **Process sync queue now**: Sync all pending files without waiting for interval
- **View pending sync queue**: See which files are waiting to sync
- **Sync all files**: Upload all supported files in vault (bypasses queue)
- **Check server status**: Test connection to server

## Status Bar

The status bar shows sync status:
- 🔮 Knosi - Idle, nothing pending
- 🕐 Knosi (3) - 3 files queued for next sync
- 🔄 Knosi: 5 files - Syncing in progress
- ✅ Knosi - Sync completed
- ❌ Knosi: 2 failed - Some files failed to sync

## Notes

- The plugin only catches changes made **through Obsidian**
- Files added via Finder/Explorer won't trigger auto-sync
- Use "Sync all files" after adding files externally
- For filesystem-level watching, use the Python `knosi-sync.py` client instead
- The server deduplicates by file hash, so re-syncing unchanged files is cheap

## Development

```bash
# Install dependencies
npm install

# Build for development (with watch)
npm run dev

# Build for production
npm run build
```

## Links

- Website: [knosi.ai](https://knosi.ai)
