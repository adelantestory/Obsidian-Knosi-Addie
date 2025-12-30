import { App, Plugin, PluginSettingTab, Setting, Notice, TFile, TAbstractFile, requestUrl } from 'obsidian';

interface KnosiSettings {
	serverUrl: string;
	apiKey: string;
	autoSync: boolean;
	syncOnStartup: boolean;
	syncIntervalMinutes: number;
	supportedExtensions: string[];
}

const DEFAULT_SETTINGS: KnosiSettings = {
	serverUrl: 'http://localhost:48550',
	apiKey: '',
	autoSync: true,
	syncOnStartup: true,
	syncIntervalMinutes: 1,
	supportedExtensions: ['.md', '.txt', '.pdf', '.html', '.htm', '.org', '.rst', '.png', '.jpg', '.jpeg', '.gif', '.webp']
};

export default class KnosiSyncPlugin extends Plugin {
	settings: KnosiSettings;
	statusBarItem: HTMLElement;
	syncInProgress: boolean = false;
	
	// Queue-based sync
	pendingUploads: Set<string> = new Set();      // Files to upload
	pendingDeletes: Set<string> = new Set();      // Files to delete
	syncIntervalId: number | null = null;

	async onload() {
		await this.loadSettings();

		// Status bar
		this.statusBarItem = this.addStatusBarItem();
		this.updateStatusBar('idle');

		// Register vault events
		if (this.settings.autoSync) {
			this.registerEvent(
				this.app.vault.on('create', (file) => this.queueFileUpload(file))
			);
			this.registerEvent(
				this.app.vault.on('modify', (file) => this.queueFileUpload(file))
			);
			this.registerEvent(
				this.app.vault.on('delete', (file) => this.queueFileDelete(file))
			);
			this.registerEvent(
				this.app.vault.on('rename', (file, oldPath) => this.handleFileRename(file, oldPath))
			);
			
			// Start the sync interval
			this.startSyncInterval();
		}

		// Commands
		this.addCommand({
			id: 'sync-current-file',
			name: 'Sync current file (immediate)',
			callback: () => this.syncCurrentFile()
		});

		this.addCommand({
			id: 'sync-queue-now',
			name: 'Process sync queue now',
			callback: () => this.processQueue()
		});

		this.addCommand({
			id: 'sync-all-files',
			name: 'Sync all files',
			callback: () => this.syncAllFiles()
		});

		this.addCommand({
			id: 'check-server-status',
			name: 'Check server status',
			callback: () => this.checkServerStatus()
		});

		this.addCommand({
			id: 'view-queue',
			name: 'View pending sync queue',
			callback: () => this.viewQueue()
		});

		// Settings tab
		this.addSettingTab(new KnosiSettingTab(this.app, this));

		// Initial sync on startup
		if (this.settings.syncOnStartup) {
			// Delay to let Obsidian fully load
			setTimeout(() => this.syncAllFiles(), 3000);
		}

		console.log('Knosi Sync plugin loaded');
	}

	onunload() {
		this.stopSyncInterval();
		this.pendingUploads.clear();
		this.pendingDeletes.clear();
		console.log('Knosi Sync plugin unloaded');
	}

	async loadSettings() {
		this.settings = Object.assign({}, DEFAULT_SETTINGS, await this.loadData());
	}

	async saveSettings() {
		await this.saveData(this.settings);
	}

	async saveSettingsAndRescan(oldExtensions: string[]) {
		await this.saveData(this.settings);

		// Check if supported extensions changed
		const newExtensions = this.settings.supportedExtensions;
		if (JSON.stringify(oldExtensions) !== JSON.stringify(newExtensions)) {
			// Extensions changed - rescan vault for new file types
			this.rescanVaultForNewExtensions(oldExtensions, newExtensions);
		}
	}

	rescanVaultForNewExtensions(oldExtensions: string[], newExtensions: string[]) {
		// Find newly added extensions
		const addedExtensions = newExtensions.filter(ext => !oldExtensions.includes(ext));

		if (addedExtensions.length === 0) {
			return;
		}

		console.log(`Rescanning vault for new extensions: ${addedExtensions.join(', ')}`);
		new Notice(`Rescanning vault for: ${addedExtensions.join(', ')}`);

		// Find all files with the new extensions
		const files = this.app.vault.getFiles();
		let queuedCount = 0;

		for (const file of files) {
			const ext = '.' + file.extension.toLowerCase();
			if (addedExtensions.includes(ext)) {
				this.pendingUploads.add(file.path);
				queuedCount++;
			}
		}

		if (queuedCount > 0) {
			console.log(`Queued ${queuedCount} files for sync`);
			new Notice(`Queued ${queuedCount} files for sync`);
			this.updateStatusBar('pending');
		} else {
			new Notice('No new files found to sync');
		}
	}

