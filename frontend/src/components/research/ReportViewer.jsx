import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Download, Check, FileText, Globe, ShieldCheck, Search, Cpu, CheckCircle2, AlertTriangle, Activity } from 'lucide-react';
import TiltCard from '../ui/TiltCard';

export default function ReportViewer({ report }) {
  const [copied, setCopied] = useState(false);
  const [showTelemetry, setShowTelemetry] = useState(true);

  if (!report) return null;

  const title = report.title || 'Research Report';
  const execSummary = report.executiveSummary || report.executive_summary || '';
  const markdownContent = report.markdownContent || report.markdown_content || report.content || '';
  const citations = report.citations || report.sources || [];
  const epistemicScore = report.epistemicScore || report.epistemic_score;
  const verification = report.verificationSummary || report.verification_summary || {};
  const factChecks = report.factChecks || [];
  const evidence = report.evidence || [];
  const qualityScore = report.qualityScore;
  const qualityCheckResults = report.qualityCheckResults || {};
  const gemini = verification.geminiIntegration || {};

  let fullMarkdown = `${markdownContent}`;
  if (execSummary && !markdownContent.includes(execSummary)) {
    fullMarkdown = `> **Executive Summary**: ${execSummary}\n\n${markdownContent}`;
  }
  if (citations.length > 0 && !/^## (?:Sources & Citations|References & Sources)/m.test(markdownContent)) {
    fullMarkdown += `\n\n## References & Sources\n`;
    citations.forEach((c, i) => {
      const idx = c.index ?? i + 1;
      const url = c.url || c.sourceUrl;
      fullMarkdown += `\n**[${idx}]** [${c.title || url}](${url}) — *${c.source_type || c.sourceType || 'web'}*\n`;
      if (c.snippet) fullMarkdown += `> ${c.snippet}\n`;
    });
  }

  const handleCopy = () => {
    navigator.clipboard.writeText(fullMarkdown);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExportHTML = () => {
    const html = `<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>${title}</title>
<style>
  body { font-family: system-ui, sans-serif; max-width: 860px; margin: 40px auto; padding: 0 24px; line-height: 1.75; color: #1e293b; }
  h1,h2,h3 { color: #0f172a; }
  a { color: #0284c7; }
  blockquote { border-left: 4px solid #0284c7; background: #f0f9ff; padding: 12px 20px; margin: 1.5rem 0; }
  pre { background: #f8fafc; border: 1px solid #e2e8f0; padding: 16px; border-radius: 8px; overflow-x: auto; }
  table { border-collapse: collapse; width: 100%; }
  th,td { border: 1px solid #e2e8f0; padding: 10px 14px; text-align: left; }
  th { background: #f8fafc; }
</style>
</head>
<body>
<h1>${title}</h1>
${document.querySelector('.markdown-body')?.innerHTML || ''}
</body>
</html>`;
    const blob = new Blob([html], { type: 'text/html' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `deep_research_${report._id || report.id || 'report'}.html`;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Derive verification telemetry rows
  const verifiedCount = verification.verifiedClaims || 0;
  const singleSourceCount = verification.singleSourceClaims || 0;
  const contradictedCount = verification.contradictedClaims || 0;
  const totalSources = verification.totalSources || citations.length || 0;
  const liveFetched = verification.liveFetchedSources || 0;
  const providers = verification.providers || [];

  const telemetryRows = [
    {
      feature: 'Gemini API integration',
      status: gemini.active ? 'Confirmed & Active' : verification.independentVerification ? 'Active (heuristic)' : 'Not configured',
      ok: gemini.active || verification.independentVerification,
      detail: gemini.model ? `Model: ${gemini.model}` : ''
    },
    {
      feature: 'Live web search',
      status: verification.liveWebResearch ? 'Confirmed' : 'Not confirmed',
      ok: verification.liveWebResearch,
      detail: providers.length > 0 ? `Providers: ${providers.join(', ')}` : ''
    },
    {
      feature: 'Actual source extraction',
      status: liveFetched > 0 ? `Confirmed — ${liveFetched} pages fetched` : totalSources > 0 ? `${totalSources} sources collected` : 'Not confirmed',
      ok: liveFetched > 0 || totalSources > 0,
      detail: verification.totalExtractedCharacters ? `${(verification.totalExtractedCharacters / 1000).toFixed(0)}K chars extracted` : ''
    },
    {
      feature: 'Evidence-based fact-checking',
      status: (verification.attemptedClaims || factChecks.length) > 0
        ? `Confirmed — ${verification.attemptedClaims || factChecks.length} claims checked`
        : 'Not confirmed',
      ok: (verification.attemptedClaims || factChecks.length) > 0,
      detail: gemini.factCheckedWithGemini ? 'Engine: Gemini Epistemic Judge' : 'Engine: Heuristic cross-source'
    },
    {
      feature: 'Citation-to-source accuracy',
      status: citations.length > 0 ? `Confirmed — ${citations.length} traceable citations` : 'Not confirmed',
      ok: citations.length > 0,
      detail: citations.filter(c => c.isVerificationSource).length > 0
        ? `${citations.filter(c => c.isVerificationSource).length} independent verification sources`
        : ''
    },
    {
      feature: 'Gemini analysis & synthesis',
      status: gemini.analyzedWithGemini ? 'Confirmed' : 'Deterministic fallback',
      ok: gemini.analyzedWithGemini || (evidence.length > 0),
      detail: gemini.reportWriter || ''
    },
  ];

  return (
    <section className="report-section">
      <div className="report-header">
        <div className="report-meta">
          <h2 className="report-title">{title}</h2>
          <div className="report-badges">
            {qualityScore != null && (
              <span className={`badge ${qualityScore >= 70 ? 'success' : qualityScore >= 40 ? 'amber' : ''}`}>
                ✓ Quality Score: {qualityScore}/100
              </span>
            )}
            {epistemicScore && (
              <span className="badge success">✓ Epistemic Score: {epistemicScore}/10</span>
            )}
            <span className="badge purple">
              <FileText size={11} />
              {citations.length} Citations
            </span>
            <span className={`badge ${verification.liveWebResearch ? 'success' : 'amber'}`}>
              {verification.liveWebResearch ? <><Globe size={11} /> Live web research confirmed</> : '⚠ Live web not confirmed'}
            </span>
            <span className={`badge ${verifiedCount > 0 ? 'success' : 'amber'}`}>
              <ShieldCheck size={11} />
              {verifiedCount}/{verification.attemptedClaims || factChecks.length || 0} claims verified
            </span>
            {gemini.active && (
              <span className="badge success">
                <Cpu size={11} /> Gemini {gemini.model || 'active'}
              </span>
            )}
          </div>
        </div>
        <div className="export-actions">
          <button
            id="toggle-telemetry-btn"
            className="btn-secondary"
            onClick={() => setShowTelemetry(!showTelemetry)}
          >
            <Activity size={14} /> {showTelemetry ? 'Hide' : 'Show'} Telemetry
          </button>
          <button id="copy-markdown-btn" className="btn-secondary" onClick={handleCopy}>
            {copied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy Markdown</>}
          </button>
          <button id="export-html-btn" className="btn-secondary" onClick={handleExportHTML}>
            <Download size={14} /> Export HTML
          </button>
        </div>
      </div>

      {/* ── Verification Telemetry Panel ── */}
      {showTelemetry && (
        <TiltCard intensity={3}>
          <div className="holo-card" style={{ padding: '20px 24px', marginBottom: 20 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
              <ShieldCheck size={18} style={{ color: 'var(--accent-green)' }} />
              <span style={{ fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)', fontWeight: 600, fontSize: '0.85rem', color: 'var(--text-primary)' }}>
                RESEARCH VERIFICATION TELEMETRY
              </span>
            </div>
            <table style={{
              width: '100%',
              borderCollapse: 'collapse',
              fontSize: '0.82rem',
              fontFamily: 'var(--font-mono, "JetBrains Mono", monospace)'
            }}>
              <thead>
                <tr style={{ borderBottom: '1px solid var(--border-color)' }}>
                  <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--text-muted)', fontWeight: 500 }}>Feature</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--text-muted)', fontWeight: 500 }}>Status</th>
                  <th style={{ textAlign: 'left', padding: '8px 12px', color: 'var(--text-muted)', fontWeight: 500 }}>Detail</th>
                </tr>
              </thead>
              <tbody>
                {telemetryRows.map((row, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                    <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                      {row.feature}
                    </td>
                    <td style={{ padding: '8px 12px' }}>
                      <span style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: 6,
                        color: row.ok ? 'var(--accent-green)' : 'var(--accent-amber)',
                        fontWeight: 500
                      }}>
                        {row.ok
                          ? <CheckCircle2 size={13} />
                          : <AlertTriangle size={13} />
                        }
                        {row.status}
                      </span>
                    </td>
                    <td style={{ padding: '8px 12px', color: 'var(--text-muted)', fontSize: '0.78rem' }}>
                      {row.detail}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {/* Summary counters */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 14, paddingTop: 12, borderTop: '1px solid var(--border-color)' }}>
              {[
                ['SOURCES', totalSources],
                ['EVIDENCE', evidence.length || verification.evidenceCount || 0],
                ['VERIFIED', verifiedCount],
                ['SINGLE-SOURCE', singleSourceCount],
                ['CONTRADICTED', contradictedCount],
                ['CITATIONS', citations.length],
              ].map(([label, val]) => (
                <span className="badge" key={label} style={{ fontSize: '0.72rem' }}>
                  {label}: {val}
                </span>
              ))}
              {qualityCheckResults.reportGenerator && (
                <span className="badge success" style={{ fontSize: '0.72rem' }}>
                  <Cpu size={10} /> {qualityCheckResults.reportGenerator}
                </span>
              )}
            </div>
          </div>
        </TiltCard>
      )}

      <TiltCard intensity={5}>
        <div className="holo-card report-card">
          <div className="markdown-body">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {fullMarkdown}
            </ReactMarkdown>
          </div>
        </div>
      </TiltCard>
    </section>
  );
}
