import Sidebar from '../components/layout/Sidebar';
import TiltCard from '../components/ui/TiltCard';
import {
  Cpu,
  Search,
  Network,
  FlaskConical,
  CheckCircle2,
  FileText,
  Activity,
  Database,
  Layers,
  Zap,
  ShieldCheck,
  Server,
  ArrowRight
} from 'lucide-react';

const AGENT_PROFILES = [
  {
    role: 'Planner Agent',
    icon: <Cpu size={22} className="agent-icon-accent" />,
    badge: 'STAGE 1',
    status: 'ONLINE',
    description: 'Deconstructs multifaceted queries into hierarchical sub-questions and orthogonal vector search tracks.',
    model: 'OpenRouter / Claude-3.5-Sonnet / GPT-4o',
    capabilities: ['Query Decomposition', 'Recursive Tree Search', 'Dependency Resolution', 'Track Budgeting']
  },
  {
    role: 'Search Engine Explorer',
    icon: <Search size={22} className="agent-icon-accent" />,
    badge: 'STAGE 2',
    status: 'ONLINE',
    description: 'Dispatches high-frequency parallel requests across web, academic papers, and market data sources.',
    model: 'Tavily Search API / Serper / ArXiv',
    capabilities: ['Multi-Engine Aggregation', 'Rate Limit Management', 'Domain Authority Scoring', 'Snippet Extraction']
  },
  {
    role: 'RAG Extraction Agent',
    icon: <Network size={22} className="agent-icon-accent" />,
    badge: 'STAGE 3',
    status: 'ONLINE',
    description: 'Parses raw HTML, cleans noisy web content, chunks text, and generates dense vector embeddings.',
    model: 'Qdrant Vector DB / Text-Embedding-3-Small',
    capabilities: ['DOM Sanitization', 'Vector Embedding', 'Cosine Similarity Filtering', 'Deduplication']
  },
  {
    role: 'Fact-Checking Judge',
    icon: <FlaskConical size={22} className="agent-icon-accent" />,
    badge: 'STAGE 4',
    status: 'ONLINE',
    description: 'Cross-verifies claims across independent sources to filter out hallucinations and biased claims.',
    model: 'Self-Consistency Cross-Encoder',
    capabilities: ['Epistemic Truth Verification', 'Contradiction Detection', 'Source Credibility Weighting', 'Hallucination Pruning']
  },
  {
    role: 'Epistemic Synthesizer',
    icon: <CheckCircle2 size={22} className="agent-icon-accent" />,
    badge: 'STAGE 5',
    status: 'ONLINE',
    description: 'Harmonizes disparate vector tracks into an integrated reasoning graph with structured causal findings.',
    model: 'Deep Reasoning Engine',
    capabilities: ['Graph Synthesis', 'Cross-Disciplinary Inference', 'Causal Reasoning', 'Gap Identification']
  },
  {
    role: 'Synthesis Scribe & Writer',
    icon: <FileText size={22} className="agent-icon-accent" />,
    badge: 'STAGE 6',
    status: 'ONLINE',
    description: 'Compiles the verified knowledge graph into an executive-grade Markdown dossier with IEEE/APA style citations.',
    model: 'Markdown Report Engine',
    capabilities: ['Executive Summarization', 'Citation Linking', 'HTML/PDF Compilation', 'Quality Assurance']
  }
];

const INFRA_TELEMETRY = [
  { name: 'Node.js Express Server', status: 'Operational', ping: '12ms', icon: <Server size={16} /> },
  { name: 'MongoDB Atlas Cluster', status: 'Connected', ping: '28ms', icon: <Database size={16} /> },
  { name: 'Distributed Job Queue (BullMQ)', status: 'Active', ping: '5ms', icon: <Zap size={16} /> },
  { name: 'Qdrant Vector Database', status: 'Online', ping: '42ms', icon: <Layers size={16} /> },
];

export default function AgentsPage() {
  return (
    <div className="app-layout">
      <Sidebar />

      <main className="main-content">
        {/* Header */}
        <section className="hero-section">
          <div className="hero-eyebrow">Autonomous Swarm Topology</div>
          <h1 className="hero-title" data-text="Multi-Agent Orchestration">
            Multi-Agent Orchestration
          </h1>
          <p className="hero-subtitle">
            Real-time topology, capability matrices, and pipeline telemetry for your 6 autonomous MERN research agents.
          </p>
        </section>

        {/* Telemetry Status Bar */}
        <div className="telemetry-bar holo-card">
          <div className="telemetry-title">
            <Activity size={16} style={{ color: 'var(--accent-cyan)' }} />
            <span>INFRASTRUCTURE STATUS</span>
          </div>
          <div className="telemetry-grid">
            {INFRA_TELEMETRY.map((t, idx) => (
              <div key={idx} className="telemetry-item">
                <span className="telemetry-icon">{t.icon}</span>
                <div>
                  <div className="telemetry-name">{t.name}</div>
                  <div className="telemetry-stat">
                    <span className="status-dot" /> {t.status} · {t.ping}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Pipeline Flow Visualization */}
        <div className="pipeline-flow-card holo-card">
          <div className="card-header">
            <span className="card-title">// EXECUTION PIPELINE ARCHITECTURE</span>
            <span className="badge">RECURSIVE DECOMPOSITION</span>
          </div>
          <div className="pipeline-steps-horizontal">
            {AGENT_PROFILES.map((agent, i) => (
              <div key={i} className="pipeline-step-box">
                <div className="pipeline-step-badge">{agent.badge}</div>
                <div className="pipeline-step-name">{agent.role.replace(' Agent', '')}</div>
                {i < AGENT_PROFILES.length - 1 && <ArrowRight size={14} className="pipeline-arrow" />}
              </div>
            ))}
          </div>
        </div>

        {/* Agent Cards Grid */}
        <div className="agents-grid">
          {AGENT_PROFILES.map((agent, idx) => (
            <TiltCard key={idx} intensity={8}>
              <div className="holo-card agent-detail-card">
                <div className="agent-card-header">
                  <div className="agent-card-icon-wrap">
                    {agent.icon}
                  </div>
                  <div>
                    <div className="agent-card-badge">{agent.badge}</div>
                    <h3 className="agent-card-role">{agent.role}</h3>
                  </div>
                  <span className="badge success" style={{ marginLeft: 'auto' }}>
                    {agent.status}
                  </span>
                </div>

                <p className="agent-card-desc">{agent.description}</p>

                <div className="agent-model-tag">
                  <ShieldCheck size={12} style={{ color: 'var(--accent-blue)' }} />
                  <span>{agent.model}</span>
                </div>

                <div className="agent-capabilities-list">
                  <div className="capabilities-label">Core Capabilities:</div>
                  <div className="capability-pills">
                    {agent.capabilities.map((cap, cIdx) => (
                      <span key={cIdx} className="capability-pill">
                        {cap}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </TiltCard>
          ))}
        </div>
      </main>
    </div>
  );
}