	startSyncInterval() {
		this.stopSyncInterval();
		const intervalMs = this.settings.syncIntervalMinutes * 60 * 1000;
		this.syncIntervalId = window.setInterval(() => this.processQueue(), intervalMs);
		console.log(`Sync interval started: every ${this.settings.syncIntervalMinutes} minute(s)`);
	}

	stopSyncInterval() {
		if (this.syncIntervalId !== null) {
			window.clearInterval(this.syncIntervalId);
			this.syncIntervalId = null;
		}
	}

	restartSyncInterval() {
		this.startSyncInterval();
	}

	updateStatusBar(status: 'idle' | 'syncing' | 'success' | 'error' | 'pending', message?: string) {
		const icons: Record<string, string> = {
			idle: '🔮',
			pending: '🕐',
			syncing: '🔄',
			success: '✅',
			error: '❌'
		};
		
		let text = `${icons[status]} Knosi`;
		if (status === 'pending' && this.pendingUploads.size > 0) {
			text += ` (${this.pendingUploads.size})`;
		} else if (message) {
			text += `: ${message}`;
		}
		
		this.statusBarItem.setText(text);
	}

	isSupportedFile(file: TAbstractFile): file is TFile {
		if (!(file instanceof TFile)) return false;
		const ext = '.' + file.extension.toLowerCase();
		return this.settings.supportedExtensions.includes(ext);
	}

	queueFileUpload(file: TAbstractFile) {
		if (!this.isSupportedFile(file)) return;
		
		// Remove from delete queue if present
		this.pendingDeletes.delete(file.path);
		
		// Add to upload queue
		this.pendingUploads.add(file.path);
		this.updateStatusBar('pending');
		
		console.log(`Queued for sync: ${file.path} (${this.pendingUploads.size} in queue)`);
	}

	queueFileDelete(file: TAbstractFile) {
		if (!(file instanceof TFile)) return;
		const ext = '.' + file.extension.toLowerCase();
		if (!this.settings.supportedExtensions.includes(ext)) return;
		
		// Remove from upload queue if present
		this.pendingUploads.delete(file.path);
		
		// Add to delete queue
		this.pendingDeletes.add(file.path);
		this.updateStatusBar('pending');
		
		console.log(`Queued for delete: ${file.path}`);
	}

	handleFileRename(file: TAbstractFile, oldPath: string) {
		if (!this.isSupportedFile(file)) return;
		
		// Queue delete for old path, upload for new path
		this.pendingDeletes.add(oldPath);
		this.pendingUploads.delete(oldPath);
		
		this.pendingUploads.add(file.path);
		this.pendingDeletes.delete(file.path);
		
		this.updateStatusBar('pending');
	}

	async processQueue() {
		if (this.syncInProgress) {
			console.log('Sync already in progress, skipping');
			return;
		}

		const uploadsToProcess = new Set(this.pendingUploads);
		const deletesToProcess = new Set(this.pendingDeletes);
		
		if (uploadsToProcess.size === 0 && deletesToProcess.size === 0) {
			return; // Nothing to do
		}

		this.syncInProgress = true;
		this.updateStatusBar('syncing', `${uploadsToProcess.size} files`);
		
		console.log(`Processing queue: ${uploadsToProcess.size} uploads, ${deletesToProcess.size} deletes`);

		let uploaded = 0;
		let deleted = 0;
		let errors = 0;

		// Process deletes first
		for (const path of deletesToProcess) {
			try {
				await this.deleteFileByPath(path);
				this.pendingDeletes.delete(path);
				deleted++;
			} catch {
				errors++;
			}
		}

		// Process uploads
		for (const path of uploadsToProcess) {
			const file = this.app.vault.getAbstractFileByPath(path);
			if (file instanceof TFile) {
				try {
					await this.uploadFile(file);
					this.pendingUploads.delete(path);
					uploaded++;
				} catch {
					errors++;
					// Keep in queue for retry
				}
			} else {
				// File no longer exists, remove from queue
				this.pendingUploads.delete(path);
			}
		}

		this.syncInProgress = false;
		
		if (errors > 0) {
			this.updateStatusBar('error', `${errors} failed`);
			setTimeout(() => this.updateStatusBar('idle'), 5000);
		} else if (uploaded > 0 || deleted > 0) {
			this.updateStatusBar('success');
			setTimeout(() => {
				if (this.pendingUploads.size > 0) {
					this.updateStatusBar('pending');
				} else {
					this.updateStatusBar('idle');
				}
			}, 2000);
		} else {
			this.updateStatusBar('idle');
		}

		console.log(`Queue processed: ${uploaded} uploaded, ${deleted} deleted, ${errors} errors`);
	}

