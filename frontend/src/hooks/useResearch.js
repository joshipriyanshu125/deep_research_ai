import { useState, useEffect, useRef, useCallback } from 'react';
import { getResearchById, getAllReports } from '../api/research';

const POLL_INTERVAL = 2500; // ms

/**
 * Polls a research job until it's complete/failed.
 * Returns { job, report, isPolling, error, startPolling, stopPolling }
 */
export function useResearch() {
  const [job, setJob] = useState(null);
  const [report, setReport] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [error, setError] = useState(null);
  const intervalRef = useRef(null);
  const jobIdRef = useRef(null);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
  }, []);

  const fetchReport = useCallback(async (researchId) => {
    try {
      const { data } = await getAllReports({ researchId });
      const reports = Array.isArray(data) ? data : data.reports || data.data || [];
      if (reports.length > 0) {
        setReport(reports[0]);
      }
    } catch (e) {
      console.warn('Could not fetch report:', e);
    }
  }, []);

  const pollJob = useCallback(async () => {
    const id = jobIdRef.current;
    if (!id) return;
    try {
      const { data } = await getResearchById(id);
      const jobData = data.research || data.data || data;
      setJob(jobData);

      const status = jobData.status?.toLowerCase();
      if (status === 'completed' || status === 'done') {
        stopPolling();
        await fetchReport(id);
      } else if (status === 'failed' || status === 'cancelled') {
        stopPolling();
        setError(`Job ${status}.`);
      }
    } catch (e) {
      console.error('Poll error:', e);
      setError(e.message);
      stopPolling();
    }
  }, [stopPolling, fetchReport]);

  const startPolling = useCallback((jobId) => {
    stopPolling();
    jobIdRef.current = jobId;
    setJob(null);
    setReport(null);
    setError(null);
    setIsPolling(true);
    pollJob(); // immediate first poll
    intervalRef.current = setInterval(pollJob, POLL_INTERVAL);
  }, [pollJob, stopPolling]);

  // Cleanup on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  return { job, report, isPolling, error, startPolling, stopPolling };
}
