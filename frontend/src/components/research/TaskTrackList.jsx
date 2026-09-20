export default function TaskTrackList({ tasks }) {
  if (!tasks || tasks.length === 0) {
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

  const statusColor = (status) => {
    switch (status?.toLowerCase()) {
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
                {t.category?.toUpperCase() || 'WEB'}
              </span>
              <span className={`badge ${statusColor(t.status)}`}>
                {t.status || 'queued'}
              </span>
            </div>
          </div>
          <div className="track-query">{t.query || t.subQuery || t.description}</div>
        </div>
      ))}
    </>
  );
}