	viewQueue() {
		const uploads = Array.from(this.pendingUploads);
		const deletes = Array.from(this.pendingDeletes);
		
		if (uploads.length === 0 && deletes.length === 0) {
			new Notice('Sync queue is empty');
			return;
		}

		let message = '';
		if (uploads.length > 0) {
			message += `📤 Pending uploads (${uploads.length}):\n${uploads.slice(0, 10).join('\n')}`;
			if (uploads.length > 10) message += `\n...and ${uploads.length - 10} more`;
		}
		if (deletes.length > 0) {
			if (message) message += '\n\n';
			message += `🗑️ Pending deletes (${deletes.length}):\n${deletes.slice(0, 10).join('\n')}`;
			if (deletes.length > 10) message += `\n...and ${deletes.length - 10} more`;
		}

		new Notice(message, 10000);
	}

	async uploadFile(file: TFile) {
		try {
			const content = await this.app.vault.readBinary(file);

			// Skip empty files
			if (content.byteLength === 0) {
				console.log(`Skipping empty file: ${file.path}`);
				return;
			}

			const blob = new Blob([content]);

			// Create form data
			const formData = new FormData();
			formData.append('file', blob, file.name);
			formData.append('path', file.path);

			const response = await fetch(`${this.settings.serverUrl}/api/upload`, {
				method: 'POST',
				headers: {
					'X-API-Key': this.settings.apiKey
				},
				body: formData
			});

			if (!response.ok) {
				const error = await response.json();
				throw new Error(error.detail || `HTTP ${response.status}`);
			}

			const result = await response.json();
			console.log(`Synced: ${file.path} (${result.status})`);

		} catch (error) {
			console.error(`Failed to sync ${file.path}:`, error);
			throw error;
		}
	}

	async deleteFileByPath(path: string) {
		try {
			const response = await fetch(
				`${this.settings.serverUrl}/api/documents/${encodeURIComponent(path)}`,
				{
					method: 'DELETE',
					headers: {
						'X-API-Key': this.settings.apiKey
					}
				}
			);

			if (response.ok) {
				console.log(`Deleted from index: ${path}`);
			}
		} catch (error) {
			console.error(`Failed to delete ${path}:`, error);
			throw error;
		}
	}

	async syncCurrentFile() {
		const file = this.app.workspace.getActiveFile();
		if (!file) {
			new Notice('No file is currently open');
			return;
		}

		if (!this.isSupportedFile(file)) {
			new Notice(`File type .${file.extension} is not supported`);
			return;
		}

		this.updateStatusBar('syncing', file.name);
		try {
			await this.uploadFile(file);
			this.updateStatusBar('success');
			new Notice(`Synced: ${file.name}`);
		} catch (error) {
			this.updateStatusBar('error', file.name);
			new Notice(`Failed to sync: ${error.message}`);
		}
		setTimeout(() => this.updateStatusBar('idle'), 2000);
	}

	async syncAllFiles() {
		if (this.syncInProgress) {
			new Notice('Sync already in progress');
			return;
		}

		this.syncInProgress = true;
		this.updateStatusBar('syncing', 'all files');

		const files = this.app.vault.getFiles().filter(f => this.isSupportedFile(f));
		let synced = 0;
		let errors = 0;

		new Notice(`Syncing ${files.length} files...`);

		for (const file of files) {
			try {
				await this.uploadFile(file);
				synced++;
			} catch {
				errors++;
			}
		}

		this.syncInProgress = false;
		this.updateStatusBar('idle');

		new Notice(`Sync complete: ${synced} files synced${errors > 0 ? `, ${errors} errors` : ''}`);
	}

