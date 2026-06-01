import { useCallback } from 'react';
import axios from 'axios';
import { useStore } from '../store/appStore';

const API_URL = 'http://localhost:5000/api';

const api = axios.create({
  baseURL: API_URL,
  timeout: 30000,
});

api.interceptors.response.use(
  (response) => response,
  (error) => {
    return Promise.reject(error);
  }
);

export function useApi() {
  const { setLoading, setError, addMessage, setSearchResults, setIndexStats } = useStore();

  const health = useCallback(async () => {
    try {
      const response = await api.get('/health'.replace('/api', ''));
      return response.data;
    } catch (error) {
      setError('Backend health check failed');
      return null;
    }
  }, [setError]);

  const chat = useCallback(
    async (message, conversationId = null) => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.post('/chat', {
          message,
          conversation_id: conversationId,
        });
        addMessage({
          id: Date.now(),
          role: 'user',
          content: message,
          timestamp: new Date(),
        });
        addMessage({
          id: Date.now() + 1,
          role: 'assistant',
          content: response.data.response,
          timestamp: new Date(),
        });
        return response.data;
      } catch (error) {
        const errorMsg = error.response?.data?.detail || error.message;
        setError(errorMsg);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addMessage]
  );

  const search = useCallback(
    async (query) => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.post('/search', { query });
        setSearchResults(response.data.results);
        return response.data;
      } catch (error) {
        const errorMsg = error.response?.data?.detail || error.message;
        setError(errorMsg);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, setSearchResults]
  );

  const executeAction = useCallback(
    async (command) => {
      setLoading(true);
      setError(null);
      try {
        const response = await api.post('/action', { command });
        addMessage({
          id: Date.now(),
          role: 'user',
          content: command,
          timestamp: new Date(),
        });
        addMessage({
          id: Date.now() + 1,
          role: 'assistant',
          content: response.data.message,
          timestamp: new Date(),
        });
        return response.data;
      } catch (error) {
        const errorMsg = error.response?.data?.detail || error.message;
        setError(errorMsg);
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError, addMessage]
  );

  const getIndexStats = useCallback(async () => {
    try {
      const response = await api.get('/index/stats');
      setIndexStats(response.data);
      return response.data;
    } catch (error) {
      setError('Failed to fetch index stats');
      return null;
    }
  }, [setError, setIndexStats]);

  const rebuildIndex = useCallback(
    async (fullRebuild = false) => {
      setLoading(true);
      try {
        const response = await api.post('/index/rebuild', {
          full_rebuild: fullRebuild,
        });
        return response.data;
      } catch (error) {
        setError('Failed to rebuild index');
        throw error;
      } finally {
        setLoading(false);
      }
    },
    [setLoading, setError]
  );

  const getChatHistory = useCallback(async () => {
    try {
      const response = await api.get('/chat/history');
      return response.data;
    } catch (error) {
      setError('Failed to fetch chat history');
      return null;
    }
  }, [setError]);

  const clearChat = useCallback(async () => {
    try {
      await api.post('/chat/clear');
      return true;
    } catch (error) {
      setError('Failed to clear chat');
      return false;
    }
  }, [setError]);

  return {
    health,
    chat,
    search,
    executeAction,
    getIndexStats,
    rebuildIndex,
    getChatHistory,
    clearChat,
  };
}
