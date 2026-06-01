import React from 'react';
import { Wifi, WifiOff, Minimize2, Maximize2, X } from 'lucide-react';
import { motion } from 'framer-motion';

export function TopBar({ isConnected, activeTab }) {
  const handleMinimize = () => {
    window.electronAPI?.minimizeWindow();
  };

  const handleMaximize = () => {
    window.electronAPI?.maximizeWindow();
  };

  const handleClose = () => {
    window.electronAPI?.closeWindow();
  };

  const tabNames = {
    chat: 'Chat',
    search: 'Search',
    settings: 'Settings',
  };

  return (
    <motion.div
      initial={{ y: -100, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.3 }}
      className="bg-slate-800/50 backdrop-blur border-b border-slate-700 px-6 py-3 flex items-center justify-between"
    >
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${
          isConnected ? 'bg-green-500 shadow-lg shadow-green-500' : 'bg-red-500 shadow-lg shadow-red-500'
        }`} />
        <span className="text-sm text-slate-400">
          {isConnected ? 'Connected' : 'Disconnected'}
        </span>
        <span className="text-slate-600">•</span>
        <span className="text-sm text-slate-400">{tabNames[activeTab] || 'Unknown'}</span>
      </div>

      {/* Window controls */}
      <div className="flex items-center gap-2">
        <button
          onClick={handleMinimize}
          className="p-2 hover:bg-slate-700 rounded transition-colors text-slate-400 hover:text-white"
        >
          <Minimize2 className="w-4 h-4" />
        </button>
        <button
          onClick={handleMaximize}
          className="p-2 hover:bg-slate-700 rounded transition-colors text-slate-400 hover:text-white"
        >
          <Maximize2 className="w-4 h-4" />
        </button>
        <button
          onClick={handleClose}
          className="p-2 hover:bg-red-900/30 rounded transition-colors text-slate-400 hover:text-red-400"
        >
          <X className="w-4 h-4" />
        </button>
      </div>
    </motion.div>
  );
}
