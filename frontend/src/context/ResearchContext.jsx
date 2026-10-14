import { createContext, useContext, useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getAllResearch, deleteResearch } from '../api/research';

const ResearchContext = createContext(null);

const RUNNING_STATUSES = new Set([
  'pending', 'planning', 'searching', 'collecting',
  'extracting', 'analyzing', 'verifying', 'synthesizing',
  'processing', 'running', 'in_progress', 'queued'
]);

const STORAGE_KEY = 'deep_research_history_cache';
const CACHE_DURATION = 5 * 60 * 1000; // 5 minutes

export function ResearchProvider({ children }) {
  const navigate = useNavigate();
  const location = useLocation();

  // Load cached history from localStorage on init
  const [history, setHistory] = useState(() => {
    try {
      const cached = localStorage.getItem(STORAGE_KEY);
      if (cached) {
        const { data, timestamp } = JSON.parse(cached);
        if (Date.now() - timestamp < CACHE_DURATION) {
          return data;
        }
      }
    } catch {}
    return [];
  });
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeJobId, setActiveJobIdState] = useState(() => {
    try {
      return sessionStorage.getItem('deep_research_active_job_id') || null;
    } catch {
      return null;
    }
  });
  
  // Track if we're actively polling a specific job
  const pollingJobIdRef = useRef(null);
  const historyRefreshIntervalRef = useRef(null);

  const setActiveJobId = useCallback((id) => {
    setActiveJobIdState(id);
    try {
      if (id) {
        sessionStorage.setItem('deep_research_active_job_id', String(id));
      } else {
        sessionStorage.removeItem('deep_research_active_job_id');
      }
    } catch {}
  }, []);

  // Save history to localStorage
  const saveHistoryToCache = useCallback((jobs) => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify({
        data: jobs,
        timestamp: Date.now()
      }));
    } catch {}
  }, []);

  const refreshHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const { data } = await getAllResearch();
      const jobs = Array.isArray(data) ? data : data?.research || data?.data || [];
      setHistory(jobs);
      saveHistoryToCache(jobs);
      return jobs;
    } catch (e) {
      console.warn('Could not refresh research history:', e);
      return [];
    } finally {
      setLoadingHistory(false);
    }
  }, [saveHistoryToCache]);

  // Initial load
  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  // Find any currently running job in history (excluding the one we're actively polling)
  const runningJob = history.find((j) =>
    RUNNING_STATUSES.has(j.status?.toLowerCase()) && (j._id || j.id) !== pollingJobIdRef.current
  );

  // Poll history periodically if there is an active job running in background
  // But only if we're not actively polling a specific job
  useEffect(() => {
    if (!runningJob || pollingJobIdRef.current) return;
    const interval = setInterval(() => {
      refreshHistory();
    }, 3500);
    return () => clearInterval(interval);
  }, [runningJob, refreshHistory]);

  const selectJob = useCallback((jobId) => {
    setActiveJobId(jobId);
    pollingJobIdRef.current = jobId;
    if (location.pathname !== '/dashboard') {
      navigate('/dashboard');
    }
  }, [location.pathname, navigate, setActiveJobId]);

  const clearPollingJob = useCallback(() => {
    pollingJobIdRef.current = null;
  }, []);

  const removeJob = useCallback(async (jobId) => {
    try {
      await deleteResearch(jobId);
      setHistory((prev) => prev.filter((j) => (j._id || j.id) !== jobId));
      if (activeJobId === jobId) {
        setActiveJobId(null);
      }
      return true;
    } catch (e) {
      // If 404, item was already deleted on server, update local list
      if (e.response?.status === 404) {
        setHistory((prev) => prev.filter((j) => (j._id || j.id) !== jobId));
        if (activeJobId === jobId) setActiveJobId(null);
        return true;
      }
      console.error('Failed to delete research job:', e);
      throw e;
    }
  }, [activeJobId, setActiveJobId]);

  return (
    <ResearchContext.Provider
      value={{
        history,
        loadingHistory,
        refreshHistory,
        activeJobId,
        setActiveJobId,
        runningJob,
        selectJob,
        removeJob,
        clearPollingJob,
      }}
    >
      {children}
    </ResearchContext.Provider>
  );
}

export function useResearchContext() {
  const ctx = useContext(ResearchContext);
  if (!ctx) {
    throw new Error('useResearchContext must be used within a ResearchProvider');
  }
  return ctx;
}
