import { Brain, Zap, History, LogOut, Radio } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { logout } from '../../api/auth';

export default function Sidebar({ history, onSelectJob, activeJobId }) {
  const { user, logoutUser } = useAuth();

  const handleLogout = async () => {
    try { await logout(); } catch (_) {}
    logoutUser();
  };

  const getInitials = (name) => {
    if (!name) return 'U';
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
          <Brain size={20} />
        </div>
        <div className="brand-text">
          <h2>Deep Research</h2>
          <span className="brand-badge">v2.0 MERN</span>
        </div>
      </div>

      {/* History */}
      <div className="sidebar-section">
        <div className="section-label" style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <History size={11} />
          Research History
        </div>
        <div className="history-list">
          {!history || history.length === 0 ? (
            <div className="empty-history">No research runs yet</div>
          ) : (
            history.map((job) => (
              <div
                key={job._id || job.id}
                className={`history-item ${activeJobId === (job._id || job.id) ? 'active' : ''}`}
                onClick={() => onSelectJob && onSelectJob(job._id || job.id)}
                title={job.query}
              >
                <div>{job.query}</div>
                <div className="history-item-status">
                  <span className={`badge ${statusColor(job.status)}`} style={{ fontSize: '0.66rem', padding: '1px 6px' }}>
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
          <span>Backend Online</span>
          <Radio size={11} style={{ marginLeft: 'auto', opacity: 0.4 }} />
        </div>
        {user && (
          <div className="user-row">
            <div className="user-info">
              <div className="user-avatar">{getInitials(user.name || user.username)}</div>
              <span className="user-name">{user.name || user.username || user.email}</span>
            </div>
            <button className="logout-btn" onClick={handleLogout} title="Sign out">
              <LogOut size={12} />
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
