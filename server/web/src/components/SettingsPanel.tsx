import { useState, useEffect } from 'react';
import { Key, Server, CheckCircle, AlertCircle, Loader2 } from 'lucide-react';
import { api } from '../api';

interface Props {
  onSettingsChanged: () => void;
}

export default function SettingsPanel({ onSettingsChanged }: Props) {
  const [apiKey, setApiKey] = useState('');
  const [serverUrl, setServerUrl] = useState('');
  const [testResult, setTestResult] = useState<{ type: 'success' | 'error'; message: string } | null>(null);
  const [isTesting, setIsTesting] = useState(false);

  useEffect(() => {
    setApiKey(api.getApiKey());
    setServerUrl(import.meta.env.VITE_API_URL || window.location.origin);
  }, []);

  const handleSaveApiKey = () => {
    api.setApiKey(apiKey);
    setTestResult({ type: 'success', message: 'API key saved' });
    onSettingsChanged();
    setTimeout(() => setTestResult(null), 3000);
  };

  const handleTestConnection = async () => {
    setIsTesting(true);
    setTestResult(null);
    try {
      const status = await api.getStatus();
      setTestResult({
        type: 'success',
        message: `Connected! ${status.document_count} documents, ${status.chunk_count} chunks`,
      });
    } catch (err) {
      setTestResult({
        type: 'error',
        message: err instanceof Error ? err.message : 'Connection failed',
      });
    } finally {
      setIsTesting(false);
    }
  };

  return (
    <div className="p-6 max-w-2xl">
      <h2 className="text-xl font-semibold text-slate-100 mb-6">Settings</h2>

      <div className="space-y-6">
        {/* Server URL */}
        <div className="bg-slate-800 rounded-xl p-4">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
            <Server size={16} />
            Server URL
          </label>
          <input
            type="text"
            value={serverUrl}
            disabled
            className="w-full bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-slate-400 cursor-not-allowed"
          />
          <p className="text-xs text-slate-500 mt-2">
            Server URL is configured at build time via VITE_API_URL environment variable
          </p>
        </div>

        {/* API Key */}
        <div className="bg-slate-800 rounded-xl p-4">
          <label className="flex items-center gap-2 text-sm font-medium text-slate-300 mb-2">
            <Key size={16} />
            API Key
          </label>
          <div className="flex gap-2">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="Enter API key if required"
              className="flex-1 bg-slate-700 border border-slate-600 rounded-lg px-3 py-2 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
            />
            <button
              onClick={handleSaveApiKey}
              className="bg-primary-600 hover:bg-primary-700 text-white px-4 py-2 rounded-lg transition-colors"
            >
              Save
            </button>
          </div>
          <p className="text-xs text-slate-500 mt-2">
            API key is stored in your browser's local storage
          </p>
        </div>

        {/* Test Connection */}
        <div className="bg-slate-800 rounded-xl p-4">
          <label className="text-sm font-medium text-slate-300 mb-2 block">
            Test Connection
          </label>
          <button
            onClick={handleTestConnection}
            disabled={isTesting}
            className="bg-slate-700 hover:bg-slate-600 disabled:bg-slate-700 disabled:cursor-not-allowed text-slate-100 px-4 py-2 rounded-lg transition-colors flex items-center gap-2"
          >
            {isTesting ? (
              <>
                <Loader2 size={16} className="animate-spin" />
                Testing...
              </>
            ) : (
              'Test Connection'
            )}
          </button>

          {testResult && (
            <div
              className={`flex items-center gap-2 mt-3 p-3 rounded-lg ${
                testResult.type === 'success'
                  ? 'bg-green-900/30 border border-green-800 text-green-300'
                  : 'bg-red-900/30 border border-red-800 text-red-300'
              }`}
            >
              {testResult.type === 'success' ? (
                <CheckCircle size={16} />
              ) : (
                <AlertCircle size={16} />
              )}
              {testResult.message}
            </div>
          )}
        </div>

        {/* About */}
        <div className="bg-slate-800 rounded-xl p-4">
          <h3 className="text-sm font-medium text-slate-300 mb-2">About Knosi</h3>
          <p className="text-sm text-slate-400">
            Your personal knowledge base powered by AI. Upload PDFs, Markdown, and other documents
            to get intelligent answers grounded in your content.
          </p>
          <p className="text-sm text-slate-500 mt-2">
            <a href="https://knosi.ai" target="_blank" rel="noopener noreferrer" className="text-primary-400 hover:text-primary-300">
              knosi.ai
            </a>
          </p>
          <div className="mt-4 pt-4 border-t border-slate-700">
            <p className="text-xs text-slate-500">Version 1.0.0</p>
          </div>
        </div>
      </div>
    </div>
  );
}
