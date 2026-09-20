import { useState } from 'react';
import { Play, Layers, Globe, BookOpen, TrendingUp } from 'lucide-react';
import { createResearch } from '../../api/research';

export default function QueryInputCard({ onJobCreated, disabled }) {
  const [query, setQuery] = useState('');
  const [depth, setDepth] = useState(2);
  const [breadth, setBreadth] = useState(3);
  const [categories, setCategories] = useState({ web: true, academic: true, market: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const toggleCategory = (key) =>
    setCategories((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleSubmit = async () => {
    const trimmed = query.trim();
    if (!trimmed) { setError('Please enter a research query.'); return; }
    setError('');
    setLoading(true);
    const cats = Object.entries(categories).filter(([, v]) => v).map(([k]) => k);
    try {
      const { data } = await createResearch({
        query: trimmed,
        depth: Number(depth),
        breadth: Number(breadth),
        categories: cats,
      });
      const job = data.research || data.data || data;
      onJobCreated(job._id || job.id, job);
      setQuery('');
    } catch (err) {
      setError(err.response?.data?.message || err.message || 'Failed to start research.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <>
      <textarea
        className="query-textarea"
        rows={3}
        placeholder="Enter any complex research question — e.g. 'Frontier AI agent architectures, reasoning & test-time compute scaling in 2026'… (Ctrl+Enter to launch)"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey) handleSubmit(); }}
        disabled={loading || disabled}
      />

      {error && <div className="auth-error-box">⚠ {error}</div>}

      <div className="query-divider" />

      <div className="options-bar">
        <div className="option-group">
          <span className="option-label">
            <Layers size={11} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
            DEPTH
          </span>
          <select className="styled-select" value={depth}
            onChange={(e) => setDepth(e.target.value)} disabled={loading || disabled}>
            <option value="quick">Standard · 1 iter</option>
            <option value="standard">Deep · 2 iters</option>
            <option value="deep">Comprehensive · 3 iters</option>
          </select>
        </div>

        <div className="option-group">
          <span className="option-label">BREADTH</span>
          <select className="styled-select" value={breadth}
            onChange={(e) => setBreadth(e.target.value)} disabled={loading || disabled}>
            <option value={3}>3 Vector Tracks</option>
            <option value={5}>5 Vector Tracks</option>
          </select>
        </div>

        <div className="option-group checkbox-group">
          <label className="check-item">
            <input type="checkbox" checked={categories.web} onChange={() => toggleCategory('web')} disabled={loading || disabled} />
            <Globe size={11} /> WEB
          </label>
          <label className="check-item">
            <input type="checkbox" checked={categories.academic} onChange={() => toggleCategory('academic')} disabled={loading || disabled} />
            <BookOpen size={11} /> ACADEMIC
          </label>
          <label className="check-item">
            <input type="checkbox" checked={categories.market} onChange={() => toggleCategory('market')} disabled={loading || disabled} />
            <TrendingUp size={11} /> MARKET
          </label>
        </div>

        <div className="options-spacer" />

        <button id="launch-research-btn" className="btn-primary" onClick={handleSubmit} disabled={loading || disabled}>
          {loading || disabled
            ? <><span className="spinner" style={{ width: 14, height: 14 }} /> {disabled ? 'RUNNING…' : 'LAUNCHING…'}</>
            : <><Play size={14} fill="currentColor" /> LAUNCH DEEP RESEARCH</>}
        </button>
      </div>
    </>
  );
}
