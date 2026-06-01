import React, { useEffect, useState } from 'react';
import { useStore } from '../store/appStore';
import { useApi } from '../hooks/useApi';
import { Settings as SettingsIcon, Database, RefreshCw, Loader, AlertCircle } from 'lucide-react';
import { motion } from 'framer-motion';

export function SettingsInterface() {
  const { indexStats, aiEnabled, isLoading, error, clearError } = useStore();
  const { getIndexStats, rebuildIndex } = useApi();
  const [isRebuildingFull, setIsRebuildingFull] = useState(false);
  const [rebuildProgress, setRebuildProgress] = useState('');

  useEffect(() => {
    loadStats();
    const interval = setInterval(loadStats, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, []);

  const loadStats = async () => {
    clearError();
    try {
      await getIndexStats();
    } catch (err) {
      console.error('Failed to load index stats:', err);
    }
  };

  const handleRebuildIndex = async (fullRebuild = false) => {
    clearError();
    setIsRebuildingFull(fullRebuild);
    setRebuildProgress('Rebuilding index...');

    try {
      const response = await rebuildIndex(fullRebuild);
      setRebuildProgress(`${response.message}. This may take a minute...`);

      // Poll for completion
      let attempts = 0;
      const pollInterval = setInterval(async () => {
        attempts++;
        try {
          await loadStats();
          // Check if still rebuilding (simple heuristic: watch for stats update)
          if (attempts > 60) {
            // Stop polling after 1 minute
            clearInterval(pollInterval);
            setRebuildProgress('Rebuild completed!');
            setTimeout(() => setRebuildProgress(''), 3000);
          }
        } catch (err) {
          console.error('Poll error:', err);
        }
      }, 1000);

      // Clear polling after reasonable time
      setTimeout(() => {
        clearInterval(pollInterval);
        setIsRebuildingFull(false);
      }, 90000);
    } catch (err) {
      setRebuildProgress('Rebuild failed. Check logs.');
      setTimeout(() => setRebuildProgress(''), 3000);
      setIsRebuildingFull(false);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col h-full bg-gradient-to-b from-slate-800 to-slate-900 overflow-y-auto"
    >
      {/* Header */}
      <div className="sticky top-0 px-6 py-4 border-b border-slate-700 bg-slate-800/50 backdrop-blur">
        <h2 className="text-xl font-bold text-white flex items-center gap-2">
          <SettingsIcon className="w-6 h-6" />
          Settings
        </h2>
      </div>

      {/* Content */}
      <div className="flex-1 px-6 py-6 space-y-6">
        {/* Error Alert */}
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 flex items-start gap-3"
          >
            <AlertCircle className="w-5 h-5 flex-shrink-0 mt-0.5" />
            <div>
              <p className="font-semibold">Error</p>
              <p className="text-sm">{error}</p>
            </div>
          </motion.div>
        )}

        {/* AI Settings */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.1 }}
          className="bg-slate-700/30 border border-slate-600 rounded-lg p-6"
        >
          <h3 className="text-lg font-semibold text-white mb-4">AI Settings</h3>
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <p className="font-medium text-white">AI Chat</p>
                <p className="text-sm text-slate-400">
                  {aiEnabled ? 'Enabled (API key configured)' : 'Disabled (no API key)'}
                </p>
              </div>
              <div
                className={`w-12 h-6 rounded-full transition-colors ${
                  aiEnabled ? 'bg-green-600' : 'bg-slate-600'
                }`}
              >
                <div
                  className={`w-5 h-5 rounded-full bg-white transition-transform ${
                    aiEnabled ? 'translate-x-6' : 'translate-x-0.5'
                  } mt-0.5`}
                />
              </div>
            </div>
            {!aiEnabled && (
              <p className="text-xs text-slate-400">
                💡 To enable AI, add your OpenAI API key to <code className="bg-slate-800 px-2 py-1 rounded">.env</code>
              </p>
            )}
          </div>
        </motion.div>

        {/* Index Statistics */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.2 }}
          className="bg-slate-700/30 border border-slate-600 rounded-lg p-6"
        >
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <Database className="w-5 h-5" />
            Index Statistics
          </h3>

          {indexStats ? (
            <div className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-slate-800/50 rounded px-4 py-3">
                  <p className="text-xs text-slate-500 uppercase">Indexed Items</p>
                  <p className="text-2xl font-bold text-indigo-400">{indexStats.item_count.toLocaleString()}</p>
                </div>
                <div className="bg-slate-800/50 rounded px-4 py-3">
                  <p className="text-xs text-slate-500 uppercase">Watcher</p>
                  <p className="text-lg font-semibold text-green-400 capitalize">{indexStats.watcher_mode}</p>
                </div>
              </div>

              <div className="bg-slate-800/50 rounded px-4 py-3">
                <p className="text-xs text-slate-500 uppercase">Last Built</p>
                <p className="text-sm text-slate-300">
                  {indexStats.last_built === 'never'
                    ? 'Never (will build on first run)'
                    : new Date(indexStats.last_built).toLocaleString()}
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2 text-slate-400">
              <Loader className="w-4 h-4 animate-spin" />
              <p>Loading stats...</p>
            </div>
          )}
        </motion.div>

        {/* Index Management */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.3 }}
          className="bg-slate-700/30 border border-slate-600 rounded-lg p-6"
        >
          <h3 className="text-lg font-semibold text-white mb-4 flex items-center gap-2">
            <RefreshCw className="w-5 h-5" />
            Index Management
          </h3>

          {rebuildProgress && (
            <motion.div
              initial={{ opacity: 0, y: -5 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-blue-900/30 border border-blue-700 text-blue-300 rounded px-4 py-2 mb-4 text-sm flex items-center gap-2"
            >
              <Loader className="w-4 h-4 animate-spin" />
              {rebuildProgress}
            </motion.div>
          )}

          <div className="space-y-3">
            <button
              onClick={() => handleRebuildIndex(false)}
              disabled={isRebuildingFull || isLoading}
              className="w-full bg-slate-700 hover:bg-slate-600 text-white rounded px-4 py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isLoading && !isRebuildingFull ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <RefreshCw className="w-4 h-4" />
              )}
              <span>Refresh Index (Incremental)</span>
            </button>
            <button
              onClick={() => handleRebuildIndex(true)}
              disabled={isRebuildingFull || isLoading}
              className="w-full bg-gradient-to-r from-orange-600 to-red-600 hover:from-orange-700 hover:to-red-700 text-white rounded px-4 py-2 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {isRebuildingFull ? (
                <Loader className="w-4 h-4 animate-spin" />
              ) : (
                <Database className="w-4 h-4" />
              )}
              <span>Rebuild Index (Full)</span>
            </button>
          </div>

          <p className="text-xs text-slate-400 mt-4">
            💡 <strong>Refresh</strong> (30 seconds): Quick sync of changed files.
            <br />
            💡 <strong>Rebuild</strong> (1-5 minutes): Full rescan of all indexed folders.
          </p>
        </motion.div>

        {/* About */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.4 }}
          className="bg-slate-700/30 border border-slate-600 rounded-lg p-6"
        >
          <h3 className="text-lg font-semibold text-white mb-4">About</h3>
          <div className="space-y-2 text-sm text-slate-400">
            <p>
              <strong className="text-slate-300">Version:</strong> 1.0.0
            </p>
            <p>
              <strong className="text-slate-300">UI:</strong> Modern React/Electron
            </p>
            <p>
              <strong className="text-slate-300">Backend:</strong> FastAPI + Python
            </p>
            <p className="pt-2 text-xs">
              Desktop AI Assistant &copy; 2026. All rights reserved.
            </p>
          </div>
        </motion.div>
      </div>
    </motion.div>
  );
}