	async checkServerStatus() {
		try {
			const response = await fetch(`${this.settings.serverUrl}/api/status`, {
				headers: {
					'X-API-Key': this.settings.apiKey
				}
			});

			if (!response.ok) {
				if (response.status === 401) {
					new Notice('❌ Authentication failed - check API key');
				} else {
					new Notice(`❌ Server error: ${response.status}`);
				}
				return;
			}

			const data = await response.json();
			new Notice(`✅ Connected: ${data.document_count} documents, ${data.chunk_count} chunks`);

		} catch (error) {
			new Notice(`❌ Cannot connect to server: ${error.message}`);
		}
	}
}

class KnosiSettingTab extends PluginSettingTab {
	plugin: KnosiSyncPlugin;

	constructor(app: App, plugin: KnosiSyncPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		containerEl.createEl('h2', { text: 'Knosi Settings' });

		new Setting(containerEl)
			.setName('Server URL')
			.setDesc('URL of your Knosi API server')
			.addText(text => text
				.setPlaceholder('http://localhost:48550')
				.setValue(this.plugin.settings.serverUrl)
				.onChange(async (value) => {
					this.plugin.settings.serverUrl = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('API Key')
			.setDesc('API key for authentication (if required)')
			.addText(text => {
				text
					.setPlaceholder('Enter API key')
					.setValue(this.plugin.settings.apiKey)
					.onChange(async (value) => {
						this.plugin.settings.apiKey = value;
						await this.plugin.saveSettings();
					});
				text.inputEl.type = 'password';
			});

		new Setting(containerEl)
			.setName('Auto-sync')
			.setDesc('Automatically queue files for sync when created or modified')
			.addToggle(toggle => toggle
				.setValue(this.plugin.settings.autoSync)
				.onChange(async (value) => {
					this.plugin.settings.autoSync = value;
					await this.plugin.saveSettings();
					new Notice('Restart Obsidian for auto-sync changes to take effect');
				}));

		new Setting(containerEl)
			.setName('Sync interval (minutes)')
			.setDesc('How often to process the sync queue. Lower = more frequent syncs, higher = fewer API calls.')
			.addSlider(slider => slider
				.setLimits(1, 60, 1)
				.setValue(this.plugin.settings.syncIntervalMinutes)
				.setDynamicTooltip()
				.onChange(async (value) => {
					this.plugin.settings.syncIntervalMinutes = value;
					await this.plugin.saveSettings();
					this.plugin.restartSyncInterval();
				}))
			.addExtraButton(button => button
				.setIcon('reset')
				.setTooltip('Reset to default (1 minute)')
				.onClick(async () => {
					this.plugin.settings.syncIntervalMinutes = 1;
					await this.plugin.saveSettings();
					this.plugin.restartSyncInterval();
					this.display();
				}));

		new Setting(containerEl)
			.setName('Sync on startup')
			.setDesc('Sync all files when Obsidian opens')
			.addToggle(toggle => toggle
				.setValue(this.plugin.settings.syncOnStartup)
				.onChange(async (value) => {
					this.plugin.settings.syncOnStartup = value;
					await this.plugin.saveSettings();
				}));

		new Setting(containerEl)
			.setName('Supported extensions')
			.setDesc('File extensions to sync (comma-separated). Changes will trigger a rescan.')
			.addText(text => text
				.setPlaceholder('.md, .txt, .pdf')
				.setValue(this.plugin.settings.supportedExtensions.join(', '))
				.onChange(async (value) => {
					const oldExtensions = [...this.plugin.settings.supportedExtensions];
					this.plugin.settings.supportedExtensions = value
						.split(',')
						.map(s => s.trim().toLowerCase())
						.filter(s => s.startsWith('.'));
					await this.plugin.saveSettingsAndRescan(oldExtensions);
				}));

		containerEl.createEl('h3', { text: 'Actions' });

		new Setting(containerEl)
			.setName('Test connection')
			.setDesc('Check if the server is reachable')
			.addButton(button => button
				.setButtonText('Test')
				.onClick(() => this.plugin.checkServerStatus()));

		new Setting(containerEl)
			.setName('View sync queue')
			.setDesc('Show files pending sync')
			.addButton(button => button
				.setButtonText('View Queue')
				.onClick(() => this.plugin.viewQueue()));

		new Setting(containerEl)
			.setName('Process queue now')
			.setDesc('Sync all pending files immediately')
			.addButton(button => button
				.setButtonText('Sync Now')
				.onClick(() => this.plugin.processQueue()));

		new Setting(containerEl)
			.setName('Sync all files')
			.setDesc('Upload all supported files to the server (bypasses queue)')
			.addButton(button => button
				.setButtonText('Sync All')
				.setCta()
				.onClick(() => this.plugin.syncAllFiles()));
	}
}
