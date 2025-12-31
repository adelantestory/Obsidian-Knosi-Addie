import { useState, useEffect, useCallback } from 'react';
import { Upload, Trash2, FileText, Loader2, CheckCircle, AlertCircle, Download } from 'lucide-react';
import { api, Document } from '../api';

interface Props {
  onDocumentsChanged: () => void;
}

export default function DocumentsPanel({ onDocumentsChanged }: Props) {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [isDragOver, setIsDragOver] = useState(false);

  const loadDocuments = useCallback(async () => {
    try {
      setIsLoading(true);
      const docs = await api.getDocuments();
      setDocuments(docs);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadDocuments();
  }, [loadDocuments]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;

    for (const file of Array.from(files)) {
      setUploadProgress(`Uploading ${file.name}...`);
      setUploadStatus(null);
      try {
        await api.uploadFile(file, undefined, (status: string) => {
          // Handle progress updates from SSE
          if (status.startsWith('complete:')) {
            const message = status.substring(9); // Remove "complete:" prefix
            setUploadProgress(null);
            setUploadStatus({
              type: 'success',
              message,
            });
          } else if (status.startsWith('error:')) {
            const message = status.substring(6); // Remove "error:" prefix
            setUploadProgress(null);
            setUploadStatus({
              type: 'error',
              message,
            });
          } else {
            // Regular progress update
            setUploadProgress(status);
          }
        });

        // Upload completed
        if (!uploadStatus) { // Only update if not already set by SSE
          setUploadStatus({
            type: 'success',
            message: `${file.name} uploaded successfully.`,
          });
        }
        loadDocuments();
        onDocumentsChanged();
      } catch (err) {
        setUploadProgress(null);

        // Make error messages more user-friendly
        let errorMessage = 'Upload failed';
        if (err instanceof Error) {
          const msg = err.message.toLowerCase();
          if (msg.includes('failed to fetch') || msg.includes('network')) {
            errorMessage = 'Cannot connect to server. Please check your connection.';
          } else if (msg.includes('unauthorized') || msg.includes('401')) {
            errorMessage = 'Authentication failed. Please check your API key.';
          } else if (msg.includes('too large') || msg.includes('file size')) {
            errorMessage = 'File is too large.';
          } else if (msg.includes('unsupported') || msg.includes('file type')) {
            errorMessage = 'File type not supported.';
          } else if (msg.includes('timeout')) {
            errorMessage = 'Upload timed out. Please try again.';
          } else {
            errorMessage = err.message;
          }
        }

        setUploadStatus({
          type: 'error',
          message: `${file.name}: ${errorMessage}`,
        });
      }
    }
    setUploadProgress(null);
  };

  const handleDelete = async (filename: string, vaultName?: string) => {
    if (!confirm(`Delete "${filename}"?`)) return;
    try {
      await api.deleteDocument(filename, vaultName);
      loadDocuments();
      onDocumentsChanged();
    } catch (err) {
      setUploadStatus({
        type: 'error',
        message: err instanceof Error ? err.message : 'Delete failed',
      });
    }
  };

  const handleDownload = (filename: string, vaultName?: string) => {
    const downloadUrl = api.getDownloadUrl(filename, vaultName);
    window.open(downloadUrl, '_blank');
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const formatDate = (iso: string) => {
    return new Date(iso).toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  return (
    <div className="p-6 space-y-6">
      {/* Upload Zone */}
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setIsDragOver(true);
        }}
        onDragLeave={() => setIsDragOver(false)}
        onDrop={handleDrop}
        className={`border-2 border-dashed rounded-xl p-8 text-center transition-colors ${
          isDragOver
            ? 'border-primary-500 bg-primary-500/10'
            : 'border-slate-700 hover:border-slate-600'
        }`}
      >
        <Upload className="w-10 h-10 mx-auto mb-4 text-slate-500" />
        <p className="text-slate-300 mb-2">Drag & drop files here, or</p>
        <label className="inline-block bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg cursor-pointer transition-colors">
          Browse Files
          <input
            type="file"
            multiple
            className="hidden"
            accept=".pdf,.md,.txt,.org,.rst,.html,.htm,.docx"
            onChange={(e) => handleUpload(e.target.files)}
          />
        </label>
        <p className="text-slate-500 text-sm mt-3">
          Supported: PDF, Markdown, TXT, Org, RST, HTML, DOCX
        </p>
      </div>

      {/* Upload Status */}
      {(uploadProgress || uploadStatus) && (
        <div
          className={`p-4 rounded-lg ${
            uploadProgress
              ? 'bg-slate-800 border border-slate-700'
              : uploadStatus?.type === 'success'
              ? 'bg-green-900/30 border border-green-800'
              : 'bg-red-900/30 border border-red-800'
          }`}
        >
          {uploadProgress ? (
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 animate-spin text-primary-400" />
              <span className="text-slate-300">{uploadProgress}</span>
            </div>
          ) : uploadStatus?.type === 'success' ? (
            <>
              <CheckCircle className="w-5 h-5 text-green-400 inline mr-3" />
              <span className="text-green-300">{uploadStatus.message}</span>
            </>
          ) : (
            <>
              <AlertCircle className="w-5 h-5 text-red-400 inline mr-3" />
              <span className="text-red-300">{uploadStatus?.message}</span>
            </>
          )}
        </div>
      )}

      {/* Documents List */}
      <div className="bg-slate-800 rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-700">
          <h2 className="font-medium text-slate-200">
            Indexed Documents ({documents.length})
          </h2>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center p-8">
            <Loader2 className="w-6 h-6 animate-spin text-slate-500" />
          </div>
        ) : error ? (
          <div className="p-8 text-center text-red-400">{error}</div>
        ) : documents.length === 0 ? (
          <div className="p-8 text-center text-slate-500">
            No documents indexed yet. Upload some files to get started.
          </div>
        ) : (
          <div className="divide-y divide-slate-700">
            {documents.map((doc) => (
              <div
                key={doc.filename}
                className="flex items-center justify-between px-4 py-3 hover:bg-slate-700/50"
              >
                <div className="flex items-center gap-3 min-w-0 flex-1">
                  <FileText className="w-5 h-5 text-slate-400 flex-shrink-0" />
                  <div className="min-w-0 flex-1">
                    <button
                      onClick={() => handleDownload(doc.filename, doc.vault_name)}
                      className="text-slate-200 hover:text-primary-400 truncate block text-left underline decoration-dotted underline-offset-2 transition-colors"
                      title={`Download ${doc.filename}`}
                    >
                      {doc.filename}
                    </button>
                    <div className="text-sm text-slate-500">
                      {formatSize(doc.file_size)} · {doc.chunk_count} chunks · {formatDate(doc.indexed_at)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleDownload(doc.filename, doc.vault_name)}
                    className="p-2 text-slate-400 hover:text-primary-400 hover:bg-slate-600 rounded-lg transition-colors"
                    title="Download"
                  >
                    <Download size={18} />
                  </button>
                  <button
                    onClick={() => handleDelete(doc.filename, doc.vault_name)}
                    className="p-2 text-slate-400 hover:text-red-400 hover:bg-slate-600 rounded-lg transition-colors"
                    title="Delete"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
