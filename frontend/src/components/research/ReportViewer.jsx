import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { Copy, Download, Check, FileText } from 'lucide-react';
import TiltCard from '../ui/TiltCard';

export default function ReportViewer({ report }) {
  const [copied, setCopied] = useState(false);

  if (!report) return null;

  const title = report.title || 'Research Report';
  const execSummary = report.executiveSummary || report.executive_summary || '';
  const markdownContent = report.markdownContent || report.markdown_content || report.content || '';
  const citations = report.citations || report.sources || [];
  const epistemicScore = report.epistemicScore || report.epistemic_score;

  let fullMarkdown = `${markdownContent}`;
  if (execSummary && !markdownContent.includes(execSummary)) {
    fullMarkdown = `> **Executive Summary**: ${execSummary}\n\n${markdownContent}`;
  }
  if (citations.length > 0) {
    fullMarkdown += `\n\n## References & Sources\n`;
    citations.forEach((c, i) => {
      const idx = c.index ?? i + 1;
      fullMarkdown += `\n**[${idx}]** [${c.title || c.url}](${c.url}) — *${c.source_type || c.sourceType || 'web'}*\n`;
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

  return (
    <section className="report-section">
      <div className="report-header">
        <div className="report-meta">
          <h2 className="report-title">{title}</h2>
          <div className="report-badges">
            {epistemicScore && (
              <span className="badge success">✓ Epistemic Score: {epistemicScore}/10</span>
            )}
            <span className="badge purple">
              <FileText size={11} />
              {citations.length} Citations
            </span>
          </div>
        </div>
        <div className="export-actions">
          <button id="copy-markdown-btn" className="btn-secondary" onClick={handleCopy}>
            {copied ? <><Check size={14} /> Copied!</> : <><Copy size={14} /> Copy Markdown</>}
          </button>
          <button id="export-html-btn" className="btn-secondary" onClick={handleExportHTML}>
            <Download size={14} /> Export HTML
          </button>
        </div>
      </div>

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
