export default function TaskTrackList({ tasks, status }) {
  const isStopped = ['cancelled', 'failed', 'completed', 'done'].includes(status?.toLowerCase());

  if (!tasks || tasks.length === 0) {
    if (status?.toLowerCase() === 'cancelled') {
      return (
        <div className="empty-state" style={{ padding: '16px 0', color: 'var(--text-muted)' }}>
          Research stopped by user. No active tracks.
        </div>
      );
    }
    if (status?.toLowerCase() === 'failed') {
      return (
        <div className="empty-state" style={{ padding: '16px 0', color: 'var(--text-muted)' }}>
          Research stopped due to error.
        </div>
      );
    }
    if (['completed', 'done'].includes(status?.toLowerCase())) {
      return (
        <div className="empty-state" style={{ padding: '16px 0', color: 'var(--text-muted)' }}>
          No tracks recorded for this run.
        </div>
      );
    }
    return (
      <div className="loading-state">
        <span className="spinner" />
        Initializing planner agent…
      </div>
    );
  }

  const categoryColor = (cat) => {
    switch (cat?.toLowerCase()) {
      case 'web': return '';
      case 'academic': return 'purple';
      case 'market': return 'success';
      default: return 'amber';
    }
  };

  const statusColor = (taskStatus) => {
    if (isStopped && taskStatus !== 'completed') return 'amber';
    switch (taskStatus?.toLowerCase()) {
      case 'completed': case 'done': return 'success';
      case 'failed': return 'red';
      case 'running': case 'processing': return '';
      default: return 'purple';
    }
  };

  return (
    <>
      {tasks.map((t, idx) => (
        <div key={t._id || t.id || idx} className="track-item">
          <div className="track-header">
            <span className="track-name">Track #{idx + 1}</span>
            <div style={{ display: 'flex', gap: 5 }}>
              <span className={`badge ${categoryColor(t.category)}`}>
                {t.category?.toUpperCase() || 'RESEARCH'}
              </span>
              <span className={`badge ${statusColor(t.status)}`}>
                {isStopped && t.status !== 'completed' ? 'stopped' : (t.status || 'queued')}
              </span>
            </div>
          </div>
          <div className="track-query">{t.query || t.subQuery || t.description}</div>
        </div>
      ))}
    </>
  );
}
