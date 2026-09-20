export default function SourcesList({ sources }) {
  if (!sources || sources.length === 0) {
    return (
      <div className="loading-state">
        <span className="spinner" />
        Awaiting search &amp; extraction…
      </div>
    );
  }

  const scoreColor = (score) => {
    if (!score && score !== 0) return '';
    if (score >= 8) return 'success';
    if (score >= 5) return '';
    return 'amber';
  };

  return (
    <>
      {sources.map((s, idx) => (
        <div key={s._id || s.id || idx} className="source-item">
          <div className="source-top">
            <a
              href={s.url}
              target="_blank"
              rel="noopener noreferrer"
              className="source-link"
            >
              {s.title || s.url}
            </a>
            {(s.credibility_score !== undefined || s.score !== undefined) && (
              <span className={`badge ${scoreColor(s.credibility_score ?? s.score)}`}>
                ★ {(s.credibility_score ?? s.score).toFixed(1)}
              </span>
            )}
          </div>
          {s.snippet && (
            <div className="source-snippet">{s.snippet}</div>
          )}
        </div>
      ))}
    </>
  );
}
