import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getAllResearch, deleteResearch } from '../api/research';

const ResearchContext = createContext(null);

const RUNNING_STATUSES = new Set([
  'pending', 'planning', 'searching', 'collecting',
  'extracting', 'analyzing', 'verifying', 'synthesizing',
  'processing', 'running', 'in_progress', 'queued'
]);

export function ResearchProvider({ children }) {
  const navigate = useNavigate();
  const location = useLocation();

  const [history, setHistory] = useState([]);
  const [loadingHistory, setLoadingHistory] = useState(false);
  const [activeJobId, setActiveJobIdState] = useState(() => {
    try {
      return sessionStorage.getItem('deep_research_active_job_id') || null;
    } catch {
      return null;
    }
  });

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

  const refreshHistory = useCallback(async () => {
    try {
      setLoadingHistory(true);
      const { data } = await getAllResearch();
      const jobs = Array.isArray(data) ? data : data?.research || data?.data || [];
      setHistory(jobs);
      return jobs;
    } catch (e) {
      console.warn('Could not refresh research history:', e);
      return [];
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  // Initial load
  useEffect(() => {
    refreshHistory();
  }, [refreshHistory]);

  // Find any currently running job in history
  const runningJob = history.find((j) =>
    RUNNING_STATUSES.has(j.status?.toLowerCase())
  );

  // Poll history periodically if there is an active job running in background
  useEffect(() => {
    if (!runningJob) return;
    const interval = setInterval(() => {
      refreshHistory();
    }, 3500);
    return () => clearInterval(interval);
  }, [runningJob, refreshHistory]);

  const selectJob = useCallback((jobId) => {
    setActiveJobId(jobId);
    if (location.pathname !== '/dashboard') {
      navigate('/dashboard');
    }
  }, [location.pathname, navigate, setActiveJobId]);

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
