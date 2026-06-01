import React, { useEffect, useState } from 'react';
import { useStore } from './store/appStore';
import { ChatInterface } from './components/ChatInterface';
import { SearchInterface } from './components/SearchInterface';
import { Sidebar } from './components/Sidebar';
import { TopBar } from './components/TopBar';
import { useApi } from './hooks/useApi';

export default function App() {
  const [activeTab, setActiveTab] = useState('chat');
  const { initializeBackend, isConnected } = useStore();
  const { health } = useApi();

  useEffect(() => {
    initializeBackend();
  }, [initializeBackend]);

  useEffect(() => {
    const checkHealth = async () => {
      await health();
    };
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, [health]);

  return (
    <div className="flex h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
      {/* Sidebar */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />

      {/* Main content */}
      <div className="flex-1 flex flex-col">
        {/* Top bar */}
        <TopBar isConnected={isConnected} activeTab={activeTab} />

        {/* Content area */}
        <div className="flex-1 overflow-hidden">
          {activeTab === 'chat' && <ChatInterface />}
          {activeTab === 'search' && <SearchInterface />}
        </div>
      </div>
    </div>
  );
}
