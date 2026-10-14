import { NavLink, useNavigate } from 'react-router-dom';
import { Brain, Compass, FileText, Cpu, Settings, History, Trash2, LogOut } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { useResearchContext } from '../../context/ResearchContext';
import { logout } from '../../api/auth';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Mission Station', icon: <Compass size={17} /> },
  { to: '/reports', label: 'Reports Archive', icon: <FileText size={17} /> },
  { to: '/agents', label: 'Agent Monitor', icon: <Cpu size={17} /> },
  { to: '/settings', label: 'Settings & Themes', icon: <Settings size={17} /> },
];

export default function Sidebar({ history: propHistory, onSelectJob: propOnSelectJob, activeJobId: propActiveJobId }) {
  const { user, logoutUser } = useAuth();
  const researchCtx = useResearchContext();
  const navigate = useNavigate();

  const history = propHistory ?? researchCtx?.history ?? [];
  const activeJobId = propActiveJobId ?? researchCtx?.activeJobId;
  const onSelectJob = propOnSelectJob ?? researchCtx?.selectJob;
  const removeJob = researchCtx?.removeJob;

  const handleLogout = async () => {
    try { await logout(); } catch (_) {}
    logoutUser();
  };

  const statusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed': return 'success';
      case 'failed': return 'red';
      case 'cancelled': return 'amber';
      case 'processing': case 'running': case 'planning': case 'searching': case 'extracting': case 'analyzing': return 'cyan';
      default: return 'purple';
    }
  };

  const isRunningStatus = (status) => {
    return ['pending', 'planning', 'searching', 'collecting', 'extracting', 'analyzing', 'verifying', 'synthesizing', 'processing', 'running', 'in_progress'].includes(status?.toLowerCase());
  };

  const handleDelete = async (e, id) => {
    e.stopPropagation();
    if (!window.confirm('Delete this research session?')) return;
    try {
      if (removeJob) {
        await removeJob(id);
      }
    } catch (err) {
      alert('Could not delete session: ' + (err.response?.data?.message || err.message));
    }
  };

  const handleItemClick = (id) => {
    if (onSelectJob) {
      onSelectJob(id);
    } else {
      navigate('/dashboard');
    }
  };

  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="brand">
        <div className="brand-icon">
          <Brain size={22} />
        </div>
        <div className="brand-text">
          <h2>Deep Research</h2>
          <span className="brand-badge">v2.0 MERN AI</span>
        </div>
      </div>

      {/* Main Navigation Links */}
      <div className="nav-section">
        <div className="section-label">SYSTEM NAVIGATION</div>
        <nav className="nav-menu">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `nav-link ${isActive ? 'active' : ''}`}
            >
              <span className="nav-icon">{item.icon}</span>
              <span className="nav-label">{item.label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      {/* History */}
      <div className="sidebar-section">
        <div className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <History size={12} />
          <span>Research Sessions</span>
          {history.length > 0 && <span className="history-count">{history.length}</span>}
        </div>
        <div className="history-list">
          {!history || history.length === 0 ? (
            <div className="empty-history">No active sessions</div>
          ) : (
            history.map((job) => {
              const id = job._id || job.id;
              const isRunning = isRunningStatus(job.status);
              const isActive = activeJobId === id;

              return (
                <div
                  key={id}
                  className={`history-item ${isActive ? 'active' : ''}`}
                  onClick={() => handleItemClick(id)}
                  title={job.query}
                >
                  <div className="history-item-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 6 }}>
                    <div className="history-query-text">{job.query}</div>
                    <button
                      type="button"
                      className="history-delete-btn"
                      title="Delete this research"
                      onClick={(e) => handleDelete(e, id)}
                    >
                      <Trash2 size={12} />
                    </button>
                  </div>
                  <div className="history-item-status" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginTop: 4 }}>
                    <span className={`badge ${statusColor(job.status)}`} style={{ fontSize: '0.64rem', padding: '1px 6px', display: 'flex', alignItems: 'center', gap: 4 }}>
                      {isRunning && <span className="spinner" style={{ width: 8, height: 8 }} />}
                      {isRunning ? 'RUNNING' : (job.status || 'queued')}
                    </span>
                    <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)' }}>
                      {job.created_at ? new Date(job.created_at).toLocaleDateString([], { month: 'short', day: 'numeric' }) : ''}
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="status-row">
          <span className="status-dot" />
          <span className="status-label">Engine Online</span>
        </div>
        <div className="user-profile-row">
          <div className="avatar-chip">{user?.name ? user.name.slice(0, 2).toUpperCase() : 'OP'}</div>
          <div className="user-meta">
            <span className="user-name">{user?.name || 'Operator'}</span>
            <span className="user-email">{user?.email || 'operator@deep-research.ai'}</span>
          </div>
          <button className="logout-btn" onClick={handleLogout} title="Log Out">
            <LogOut size={14} />
          </button>
        </div>
      </div>
    </aside>
  );
}
