import { useState, useEffect } from 'react';
import { getAllResearch } from '../api/research';
import { useResearch } from '../hooks/useResearch';
import Sidebar from '../components/layout/Sidebar';
import QueryInputCard from '../components/research/QueryInputCard';
import MissionControl from '../components/research/MissionControl';
import ReportViewer from '../components/research/ReportViewer';
import TiltCard from '../components/ui/TiltCard';
import { Cpu, FlaskConical, Network, CheckCircle2, Search, FileText } from 'lucide-react';

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

  const handleJobCreated = (jobId) => {
    setActiveJobId(jobId);
    startPolling(jobId);
    loadHistory();
  };

  const handleSelectJob = (jobId) => {
    setActiveJobId(jobId);
    startPolling(jobId);
  };

  useEffect(() => {
    if (!isPolling && job) loadHistory();
  }, [isPolling, job]);

  const showMission = isPolling || (job && !report);
  const showReport = !!report;

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
          </div>
        </section>

        {/* ── Query Input ── */}
        <TiltCard intensity={6}>
          <div className="holo-card query-card">
            <QueryInputCard onJobCreated={handleJobCreated} disabled={isPolling} />
          </div>
        </TiltCard>

        {/* ── Error ── */}
        {error && !isPolling && (
          <div className="auth-error-box">⚠ {error}</div>
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
