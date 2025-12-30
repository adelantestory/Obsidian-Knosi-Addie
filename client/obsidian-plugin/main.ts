import { App, Plugin, PluginSettingTab, Setting, Notice, TFile, TAbstractFile, requestUrl } from 'obsidian';

interface KnosiSettings {
	serverUrl: string;
	apiKey: string;
	autoSync: boolean;
	syncOnStartup: boolean;
	syncIntervalMinutes: number;
	supportedExtensions: string[];
	excludePatterns: string[];
}

const DEFAULT_SETTINGS: KnosiSettings = {
	serverUrl: 'http://localhost:48550',
	apiKey: '',
	autoSync: true,
	syncOnStartup: true,
	syncIntervalMinutes: 1,
	supportedExtensions: ['.md', '.txt', '.pdf', '.html', '.htm', '.org', '.rst', '.png', '.jpg', '.jpeg', '.gif', '.webp'],
	excludePatterns: ['.obsidian/', '.trash/', 'Templates/']
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

	async saveSettingsAndRescanExclusions(oldPatterns: string[]) {
		await this.saveData(this.settings);

		// Check if exclusion patterns changed
		const newPatterns = this.settings.excludePatterns;
		if (JSON.stringify(oldPatterns) !== JSON.stringify(newPatterns)) {
			// Patterns changed - rescan vault for newly excluded files
			this.rescanVaultForNewExclusions(oldPatterns, newPatterns);
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
			if (addedExtensions.includes(ext) && !this.isExcluded(file.path)) {
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

	rescanVaultForNewExclusions(oldPatterns: string[], newPatterns: string[]) {
		// Find newly added exclusion patterns
		const addedPatterns = newPatterns.filter(p => !oldPatterns.includes(p));

		if (addedPatterns.length === 0) {
			return;
		}

		console.log(`Rescanning vault for newly excluded patterns: ${addedPatterns.join(', ')}`);
		new Notice(`Finding files to delete for: ${addedPatterns.join(', ')}`);

		// Find all files that match the new exclusion patterns
		const files = this.app.vault.getFiles();
		let queuedCount = 0;

		for (const file of files) {
			// Check if file matches any of the NEW exclusion patterns
			for (const pattern of addedPatterns) {
				if (!pattern.trim()) continue;

				let matches = false;

				// Directory pattern (ends with /)
				if (pattern.endsWith('/')) {
					if (file.path.startsWith(pattern) || file.path.includes('/' + pattern)) {
						matches = true;
					}
				}
				// Simple glob patterns (* and **)
				else if (pattern.includes('*')) {
					const regexPattern = pattern
						.replace(/\./g, '\\.')
						.replace(/\*\*/g, '.*')
						.replace(/\*/g, '[^/]*');
					const regex = new RegExp('^' + regexPattern + '$');
					if (regex.test(file.path)) {
						matches = true;
					}
				}
				// Exact filename match
				else {
					const fileName = file.path.split('/').pop() || '';
					if (fileName === pattern || file.path === pattern || file.path.endsWith('/' + pattern)) {
						matches = true;
					}
				}

				if (matches) {
					// Remove from upload queue if present
					this.pendingUploads.delete(file.path);
					// Add to delete queue
					this.pendingDeletes.add(file.path);
					queuedCount++;
					break; // Found a match, no need to check other patterns
				}
			}
		}

		if (queuedCount > 0) {
			console.log(`Queued ${queuedCount} files for deletion`);
			new Notice(`Queued ${queuedCount} files for deletion from server`);
			this.updateStatusBar('pending');
		} else {
			new Notice('No matching files found to delete');
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

	isExcluded(filePath: string): boolean {
		// Check if file matches any exclusion pattern
		for (const pattern of this.settings.excludePatterns) {
			if (!pattern.trim()) continue;

			// Directory pattern (ends with /)
			if (pattern.endsWith('/')) {
				if (filePath.startsWith(pattern) || filePath.includes('/' + pattern)) {
					return true;
				}
			}
			// Simple glob patterns (* and **)
			else if (pattern.includes('*')) {
				const regexPattern = pattern
					.replace(/\./g, '\\.')
					.replace(/\*\*/g, '.*')
					.replace(/\*/g, '[^/]*');
				const regex = new RegExp('^' + regexPattern + '$');
				if (regex.test(filePath)) {
					return true;
				}
			}
			// Exact filename match
			else {
				const fileName = filePath.split('/').pop() || '';
				if (fileName === pattern || filePath === pattern || filePath.endsWith('/' + pattern)) {
					return true;
				}
			}
		}
		return false;
	}

	queueFileUpload(file: TAbstractFile) {
		if (!this.isSupportedFile(file)) return;

		// Check if file is excluded
		if (this.isExcluded(file.path)) {
			console.log(`Skipping excluded file: ${file.path}`);
			return;
		}

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
	private tempSettings: KnosiSettings;
	private originalSettings: KnosiSettings;

	constructor(app: App, plugin: KnosiSyncPlugin) {
		super(app, plugin);
		this.plugin = plugin;
	}

	display(): void {
		const { containerEl } = this;
		containerEl.empty();

		// Store original settings and create a copy for editing
		this.originalSettings = JSON.parse(JSON.stringify(this.plugin.settings));
		this.tempSettings = JSON.parse(JSON.stringify(this.plugin.settings));

		containerEl.createEl('h1', { text: 'Knosi' });

		new Setting(containerEl)
			.setName('Server URL')
			.setDesc('URL of your Knosi API server')
			.addText(text => text
				.setPlaceholder('http://localhost:48550')
				.setValue(this.tempSettings.serverUrl)
				.onChange((value) => {
					this.tempSettings.serverUrl = value;
				}));

		new Setting(containerEl)
			.setName('API Key')
			.setDesc('API key for authentication (if required)')
			.addText(text => {
				text
					.setPlaceholder('Enter API key')
					.setValue(this.tempSettings.apiKey)
					.onChange((value) => {
						this.tempSettings.apiKey = value;
					});
				text.inputEl.type = 'password';
			});

		new Setting(containerEl)
			.setName('Auto-sync')
			.setDesc('Automatically queue files for sync when created or modified (requires Obsidian restart)')
			.addToggle(toggle => toggle
				.setValue(this.tempSettings.autoSync)
				.onChange((value) => {
					this.tempSettings.autoSync = value;
				}));

		new Setting(containerEl)
			.setName('Sync interval (minutes)')
			.setDesc('How often to process the sync queue. Lower = more frequent syncs, higher = fewer API calls.')
			.addSlider(slider => slider
				.setLimits(1, 60, 1)
				.setValue(this.tempSettings.syncIntervalMinutes)
				.setDynamicTooltip()
				.onChange((value) => {
					this.tempSettings.syncIntervalMinutes = value;
				}))
			.addExtraButton(button => button
				.setIcon('reset')
				.setTooltip('Reset to default (1 minute)')
				.onClick(() => {
					this.tempSettings.syncIntervalMinutes = 1;
					this.display();
				}));

		new Setting(containerEl)
			.setName('Sync on startup')
			.setDesc('Sync all files when Obsidian opens')
			.addToggle(toggle => toggle
				.setValue(this.tempSettings.syncOnStartup)
				.onChange((value) => {
					this.tempSettings.syncOnStartup = value;
				}));

		new Setting(containerEl)
			.setName('Supported extensions')
			.setDesc('File extensions to sync (comma-separated). Changes will trigger a rescan when saved.')
			.addText(text => text
				.setPlaceholder('.md, .txt, .pdf')
				.setValue(this.tempSettings.supportedExtensions.join(', '))
				.onChange((value) => {
					this.tempSettings.supportedExtensions = value
						.split(',')
						.map(s => s.trim().toLowerCase())
						.filter(s => s.startsWith('.'));
				}));

		new Setting(containerEl)
			.setName('Exclude patterns')
			.setDesc('Paths/files to exclude (comma-separated). Supports directories (end with /), filenames, or glob patterns (*). Adding new patterns will delete matching files from server when saved.')
			.addTextArea(text => {
				text
					.setPlaceholder('.obsidian/, Templates/, *.tmp, **/*.backup')
					.setValue(this.tempSettings.excludePatterns.join(', '))
					.onChange((value) => {
						this.tempSettings.excludePatterns = value
							.split(',')
							.map(s => s.trim())
							.filter(s => s.length > 0);
					});
				text.inputEl.rows = 3;
				text.inputEl.style.width = '100%';
			});

		// Save button
		new Setting(containerEl)
			.addButton(button => button
				.setButtonText('Save')
				.setCta()
				.onClick(async () => {
					await this.saveSettings();
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

	async saveSettings() {
		// Check what changed
		const extensionsChanged = JSON.stringify(this.originalSettings.supportedExtensions) !== JSON.stringify(this.tempSettings.supportedExtensions);
		const patternsChanged = JSON.stringify(this.originalSettings.excludePatterns) !== JSON.stringify(this.tempSettings.excludePatterns);
		const intervalChanged = this.originalSettings.syncIntervalMinutes !== this.tempSettings.syncIntervalMinutes;
		const autoSyncChanged = this.originalSettings.autoSync !== this.tempSettings.autoSync;

		// Apply temp settings to plugin
		this.plugin.settings = JSON.parse(JSON.stringify(this.tempSettings));
		await this.plugin.saveData(this.plugin.settings);

		// Handle side effects
		if (intervalChanged) {
			this.plugin.restartSyncInterval();
		}

		if (autoSyncChanged) {
			new Notice('Restart Obsidian for auto-sync changes to take effect');
		}

		if (extensionsChanged) {
			const oldExtensions = this.originalSettings.supportedExtensions;
			const newExtensions = this.tempSettings.supportedExtensions;
			this.plugin.rescanVaultForNewExtensions(oldExtensions, newExtensions);
		}

		if (patternsChanged) {
			const oldPatterns = this.originalSettings.excludePatterns;
			const newPatterns = this.tempSettings.excludePatterns;
			this.plugin.rescanVaultForNewExclusions(oldPatterns, newPatterns);
		}

		new Notice('Settings saved');

		// Update original to match current
		this.originalSettings = JSON.parse(JSON.stringify(this.tempSettings));
	}
}
