import { useState, useEffect } from 'react';
import { useResearchContext } from '../context/ResearchContext';
import { useResearch } from '../hooks/useResearch';
import Sidebar from '../components/layout/Sidebar';
import QueryInputCard from '../components/research/QueryInputCard';
import MissionControl from '../components/research/MissionControl';
import ReportViewer from '../components/research/ReportViewer';
import QuickAnswerViewer from '../components/research/QuickAnswerViewer';
import TiltCard from '../components/ui/TiltCard';
import { Cpu, FlaskConical, Network, CheckCircle2, Search, FileText, Zap } from 'lucide-react';

const AGENTS = [
  { icon: <Cpu size={12} />, label: 'Planner' },
  { icon: <Search size={12} />, label: 'Search' },
  { icon: <Network size={12} />, label: 'Research' },
  { icon: <FlaskConical size={12} />, label: 'Fact Check' },
  { icon: <CheckCircle2 size={12} />, label: 'Analysis' },
  { icon: <FileText size={12} />, label: 'Writer' },
];

export default function DashboardPage() {
  const {
    history,
    activeJobId,
    setActiveJobId,
    runningJob,
    selectJob,
    refreshHistory,
  } = useResearchContext();

  const {
    job,
    report,
    isPolling,
    isCancelling,
    error,
    notice,
    startPolling,
    cancelActiveResearch,
  } = useResearch();

  // Quick Answer state
  const [quickAnswerData, setQuickAnswerData] = useState(null); // { answer, query, model }
  const [deepResearchSeed, setDeepResearchSeed] = useState(null);

  // Restore or start polling activeJobId on mount
  useEffect(() => {
    if (activeJobId) {
      startPolling(activeJobId);
    } else if (runningJob) {
      const runId = runningJob._id || runningJob.id;
      setActiveJobId(runId);
      startPolling(runId);
    }
  }, []);

  // Called when Deep Research job is created
  const handleJobCreated = (jobId) => {
    setQuickAnswerData(null);
    selectJob(jobId);
    startPolling(jobId);
    refreshHistory();
  };

  // Called when Quick Answer is returned by the router
  const handleQuickAnswer = (data) => {
    setQuickAnswerData(data);
    setActiveJobId(null);
  };

  // Called when user clicks "Run Deep Research Instead" from QuickAnswerViewer
  const handleUpgradeToDeep = () => {
    if (!quickAnswerData) return;
    setDeepResearchSeed(`${quickAnswerData.query}`);
    setQuickAnswerData(null);
    setActiveJobId(null);
  };

  const handleSelectJob = (jobId) => {
    setQuickAnswerData(null);
    selectJob(jobId);
    startPolling(jobId);
  };

  useEffect(() => {
    if (!isPolling && job) refreshHistory();
  }, [isPolling, job, refreshHistory]);

  const showMission = Boolean(activeJobId) && (isPolling || (job && !report));
  const showReport = !!report;
  const showQuickAnswer = !!quickAnswerData && !showMission && !showReport;

  return (
    <div className="app-layout">
      <Sidebar history={history} onSelectJob={handleSelectJob} activeJobId={activeJobId} />

      <main className="main-content">
        {/* ── Hero ── */}
        <section className="hero-section">
          <div className="hero-eyebrow">Autonomous Multi-Agent System</div>
          <h1 className="hero-title" data-text="Autonomous Deep Research Platform">
            Autonomous Deep Research Platform
          </h1>
          <p className="hero-subtitle">
            Recursive query decomposition · Multi-track vector search · RAG evidence extraction ·
            Epistemic fact synthesis — all orchestrated by your MERN agent stack.
          </p>
          <div className="agent-pills">
            {AGENTS.map((a) => (
              <div key={a.label} className="badge" style={{ padding: '5px 12px', gap: 5, fontSize: '0.7rem' }}>
                {a.icon} {a.label}
              </div>
            ))}
            <div className="badge badge--quick" style={{ padding: '5px 12px', gap: 5, fontSize: '0.7rem' }}>
              <Zap size={12} fill="currentColor" /> Quick Answer
            </div>
          </div>
        </section>

        {/* ── Query Input ── */}
        <TiltCard intensity={6}>
          <div className="holo-card query-card">
            <QueryInputCard
              onJobCreated={handleJobCreated}
              onQuickAnswer={handleQuickAnswer}
              disabled={isPolling}
              initialQuery={deepResearchSeed}
            />
          </div>
        </TiltCard>

        {/* ── Background Running Job Banner ── */}
        {runningJob && (runningJob._id || runningJob.id) !== activeJobId && (
          <div className="running-job-banner">
            <div className="running-job-info">
              <span className="spinner" style={{ width: 14, height: 14 }} />
              <span>
                <strong>Research in progress:</strong> "{runningJob.query}" —{' '}
                <span className="running-job-step">{runningJob.current_step || 'Executing vectors…'}</span>
              </span>
            </div>
            <button
              type="button"
              className="btn-primary"
              style={{ padding: '6px 14px', fontSize: '0.78rem' }}
              onClick={() => handleSelectJob(runningJob._id || runningJob.id)}
            >
              VIEW LIVE PROGRESS →
            </button>
          </div>
        )}

        {/* ── Error ── */}
        {error && !isPolling && (
          <div className="auth-error-box">⚠ {error}</div>
        )}
        {notice && !isPolling && (
          <div className="notice-box">✓ {notice}</div>
        )}

        {/* ── Quick Answer ── */}
        {showQuickAnswer && (
          <TiltCard intensity={3}>
            <QuickAnswerViewer
              answer={quickAnswerData.answer}
              query={quickAnswerData.query}
              model={quickAnswerData.model}
              onUpgrade={handleUpgradeToDeep}
            />
          </TiltCard>
        )}

        {/* ── Mission Control ── */}
        {showMission && (
          <div className="holo-card mission-card">
            <MissionControl
              job={job}
              jobId={activeJobId}
              onCancel={cancelActiveResearch}
              isCancelling={isCancelling}
            />
          </div>
        )}

        {/* ── Report ── */}
        {showReport && (
          <>
            <ReportViewer report={report} />
          </>
        )}
      </main>
    </div>
  );
}
