import { useState } from 'react';
import { Zap, ChevronDown, ChevronUp, Copy, CheckCheck, ArrowRight } from 'lucide-react';

/**
 * QuickAnswerViewer
 * Renders a Gemini Quick Answer with a premium card UI.
 * Props:
 *   answer       — string (markdown-ish text from Gemini)
 *   query        — string (the original question)
 *   model        — string (e.g. "gemini-1.5-flash")
 *   onUpgrade    — () => void — called when user clicks "Run Deep Research Instead"
 */
export default function QuickAnswerViewer({ answer, query, model, onUpgrade }) {
  const [collapsed, setCollapsed] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(answer);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (_) {}
  };

  // Render newlines + simple bold markdown (**text**)
  const renderAnswer = (text) => {
    return text
      .split('\n')
      .map((line, i) => {
        const parts = line.split(/\*\*(.+?)\*\*/g);
        return (
          <p key={i} style={{ margin: '0 0 0.45em', lineHeight: 1.7 }}>
            {parts.map((part, j) =>
              j % 2 === 1 ? <strong key={j}>{part}</strong> : part
            )}
          </p>
        );
      });
  };

  return (
    <div className="quick-answer-card" id="quick-answer-result">
      {/* Header */}
      <div className="qa-header">
        <div className="qa-badge">
          <Zap size={12} fill="currentColor" />
          QUICK ANSWER
        </div>

        <div className="qa-meta">
          <span className="qa-model-tag">{model}</span>
          <button
            className="qa-icon-btn"
            onClick={handleCopy}
            title="Copy answer"
            aria-label="Copy answer"
          >
            {copied ? <CheckCheck size={14} /> : <Copy size={14} />}
          </button>
          <button
            className="qa-icon-btn"
            onClick={() => setCollapsed((p) => !p)}
            title={collapsed ? 'Expand' : 'Collapse'}
            aria-label={collapsed ? 'Expand answer' : 'Collapse answer'}
          >
            {collapsed ? <ChevronDown size={14} /> : <ChevronUp size={14} />}
          </button>
        </div>
      </div>

      {/* Query echo */}
      <div className="qa-query">{query}</div>

      {/* Answer body */}
      {!collapsed && (
        <div className="qa-body">
          {renderAnswer(answer)}
        </div>
      )}

      {/* Footer — upgrade prompt */}
      <div className="qa-footer">
        <span className="qa-footer-hint">
          Need a comprehensive report with sources?
        </span>
        <button
          className="qa-upgrade-btn"
          onClick={onUpgrade}
          id="upgrade-to-deep-research-btn"
        >
          Run Deep Research Instead
          <ArrowRight size={13} />
        </button>
      </div>
    </div>
  );
}
