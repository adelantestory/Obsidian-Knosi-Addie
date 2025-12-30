// Knosi API client
// https://knosi.ai

const API_URL = import.meta.env.VITE_API_URL || '';

// Helper to generate UUID (fallback for environments without crypto.randomUUID)
function generateUUID(): string {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback UUID v4 generation
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

export interface Document {
  filename: string;
  file_size: number;
  chunk_count: number;
  indexed_at: string;
}

export interface StatusResponse {
  status: string;
  document_count: number;
  chunk_count: number;
}

export interface ChatResponse {
  response: string;
  sources: { filename: string; chunk_index: number }[];
}

export interface SearchResult {
  filename: string;
  content: string;
  chunk_index: number;
}

class ApiClient {
  private apiKey: string = '';

  setApiKey(key: string) {
    this.apiKey = key;
    localStorage.setItem('knosi-api-key', key);
  }

  getApiKey(): string {
    if (!this.apiKey) {
      this.apiKey = localStorage.getItem('knosi-api-key') || '';
    }
    return this.apiKey;
  }

  private getHeaders(): HeadersInit {
    const headers: HeadersInit = {};
    const key = this.getApiKey();
    if (key) {
      headers['X-API-Key'] = key;
    }
    return headers;
  }

  async getStatus(): Promise<StatusResponse> {
    const response = await fetch(`${API_URL}/api/status`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) throw new Error('Failed to get status');
    return response.json();
  }

  async getDocuments(): Promise<Document[]> {
    const response = await fetch(`${API_URL}/api/documents`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 401) throw new Error('Authentication failed');
      throw new Error('Failed to get documents');
    }
    return response.json();
  }

  async uploadFile(
    file: File,
    path?: string,
    onProgress?: (status: string) => void
  ): Promise<{ message: string; filename: string; chunks: number; status: string; upload_id: string }> {
    // Generate upload ID
    const uploadId = generateUUID();

    // If progress callback provided, start listening to SSE
    if (onProgress) {
      this.subscribeToUploadProgress(uploadId, onProgress);
    }

    const formData = new FormData();
    formData.append('file', file);
    formData.append('upload_id', uploadId);
    if (path) {
      formData.append('path', path);
    }

    const response = await fetch(`${API_URL}/api/upload`, {
      method: 'POST',
      headers: this.getHeaders(),
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Upload failed');
    }
    return response.json();
  }

  private subscribeToUploadProgress(uploadId: string, onProgress: (status: string) => void) {
    const apiKey = this.getApiKey();
    const url = new URL(`${API_URL}/api/upload/${uploadId}/progress`);

    // EventSource doesn't support custom headers, so pass API key as query param
    if (apiKey) {
      url.searchParams.append('api_key', apiKey);
    }

    const eventSource = new EventSource(url.toString());

    eventSource.addEventListener('progress', (event) => {
      onProgress(event.data);

      // Close connection if done
      if (event.data.startsWith('complete:') || event.data.startsWith('error:')) {
        eventSource.close();
      }
    });

    eventSource.addEventListener('error', () => {
      eventSource.close();
    });
  }

  async deleteDocument(filename: string): Promise<void> {
    const response = await fetch(`${API_URL}/api/documents/${encodeURIComponent(filename)}`, {
      method: 'DELETE',
      headers: this.getHeaders(),
    });
    if (!response.ok) {
      if (response.status === 404) throw new Error('Document not found');
      throw new Error('Failed to delete document');
    }
  }

  async chat(message: string, includeSources: boolean = true): Promise<ChatResponse> {
    const response = await fetch(`${API_URL}/api/chat`, {
      method: 'POST',
      headers: {
        ...this.getHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ message, include_sources: includeSources }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Chat failed');
    }
    return response.json();
  }

  async search(query: string, limit: number = 10): Promise<SearchResult[]> {
    const response = await fetch(`${API_URL}/api/search?q=${encodeURIComponent(query)}&limit=${limit}`, {
      headers: this.getHeaders(),
    });
    if (!response.ok) throw new Error('Search failed');
    return response.json();
  }

  getDownloadUrl(filename: string): string {
    const apiKey = this.getApiKey();
    const url = `${API_URL}/api/documents/${encodeURIComponent(filename)}/download`;
    if (apiKey) {
      return `${url}?api_key=${encodeURIComponent(apiKey)}`;
    }
    return url;
  }
}

export const api = new ApiClient();
