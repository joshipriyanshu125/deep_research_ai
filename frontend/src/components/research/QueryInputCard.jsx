import { useState } from 'react';
import { Play, Layers, Globe, BookOpen, TrendingUp, Zap, Brain } from 'lucide-react';
import { createResearch } from '../../api/research';
import { quickAnswer } from '../../api/research';
import { getErrorMessage } from '../../api/errorMessage';

/**
 * QueryInputCard
 *
 * Two-mode submission:
 *  • Quick Answer  → POST /api/v1/quick-answer (Gemini direct)
 *  • Deep Research → POST /api/v1/research      (full pipeline)
 *
 * Props:
 *   onJobCreated(jobId, job)      — called after a deep-research job is enqueued
 *   onQuickAnswer({ answer, query, model }) — called after a quick answer is returned
 *   disabled                      — disable inputs while pipeline is running
 */
export default function QueryInputCard({ onJobCreated, onQuickAnswer, disabled }) {
  const [query, setQuery] = useState('');
  const [mode, setMode] = useState('auto'); // 'auto' | 'quick' | 'deep'
  const [depth, setDepth] = useState('standard');
  const [breadth, setBreadth] = useState(3);
  const [categories, setCategories] = useState({ web: true, academic: true, market: true });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const toggleCategory = (key) =>
    setCategories((prev) => ({ ...prev, [key]: !prev[key] }));

  const handleSubmit = async (requestedMode = mode) => {
    if (loading || disabled) return;
    const trimmed = query.trim();
    if (!trimmed) { setError('Please enter a question or research query.'); return; }
    setError('');
    setLoading(true);

    // Button wrappers pass an explicit mode; keyboard submission uses the
    // selected mode from state. This keeps click events out of the mode value.
    const submissionMode = ['auto', 'quick', 'deep'].includes(requestedMode)
      ? requestedMode
      : mode;

    try {
      // Quick-only or Auto mode → try quick-answer router first
      if (submissionMode === 'quick' || submissionMode === 'auto') {
        const { data } = await quickAnswer(trimmed);

        if (data.mode === 'quick' && data.answer) {
          // Gemini answered directly
          if (onQuickAnswer) onQuickAnswer({ answer: data.answer, query: trimmed, model: data.model });
          setQuery('');
          return;
        }

        // Router said "deep" — fall through only if mode is 'auto'
        if (submissionMode === 'quick') {
          // User explicitly chose Quick but it fell back to deep — inform them
          setError('This question requires deep research. Switching to Deep Research mode…');
          // Still proceed to deep pipeline below
        }
      }

      // Deep Research pipeline
      const cats = Object.entries(categories).filter(([, v]) => v).map(([k]) => k);
      const { data } = await createResearch({
        query: trimmed,
        // The API contract uses a numeric planner depth. Keep the UI labels
        // (quick/standard/deep) separate from the wire format so older
        // deployed backends cannot reject a valid submission with 422.
        depth: { quick: 1, standard: 2, deep: 3 }[depth] || 2,
        research_mode: depth,
        breadth: Number(breadth),
        categories: cats,
      });
      const job = data?.research || data?.data || data;
      const jobId = job?._id || job?.id;
      if (!jobId) {
        setError('Research submission did not return a job id.');
        return;
      }
      if (onJobCreated) onJobCreated(jobId, job);
      setQuery('');
    } catch (err) {
      setError(getErrorMessage(err, 'Failed to submit.'));
    } finally {
      setLoading(false);
    }
  };

  const isDeepMode = mode === 'deep';
  const isQuickMode = mode === 'quick';
  const isAutoMode = mode === 'auto';

  return (
    <>
      {/* ── Mode Toggle ── */}
      <div className="mode-toggle-bar" role="group" aria-label="Research mode">
        <button
          id="mode-auto-btn"
          className={`mode-btn ${isAutoMode ? 'mode-btn--active' : ''}`}
          onClick={() => setMode('auto')}
          disabled={loading || disabled}
          title="Auto-detect: simple questions get a direct Gemini answer; complex ones use the full pipeline"
        >
          <Brain size={12} />
          AUTO
        </button>
        <button
          id="mode-quick-btn"
          className={`mode-btn ${isQuickMode ? 'mode-btn--active mode-btn--quick' : ''}`}
          onClick={() => setMode('quick')}
          disabled={loading || disabled}
          title="Quick Answer: direct Gemini response, no pipeline"
        >
          <Zap size={12} />
          QUICK ANSWER
        </button>
        <button
          id="mode-deep-btn"
          className={`mode-btn ${isDeepMode ? 'mode-btn--active mode-btn--deep' : ''}`}
          onClick={() => setMode('deep')}
          disabled={loading || disabled}
          title="Deep Research: full multi-agent pipeline with sources and report"
        >
          <Play size={12} />
          DEEP RESEARCH
        </button>
      </div>

      {/* ── Mode hint ── */}
      <div className="mode-hint">
        {isAutoMode && 'Auto mode: simple questions → direct answer · complex queries → full pipeline'}
        {isQuickMode && 'Quick Answer: Gemini answers directly — instant, no sources generated'}
        {isDeepMode && 'Deep Research: multi-agent pipeline — planner → search → fact-check → report'}
      </div>

      {/* ── Textarea ── */}
      <textarea
        className="query-textarea"
        rows={3}
        placeholder={
          isQuickMode
            ? 'Ask a quick question — e.g. "What is quantum computing?" (Ctrl+Enter)'
            : isDeepMode
            ? 'Enter a complex research query — e.g. "Analyze the Indian EV market…" (Ctrl+Enter)'
            : 'Ask anything — simple questions get instant answers, complex ones launch full research… (Ctrl+Enter)'
        }
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && e.ctrlKey) handleSubmit(); }}
        disabled={loading || disabled}
      />

      {error && <div className="auth-error-box">⚠ {error}</div>}

      <div className="query-divider" />

      {/* ── Options (only relevant in deep / auto mode) ── */}
      {!isQuickMode && (
        <div className="options-bar">
          <div className="option-group">
            <span className="option-label">
              <Layers size={11} style={{ display: 'inline', marginRight: 4, verticalAlign: 'middle' }} />
              DEPTH
            </span>
            <select className="styled-select" value={depth}
              onChange={(e) => setDepth(e.target.value)} disabled={loading || disabled}>
              <option value="quick">Quick</option>
              <option value="standard">Standard</option>
              <option value="deep">Comprehensive</option>
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
            <label className="check-item">
              <input type="checkbox" checked={!!categories.other} onChange={() => toggleCategory('other')} disabled={loading || disabled} />
              <Globe size={11} /> OTHER
            </label>
          </div>

          <div className="options-spacer" />

          <button id="launch-research-btn" className="btn-primary" onClick={() => handleSubmit('deep')} disabled={loading || disabled}>
            {loading || disabled
              ? <><span className="spinner" style={{ width: 14, height: 14 }} /> {disabled ? 'RUNNING…' : 'LAUNCHING…'}</>
              : <><Play size={14} fill="currentColor" /> LAUNCH DEEP RESEARCH</>}
          </button>
        </div>
      )}

      {/* ── Quick-mode submit bar ── */}
      {isQuickMode && (
        <div className="options-bar">
          <div className="options-spacer" />
          <button id="quick-answer-btn" className="btn-quick" onClick={() => handleSubmit('quick')} disabled={loading || disabled}>
            {loading
              ? <><span className="spinner" style={{ width: 14, height: 14 }} /> THINKING…</>
              : <><Zap size={14} fill="currentColor" /> GET QUICK ANSWER</>}
          </button>
        </div>
      )}

      {/* ── Auto-mode submit bar ── */}
      {isAutoMode && (
        <div className="options-bar">
          <div className="options-spacer" />
          <button id="auto-submit-btn" className="btn-primary" onClick={() => handleSubmit('auto')} disabled={loading || disabled}>
            {loading || disabled
              ? <><span className="spinner" style={{ width: 14, height: 14 }} /> {disabled ? 'RUNNING…' : 'ROUTING…'}</>
              : <><Brain size={14} /> SMART SUBMIT</>}
          </button>
        </div>
      )}
    </>
  );
}
