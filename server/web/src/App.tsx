import { useState, useEffect } from 'react';
import { MessageSquare, FileText, Settings, Database } from 'lucide-react';
import { api, StatusResponse } from './api';
import ChatPanel from './components/ChatPanel';
import DocumentsPanel from './components/DocumentsPanel';
import SettingsPanel from './components/SettingsPanel';

type Tab = 'chat' | 'documents' | 'settings';

function App() {
  const [activeTab, setActiveTab] = useState<Tab>('chat');
  const [status, setStatus] = useState<StatusResponse | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  const loadStatus = async () => {
    try {
      const data = await api.getStatus();
      setStatus(data);
      setStatusError(null);
    } catch (err) {
      setStatusError('Cannot connect to server');
      setStatus(null);
    }
  };

  useEffect(() => {
    loadStatus();
    const interval = setInterval(loadStatus, 30000);
    return () => clearInterval(interval);
  }, []);

  const tabs: { id: Tab; label: string; icon: React.ReactNode }[] = [
    { id: 'chat', label: 'Chat', icon: <MessageSquare size={18} /> },
    { id: 'documents', label: 'Documents', icon: <FileText size={18} /> },
    { id: 'settings', label: 'Settings', icon: <Settings size={18} /> },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="bg-slate-800 border-b border-slate-700 px-6 py-4">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-primary-600 rounded-lg flex items-center justify-center">
              <span className="text-white font-bold text-lg">K</span>
            </div>
            <h1 className="text-xl font-semibold text-white">Knosi</h1>
          </div>
          <div className="flex items-center gap-2 text-sm">
            <Database size={16} className="text-slate-400" />
            {statusError ? (
              <span className="text-red-400">{statusError}</span>
            ) : status ? (
              <span className="text-slate-400">
                {status.document_count} docs · {status.chunk_count} chunks
              </span>
            ) : (
              <span className="text-slate-500">Loading...</span>
            )}
          </div>
        </div>
      </header>

      {/* Navigation */}
      <nav className="bg-slate-800/50 border-b border-slate-700 px-6">
        <div className="max-w-6xl mx-auto flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 -mb-px ${
                activeTab === tab.id
                  ? 'border-primary-500 text-primary-400'
                  : 'border-transparent text-slate-400 hover:text-slate-200'
              }`}
            >
              {tab.icon}
              {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        <div className="max-w-6xl mx-auto h-full">
          {activeTab === 'chat' && <ChatPanel />}
          {activeTab === 'documents' && <DocumentsPanel onDocumentsChanged={loadStatus} />}
          {activeTab === 'settings' && <SettingsPanel onSettingsChanged={loadStatus} />}
        </div>
      </main>
    </div>
  );
}

export default App;
