import React, { useState } from 'react';
import { useStore } from '../store/appStore';
import { useApi } from '../hooks/useApi';
import { Search, Folder, FileText, Disc, Music, Loader } from 'lucide-react';
import { motion } from 'framer-motion';

const getIconForType = (itemType) => {
  const iconMap = {
    folder: <Folder className="w-5 h-5" />,
    app: <Disc className="w-5 h-5" />,
    video: <Disc className="w-5 h-5" />,
    audio: <Music className="w-5 h-5" />,
    document: <FileText className="w-5 h-5" />,
  };
  return iconMap[itemType] || <FileText className="w-5 h-5" />;
};

export function SearchInterface() {
  const { searchResults, isLoading, error, clearError } = useStore();
  const { search, executeAction } = useApi();
  const [query, setQuery] = useState('');
  const [searched, setSearched] = useState(false);

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    clearError();
    setSearched(true);

    try {
      await search(query);
    } catch (err) {
      console.error('Search error:', err);
    }
  };

  const handleOpen = async (result) => {
    clearError();
    try {
      await executeAction(`open ${result.name}`);
    } catch (err) {
      console.error('Action error:', err);
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col h-full bg-gradient-to-b from-slate-800 to-slate-900"
    >
      {/* Header */}
      <div className="px-6 py-4 border-b border-slate-700">
        <h2 className="text-xl font-bold text-white mb-4">Search</h2>

        {/* Search input */}
        <form onSubmit={handleSearch} className="flex gap-3">
          <div className="flex-1 relative">
            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search files, apps, folders..."
              disabled={isLoading}
              className="w-full bg-slate-700 text-white placeholder-slate-500 rounded-lg px-4 py-2 pl-10 focus:outline-none focus:ring-2 focus:ring-indigo-600 disabled:opacity-50 transition-all"
            />
            <Search className="absolute left-3 top-2.5 w-5 h-5 text-slate-500" />
          </div>
          <button
            type="submit"
            disabled={isLoading || !query.trim()}
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white rounded-lg px-6 py-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {isLoading ? <Loader className="w-4 h-4 animate-spin" /> : 'Search'}
          </button>
        </form>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto p-6">
        {error && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            className="bg-red-900/30 border border-red-700 text-red-300 rounded-lg p-4 mb-4 text-sm"
          >
            {error}
          </motion.div>
        )}

        {!searched ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <Search className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <p className="text-slate-400">Enter a search query to find files and apps</p>
            </div>
          </div>
        ) : isLoading ? (
          <div className="h-full flex items-center justify-center">
            <Loader className="w-8 h-8 text-indigo-600 animate-spin" />
          </div>
        ) : searchResults.length === 0 ? (
          <div className="h-full flex items-center justify-center text-center">
            <div>
              <p className="text-slate-400">No results found for "{query}"</p>
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-3">
            {searchResults.map((result) => (
              <motion.div
                key={result.path}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                whileHover={{ scale: 1.02 }}
                className="bg-slate-700/50 hover:bg-slate-700 border border-slate-600 rounded-lg p-4 cursor-pointer transition-all group"
                onClick={() => handleOpen(result)}
              >
                <div className="flex items-start gap-4">
                  <div className="text-slate-400 mt-1">{getIconForType(result.item_type)}</div>
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-white group-hover:text-indigo-400 transition-colors truncate">
                      {result.name}
                    </h3>
                    <p className="text-xs text-slate-500 truncate mt-1">{result.path}</p>
                    <p className="text-xs text-slate-600 mt-1 capitalize">{result.item_type}</p>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </div>
    </motion.div>
  );
}
