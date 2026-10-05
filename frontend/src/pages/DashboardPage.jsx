import { useState, useEffect } from 'react';
import { getAllResearch } from '../api/research';
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
  const [history, setHistory] = useState([]);
  const [activeJobId, setActiveJobId] = useState(null);
  const { job, report, isPolling, error, startPolling } = useResearch();

  // Quick Answer state
  const [quickAnswerData, setQuickAnswerData] = useState(null); // { answer, query, model }

  const loadHistory = async () => {
    try {
      const { data } = await getAllResearch();
      const jobs = Array.isArray(data) ? data : data.research || data.data || [];
      setHistory(jobs);
    } catch (e) {
      console.warn('Could not load history:', e);
    }
  };

  useEffect(() => { loadHistory(); }, []);

  // Called when Deep Research job is created
  const handleJobCreated = (jobId) => {
    setQuickAnswerData(null); // clear any previous quick answer
    setActiveJobId(jobId);
    startPolling(jobId);
    loadHistory();
  };

  // Called when Quick Answer is returned by the router
  const handleQuickAnswer = (data) => {
    setQuickAnswerData(data);
    setActiveJobId(null); // clear any running deep job display
  };

  // Called when user clicks "Run Deep Research Instead" from QuickAnswerViewer
  const handleUpgradeToDeep = () => {
    if (!quickAnswerData) return;
    // Pre-fill the textarea by storing the query; the user re-submits in deep mode.
    // Since QueryInputCard manages its own state, we just clear quick answer
    // and let the user re-submit. A toast/hint would improve UX further.
    setQuickAnswerData(null);
  };

  const handleSelectJob = (jobId) => {
    setQuickAnswerData(null);
    setActiveJobId(jobId);
    startPolling(jobId);
  };

  useEffect(() => {
    if (!isPolling && job) loadHistory();
  }, [isPolling, job]);

  const showMission = isPolling || (job && !report);
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
            />
          </div>
        </TiltCard>

        {/* ── Error ── */}
        {error && !isPolling && (
          <div className="auth-error-box">⚠ {error}</div>
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
            <MissionControl job={job} jobId={activeJobId} />
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
