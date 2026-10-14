import { useState, useEffect, useRef, useCallback } from 'react';
import { useResearchContext } from '../context/ResearchContext';
import {
  cancelResearch,
  getResearchById,
  getResearchEvidence,
  getResearchSources,
  getReportForResearch,
} from '../api/research';
import {
  normalizeEvidence,
  normalizeJob,
  normalizeReport,
  normalizeSource,
} from '../utils/researchAdapter';

const POLL_INTERVAL = 2500; // ms

// Finished runs are remembered so that navigating away from the dashboard and
// back renders the completed report immediately, instead of replaying the live
// "Decomposing research query…" mission view for one polling round-trip.
const FINISHED_RUN_CACHE = new Map();
const FINISHED_RUN_CACHE_LIMIT = 25;
const FINISHED_RUN_STORAGE_KEY = 'deep_research_finished_run_v1';

function rememberFinishedRun(id, job, report) {
  if (!id || !job || !report) return;
  const key = String(id);
  FINISHED_RUN_CACHE.set(key, { job, report });
  if (FINISHED_RUN_CACHE.size > FINISHED_RUN_CACHE_LIMIT) {
    const oldest = FINISHED_RUN_CACHE.keys().next().value;
    FINISHED_RUN_CACHE.delete(oldest);
  }
  // Also persist the latest finished run so a full page reload is instant too.
  try {
    sessionStorage.setItem(FINISHED_RUN_STORAGE_KEY, JSON.stringify({ id: key, job, report }));
  } catch {
    // Storage unavailable or full — the in-memory cache still works.
  }
}

function recallFinishedRun(id) {
  if (!id) return null;
  const key = String(id);
  const cached = FINISHED_RUN_CACHE.get(key);
  if (cached) return cached;
  try {
    const raw = sessionStorage.getItem(FINISHED_RUN_STORAGE_KEY);
    if (!raw) return null;
    const saved = JSON.parse(raw);
    if (saved && String(saved.id) === key && saved.job && saved.report) {
      FINISHED_RUN_CACHE.set(key, { job: saved.job, report: saved.report });
      return saved;
    }
  } catch {
    // Corrupt cache entry — ignore it.
  }
  return null;
}

function responsePayload(response) {
  return response?.data?.research || response?.data?.data || response?.data;
}

/**
 * Poll a research job until it reaches a terminal state, hydrate the artifacts
 * that the FastAPI deployment stores in separate collections, and provide a
 * real server-side cancellation operation for the Stop button.
 */
