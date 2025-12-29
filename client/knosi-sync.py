#!/usr/bin/env python3
"""
Knosi Local Sync Client
Watches a local folder and syncs files to a remote Knosi server.

Usage:
    python knosi-sync.py --server https://your-server:48550 --vault ~/Documents/vault
"""
import os
import sys
import time
import argparse
import hashlib
from pathlib import Path
from datetime import datetime

import requests
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Supported file extensions
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".org", ".rst", ".html", ".htm", ".docx"}


class KnosiSyncHandler(FileSystemEventHandler):
    """Handle file system events and sync to remote server."""
    
    def __init__(self, server_url: str, api_key: str, vault_path: Path, debounce_seconds: float = 2.0):
        self.server_url = server_url.rstrip('/')
        self.api_key = api_key
        self.vault_path = vault_path
        self.debounce_seconds = debounce_seconds
        self.pending_events = {}  # path -> timestamp
        self.file_hashes = {}  # path -> hash (to detect actual changes)
        
    def _get_relative_path(self, path: str) -> str:
        """Get path relative to vault root."""
        return str(Path(path).relative_to(self.vault_path))
    
    def _is_supported(self, path: str) -> bool:
        """Check if file type is supported."""
        return Path(path).suffix.lower() in SUPPORTED_EXTENSIONS
    
    def _compute_hash(self, path: str) -> str:
        """Compute file hash."""
        try:
            with open(path, 'rb') as f:
                return hashlib.sha256(f.read()).hexdigest()
        except:
            return ""
    
    def _upload_file(self, path: str):
        """Upload file to remote server."""
        rel_path = self._get_relative_path(path)
        
        # Check if file actually changed
        new_hash = self._compute_hash(path)
        if new_hash == self.file_hashes.get(path):
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Skipped (unchanged): {rel_path}")
            return
        
        try:
            with open(path, 'rb') as f:
                files = {'file': (Path(path).name, f)}
                data = {'path': rel_path}
                headers = {}
                if self.api_key:
                    headers['X-API-Key'] = self.api_key
                
                response = requests.post(
                    f"{self.server_url}/api/upload",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=120  # Large files may take time
                )
                
                if response.status_code == 200:
                    result = response.json()
                    self.file_hashes[path] = new_hash
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] {result['status'].capitalize()}: {rel_path} ({result.get('chunks', 0)} chunks)")
                elif response.status_code == 401:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Auth failed: Check API key")
                else:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Error uploading {rel_path}: {response.text}")
                    
        except requests.exceptions.ConnectionError:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Connection failed - is server running?")
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
    
    def _delete_file(self, path: str):
        """Delete file from remote server."""
        rel_path = self._get_relative_path(path)
        
        try:
            headers = {}
            if self.api_key:
                headers['X-API-Key'] = self.api_key
            
            response = requests.delete(
                f"{self.server_url}/api/documents/{rel_path}",
                headers=headers,
                timeout=30
            )
            
            if response.status_code == 200:
                self.file_hashes.pop(path, None)
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Deleted: {rel_path}")
            elif response.status_code == 404:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Already gone: {rel_path}")
            else:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Error deleting {rel_path}: {response.text}")
                
        except Exception as e:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: {e}")
    
    def _process_pending(self):
        """Process pending events after debounce period."""
        now = time.time()
        to_process = []
        
        for path, (timestamp, event_type) in list(self.pending_events.items()):
            if now - timestamp >= self.debounce_seconds:
                to_process.append((path, event_type))
                del self.pending_events[path]
        
        for path, event_type in to_process:
            if event_type == 'delete':
                self._delete_file(path)
            elif os.path.exists(path):
                self._upload_file(path)
    
    def on_created(self, event):
        if event.is_directory:
            return
        if self._is_supported(event.src_path):
            self.pending_events[event.src_path] = (time.time(), 'create')
    
    def on_modified(self, event):
        if event.is_directory:
            return
        if self._is_supported(event.src_path):
            self.pending_events[event.src_path] = (time.time(), 'modify')
    
    def on_deleted(self, event):
        if event.is_directory:
            return
        if self._is_supported(event.src_path):
            self.pending_events[event.src_path] = (time.time(), 'delete')
    
    def on_moved(self, event):
        if event.is_directory:
            return
        # Treat as delete + create
        if self._is_supported(event.src_path):
            self.pending_events[event.src_path] = (time.time(), 'delete')
        if self._is_supported(event.dest_path):
            self.pending_events[event.dest_path] = (time.time(), 'create')


def initial_sync(handler: KnosiSyncHandler, vault_path: Path):
    """Sync all existing files on startup."""
    print(f"Starting initial sync of {vault_path}...")
    
    files_found = 0
    for ext in SUPPORTED_EXTENSIONS:
        for path in vault_path.rglob(f"*{ext}"):
            if path.is_file():
                files_found += 1
                handler._upload_file(str(path))
    
    print(f"Initial sync complete: {files_found} files processed")


def check_server(server_url: str, api_key: str) -> bool:
    """Check if server is reachable."""
    try:
        headers = {'X-API-Key': api_key} if api_key else {}
        response = requests.get(f"{server_url}/api/status", headers=headers, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"Server connected: {data['document_count']} documents, {data['chunk_count']} chunks")
            return True
        elif response.status_code == 401:
            print("Server requires API key - check your --api-key")
            return False
        else:
            print(f"Server error: {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print(f"Cannot connect to server at {server_url}")
        return False
    except Exception as e:
        print(f"Error checking server: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Sync local files to Knosi server")
    parser.add_argument("--server", "-s", required=True, help="Server URL (e.g., https://knosi.example.com:48550)")
    parser.add_argument("--vault", "-v", required=True, help="Path to local vault folder")
    parser.add_argument("--api-key", "-k", default=os.getenv("KNOSI_API_KEY", ""), help="API key for authentication")
    parser.add_argument("--no-initial-sync", action="store_true", help="Skip initial sync on startup")
    parser.add_argument("--debounce", type=float, default=2.0, help="Debounce delay in seconds (default: 2)")
    
    args = parser.parse_args()
    
    vault_path = Path(args.vault).expanduser().resolve()
    
    if not vault_path.exists():
        print(f"Error: Vault path does not exist: {vault_path}")
        sys.exit(1)
    
    if not vault_path.is_dir():
        print(f"Error: Vault path is not a directory: {vault_path}")
        sys.exit(1)
    
    print(f"Knosi Sync Client")
    print(f"Server: {args.server}")
    print(f"Vault:  {vault_path}")
    print()
    
    # Check server connection
    if not check_server(args.server, args.api_key):
        sys.exit(1)
    
    print()
    
    # Create handler
    handler = KnosiSyncHandler(
        server_url=args.server,
        api_key=args.api_key,
        vault_path=vault_path,
        debounce_seconds=args.debounce
    )
    
    # Initial sync
    if not args.no_initial_sync:
        initial_sync(handler, vault_path)
        print()
    
    # Start watching
    observer = Observer()
    observer.schedule(handler, str(vault_path), recursive=True)
    observer.start()
    
    print(f"Watching for changes... (Ctrl+C to stop)")
    print()
    
    try:
        while True:
            time.sleep(0.5)
            handler._process_pending()
    except KeyboardInterrupt:
        print("\nStopping...")
        observer.stop()
    
    observer.join()
    print("Done.")


if __name__ == "__main__":
    main()
