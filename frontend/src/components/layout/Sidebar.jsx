import { NavLink } from 'react-router-dom';
import { Brain, Compass, FileText, Cpu, Settings, History, LogOut, Radio } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { logout } from '../../api/auth';

const NAV_ITEMS = [
  { to: '/dashboard', label: 'Mission Station', icon: <Compass size={17} /> },
  { to: '/reports', label: 'Reports Archive', icon: <FileText size={17} /> },
  { to: '/agents', label: 'Agent Monitor', icon: <Cpu size={17} /> },
  { to: '/settings', label: 'Settings & Themes', icon: <Settings size={17} /> },
];

export default function Sidebar({ history = [], onSelectJob, activeJobId }) {
  const { user, logoutUser } = useAuth();

  const handleLogout = async () => {
    try { await logout(); } catch (_) {}
    logoutUser();
  };

  const getInitials = (name) => {
    if (!name) return 'OP';
    return name.split(' ').map((n) => n[0]).join('').toUpperCase().slice(0, 2);
  };

  const statusColor = (status) => {
    switch (status?.toLowerCase()) {
      case 'completed': return 'success';
      case 'failed': return 'red';
      case 'cancelled': return 'amber';
      case 'processing': case 'running': return '';
      default: return 'purple';
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
            history.map((job) => (
              <div
                key={job._id || job.id}
                className={`history-item ${activeJobId === (job._id || job.id) ? 'active' : ''}`}
                onClick={() => onSelectJob && onSelectJob(job._id || job.id)}
                title={job.query}
              >
                <div className="history-query-text">{job.query}</div>
                <div className="history-item-status">
                  <span className={`badge ${statusColor(job.status)}`} style={{ fontSize: '0.64rem', padding: '1px 6px' }}>
                    {job.status || 'queued'}
                  </span>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Footer */}
      <div className="sidebar-footer">
        <div className="status-row">
          <span className="status-dot" />
          <span className="status-label">Engine Online</span>
          <Radio size={12} style={{ marginLeft: 'auto', opacity: 0.5, color: 'var(--accent-green)' }} />
        </div>
        {user && (
          <div className="user-row">
            <div className="user-info">
              <div className="user-avatar">{getInitials(user.name || user.username)}</div>
              <div className="user-meta">
                <span className="user-name">{user.name || user.username || 'Operator'}</span>
                <span className="user-email">{user.email}</span>
              </div>
            </div>
            <button className="logout-btn" onClick={handleLogout} title="Sign Out">
              <LogOut size={13} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