export function useResearch() {
  const { clearPollingJob } = useResearchContext();
  const [job, setJob] = useState(null);
  const [report, setReport] = useState(null);
  const [isPolling, setIsPolling] = useState(false);
  const [isCancelling, setIsCancelling] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const intervalRef = useRef(null);
  const jobIdRef = useRef(null);
  const generationRef = useRef(0);

  const stopPolling = useCallback(() => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    setIsPolling(false);
    clearPollingJob();
  }, [clearPollingJob]);

  const hydrateArtifacts = useCallback(async (researchId, jobData, generation) => {
    const sourceRequest = jobData.sources.length > 0
      ? Promise.resolve({ data: jobData.sources })
      : getResearchSources(researchId);
    const evidenceRequest = jobData.evidence.length > 0
      ? Promise.resolve({ data: jobData.evidence })
      : getResearchEvidence(researchId);

    const [reportResult, sourcesResult, evidenceResult] = await Promise.allSettled([
      getReportForResearch(researchId),
      sourceRequest,
      evidenceRequest,
    ]);

    if (generation !== generationRef.current || jobIdRef.current !== researchId) return;

    const sources = sourcesResult.status === 'fulfilled'
      ? (Array.isArray(sourcesResult.value?.data)
        ? sourcesResult.value.data.map(normalizeSource)
        : [])
      : jobData.sources;
    const evidence = evidenceResult.status === 'fulfilled'
      ? (Array.isArray(evidenceResult.value?.data)
        ? evidenceResult.value.data.map(normalizeEvidence)
        : [])
      : jobData.evidence;

    if (reportResult.status === 'fulfilled') {
      const payload = responsePayload(reportResult.value);
      // A list-shaped payload (Node's GET /reports?researchId=...) must never
      // be normalised as if it were the report document itself.
      const rawReport = Array.isArray(payload) ? payload[0] : payload;
      if (rawReport) {
        const normalizedReport = normalizeReport(rawReport);
        const reportSources = normalizedReport.sources.length > 0
          ? normalizedReport.sources
          : sources;
        const reportEvidence = normalizedReport.evidence.length > 0
          ? normalizedReport.evidence
          : evidence;
        const reportFactChecks = normalizedReport.factChecks.length > 0
          ? normalizedReport.factChecks
          : jobData.factChecks;
        const reportCitations = normalizedReport.citations.length > 0
          ? normalizedReport.citations
          : reportSources;
        const reportVerification = normalizedReport.verificationSummary;
        const hasVerificationData = Boolean(
          reportVerification.liveWebResearch
          || reportVerification.independentVerification
          || reportVerification.totalSources
          || reportVerification.evidenceCount
          || reportVerification.attemptedClaims
          || reportVerification.providers?.length
          || reportVerification.geminiIntegration?.active,
        );

        const reportBody = `${normalizedReport.markdownContent || ''}\n${normalizedReport.executiveSummary || ''}`.trim();

        if (!reportBody && reportSources.length === 0 && reportCitations.length === 0) {
          // Never present a blank document as a finished research report.
          setError('Research finished, but its report contains no content. Please re-run this research.');
        } else {
          const nextReport = {
            ...normalizedReport,
            sources: reportSources,
            evidence: reportEvidence,
            factChecks: reportFactChecks,
            citations: reportCitations,
            verificationSummary: hasVerificationData
              ? reportVerification
              : {
                ...jobData.verificationSummary,
                liveWebResearch: reportSources.some((source) =>
                  source.metadata?.fetched || source.metadata?.search_provider,
                ),
                totalSources: reportSources.length,
                evidenceCount: reportEvidence.length,
                attemptedClaims: reportFactChecks.length,
              },
          };
          setReport(nextReport);
          rememberFinishedRun(researchId, jobData, nextReport);
        }
      }
    }

    if (sources.length > 0 || evidence.length > 0) {
      setJob((current) => current && current.id === researchId
        ? { ...current, sources, evidence }
        : current);
    }

    if (reportResult.status === 'rejected') {
      console.warn('Research completed but report could not be loaded:', reportResult.reason);
      setError('Research completed, but the final report could not be loaded. Please open this run again.');
    }
  }, []);

  const pollJob = useCallback(async (pollId, generation) => {
    if (!pollId || generation !== generationRef.current || jobIdRef.current !== pollId) return;

    try {
      const { data } = await getResearchById(pollId);
      if (generation !== generationRef.current || jobIdRef.current !== pollId) return;

      const jobData = normalizeJob(data);
      setJob(jobData);

      const status = jobData.status;
      if (status === 'completed' || status === 'done') {
        stopPolling();
        await hydrateArtifacts(pollId, jobData, generation);
      } else if (status === 'failed') {
        stopPolling();
        setError(jobData.errorMessage || `Job ${status}.`);
      } else if (status === 'cancelled') {
        stopPolling();
        setError(null);
        setNotice('Research stopped. You can start another Quick Answer or Deep Research run.');
      }
    } catch (e) {
      if (generation !== generationRef.current || jobIdRef.current !== pollId) return;
      console.error('Poll error:', e);
      setError(e.message || 'Could not read research progress.');
      stopPolling();
    }
  }, [hydrateArtifacts, stopPolling]);

  const startPolling = useCallback((jobId) => {
    stopPolling();
    const id = String(jobId);
    const generation = generationRef.current + 1;
    generationRef.current = generation;
    jobIdRef.current = id;
    setError(null);
    setNotice(null);
    setIsCancelling(false);

    // A finished run we have already hydrated: render it right away so the
    // mission view never flashes when the user comes back to the dashboard.
    const cachedRun = recallFinishedRun(id);
    if (cachedRun && ['completed', 'done'].includes(cachedRun.job?.status?.toLowerCase())) {
      setJob(cachedRun.job);
      setReport(cachedRun.report);
      setIsPolling(false);
      // Refresh quietly in the background; the report stays on screen while
      // this runs, so the mission view is never shown again.
      pollJob(id, generation);
      return;
    }

    setJob(null);
    setReport(null);
    setIsPolling(true);

    pollJob(id, generation);
    intervalRef.current = setInterval(() => pollJob(id, generation), POLL_INTERVAL);
  }, [pollJob, stopPolling]);

  const cancelActiveResearch = useCallback(async () => {
    const id = jobIdRef.current;
    if (!id || isCancelling) return;

    const generation = generationRef.current + 1;
    generationRef.current = generation;
    stopPolling();
    setIsCancelling(true);
    setError(null);
    setNotice(null);

    // Optimistically reflect cancelled state so UI immediately stops
    setJob((prev) => (prev ? {
      ...prev,
      status: 'cancelled',
      current_step: 'Research stopped by user.',
      currentStep: 'Research stopped by user.'
    } : prev));

    try {
      const { data } = await cancelResearch(id);
      const cancelledJob = normalizeJob(data);
      setJob(cancelledJob);
      setReport(null);
      setNotice('Research stopped successfully.');
    } catch (e) {
      // A failed cancel request must not be presented as a successful stop.
      setError(e.message || 'Could not stop the research job.');
      startPolling(id);
    } finally {
      setIsCancelling(false);
    }
  }, [isCancelling, startPolling, stopPolling]);

  // Cleanup on unmount
  useEffect(() => () => stopPolling(), [stopPolling]);

  return {
    job,
    report,
    isPolling,
    isCancelling,
    error,
    notice,
    startPolling,
    stopPolling,
    cancelActiveResearch,
  };
}
