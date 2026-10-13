export default function SourcesList({ sources, emptyMessage }) {
  if (!sources || sources.length === 0) {
    return (
      <div className="loading-state">
        {emptyMessage || (
          <>
            <span className="spinner" />
            Awaiting search &amp; extraction…
          </>
        )}
      </div>
    );
  }

  const scoreColor = (score) => {
    if (!score && score !== 0) return '';
    const normalized = score <= 1 ? score * 10 : score;
    if (normalized >= 8) return 'success';
    if (normalized >= 5) return '';
    return 'amber';
  };

  const publisherHost = (value) => {
    try { return new URL(value).hostname; } catch { return value; }
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
            {(s.credibility_score !== undefined || s.relevanceScore !== undefined || s.score !== undefined) && (
              <span className={`badge ${scoreColor(s.credibility_score ?? s.relevanceScore ?? s.score)}`}>
                ★ {((s.credibility_score ?? s.relevanceScore ?? s.score) <= 1
                  ? (s.credibility_score ?? s.relevanceScore ?? s.score) * 10
                  : (s.credibility_score ?? s.relevanceScore ?? s.score)).toFixed(1)}
              </span>
            )}
          </div>
          {s.snippet && (
            <div className="source-snippet">{s.snippet}</div>
          )}
          {(s.sourceType || s.category || s.extractionStatus) && (
            <div className="source-snippet" style={{ opacity: 0.7 }}>
              {(s.isVerificationSource ? 'VERIFICATION · ' : '')}
              {(s.sourceType || s.category || 'source').toUpperCase()} · {s.extractionStatus || 'collected'}
              {s.provider ? ` · ${s.provider}` : ''}
              {s.publisherUrl ? ` · publisher: ${publisherHost(s.publisherUrl)}` : ''}
            </div>
          )}
          {s.isVerificationSource && (
            <span className="badge success" style={{ alignSelf: 'flex-start' }}>
              ✓ Used for independent claim verification
            </span>
          )}
        </div>
      ))}
    </>
  );
}
