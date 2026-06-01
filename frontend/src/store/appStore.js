import { create } from 'zustand';
import axios from 'axios';

const API_URL = 'http://localhost:5000/api';

export const useStore = create((set, get) => ({
  // State
  isConnected: false,
  backendUrl: API_URL,
  currentTheme: 'dark',
  aiEnabled: false,
  indexStats: null,
  messages: [],
  searchResults: [],
  isLoading: false,
  error: null,

  // Actions
  initializeBackend: async () => {
    try {
      const response = await axios.get(`${API_URL.replace('/api', '')}/health`);
      set({
        isConnected: true,
        aiEnabled: response.data.ai_enabled === 'yes',
      });
    } catch (err) {
      set({ isConnected: false, error: 'Cannot connect to backend' });
    }
  },

  setLoading: (isLoading) => set({ isLoading }),
  setError: (error) => set({ error }),
  clearError: () => set({ error: null }),

  addMessage: (message) => {
    set((state) => ({
      messages: [...state.messages, message],
    }));
  },

  setMessages: (messages) => set({ messages }),
  clearMessages: () => set({ messages: [] }),

  setSearchResults: (results) => set({ searchResults: results }),
  clearSearchResults: () => set({ searchResults: [] }),

  setIndexStats: (stats) => set({ indexStats: stats }),

  setTheme: (theme) => set({ currentTheme: theme }),
}));
