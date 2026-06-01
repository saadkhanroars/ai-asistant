import React, { useEffect, useRef, useState } from 'react';
import { useStore } from '../store/appStore';
import { useApi } from '../hooks/useApi';
import { Send, Loader } from 'lucide-react';
import { MessageBubble } from './MessageBubble';
import { motion } from 'framer-motion';

export function ChatInterface() {
  const { messages, isLoading, error, clearError } = useStore();
  const { chat, clearChat } = useApi();
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSendMessage = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const messageText = input;
    setInput('');
    clearError();

    try {
      await chat(messageText);
    } catch (err) {
      console.error('Chat error:', err);
    }
  };

  const handleClearChat = async () => {
    if (window.confirm('Clear all messages?')) {
      await clearChat();
      const { clearMessages } = useStore.getState();
      clearMessages();
    }
  };

  return (
    <motion.div
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      className="flex flex-col h-full bg-gradient-to-b from-slate-800 to-slate-900"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-6 py-4 border-b border-slate-700">
        <h2 className="text-xl font-bold text-white">Chat</h2>
        {messages.length > 0 && (
          <button
            onClick={handleClearChat}
            className="text-sm text-slate-400 hover:text-red-400 transition-colors"
          >
            Clear
          </button>
        )}
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 ? (
          <div className="h-full flex items-center justify-center">
            <div className="text-center">
              <h3 className="text-lg font-semibold text-slate-400 mb-2">Start a conversation</h3>
              <p className="text-slate-500 text-sm">Ask me anything or use commands like:</p>
              <ul className="mt-2 text-slate-500 text-sm space-y-1">
                <li>"Open Chrome"</li>
                <li>"Search cats on Google"</li>
                <li>"Show my downloads"</li>
              </ul>
            </div>
          </div>
        ) : (
          messages.map((msg) => (
            <MessageBubble key={msg.id} message={msg} />
          ))
        )}

        {isLoading && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="flex justify-start"
          >
            <div className="bg-indigo-600 text-white rounded-lg px-4 py-2 rounded-bl-none flex items-center gap-2">
              <Loader className="w-4 h-4 animate-spin" />
              <span>Thinking...</span>
            </div>
          </motion.div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Error message */}
      {error && (
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          className="px-6 py-3 bg-red-900/30 border border-red-700 text-red-300 rounded-lg mx-4 mb-4 text-sm"
        >
          {error}
        </motion.div>
      )}

      {/* Input */}
      <div className="px-6 py-4 border-t border-slate-700">
        <form onSubmit={handleSendMessage} className="flex gap-3">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message or command..."
            disabled={isLoading}
            className="flex-1 bg-slate-700 text-white placeholder-slate-500 rounded-lg px-4 py-2 focus:outline-none focus:ring-2 focus:ring-indigo-600 disabled:opacity-50 transition-all"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className="bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700 text-white rounded-lg px-4 py-2 flex items-center gap-2 transition-all disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Send className="w-4 h-4" />
            <span className="hidden sm:inline">Send</span>
          </button>
        </form>
      </div>
    </motion.div>
  );
}
