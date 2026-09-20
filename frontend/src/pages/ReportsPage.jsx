import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { getAllReports, deleteReport } from '../api/research';
import Sidebar from '../components/layout/Sidebar';
import ReportViewer from '../components/research/ReportViewer';
import TiltCard from '../components/ui/TiltCard';
import { FileText, Search, Download, Trash2, ExternalLink, Sparkles, BookOpen, Clock, AlertCircle } from 'lucide-react';

export default function ReportsPage() {
  const navigate = useNavigate();
  const [reports, setReports] = useState([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selectedReport, setSelectedReport] = useState(null);
  const [error, setError] = useState('');

  const loadReports = async () => {
    setLoading(true);
    setError('');
    try {
      const { data } = await getAllReports();
      const list = Array.isArray(data) ? data : data.reports || data.data || [];
      setReports(list);
      if (list.length > 0 && !selectedReport) {
        setSelectedReport(list[0]);
      }
    } catch (err) {
      setError(err.response?.data?.message || 'Failed to load reports archive.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadReports();
  }, []);

  const handleDelete = async (id, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this research report?')) return;
    try {
      await deleteReport(id);
      setReports((prev) => prev.filter((r) => (r._id || r.id) !== id));
      if (selectedReport && (selectedReport._id || selectedReport.id) === id) {
        setSelectedReport(reports.find((r) => (r._id || r.id) !== id) || null);
      }
    } catch (err) {
      alert('Could not delete report: ' + (err.response?.data?.message || err.message));
    }
  };

  const filteredReports = reports.filter((r) => {
    const term = search.toLowerCase();
    const title = (r.title || '').toLowerCase();
    const summary = (r.summary || r.executiveSummary || '').toLowerCase();
    return title.includes(term) || summary.includes(term);
  });

  return (
    <div className="app-layout">
      <Sidebar />

      <main className="main-content">
        {/* Header */}
        <section className="hero-section">
          <div className="hero-eyebrow">Intelligence Archive</div>
          <h1 className="hero-title" data-text="Synthesized Research Reports">
            Synthesized Research Reports
          </h1>
          <p className="hero-subtitle">
            Permanent repository of all verified epistemic intelligence dossiers, citations, and structured findings.
          </p>
        </section>

        {/* Toolbar */}
        <div className="reports-toolbar">
          <div className="search-box">
            <Search size={16} className="search-icon" />
            <input
              type="text"
              className="search-input"
              placeholder="Filter reports by query, title, or keywords…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button className="btn-primary" onClick={() => navigate('/dashboard')}>
            <Sparkles size={14} /> NEW RESEARCH
          </button>
        </div>

        {error && <div className="auth-error-box">⚠ {error}</div>}

        {loading ? (
          <div className="loading-state" style={{ padding: '60px 0', textAlign: 'center' }}>
            <span className="spinner" style={{ width: 28, height: 28 }} />
            <div style={{ marginTop: 12 }}>Loading verified reports archive…</div>
          </div>
        ) : filteredReports.length === 0 ? (
          <div className="empty-state-card holo-card">
            <BookOpen size={48} style={{ opacity: 0.3, marginBottom: 16 }} />
            <h3>No Research Reports Found</h3>
            <p style={{ color: 'var(--text-secondary)', maxWidth: 460, margin: '8px auto 20px' }}>
              {search ? 'No reports matched your search query.' : 'Run your first autonomous research mission from the Mission Station to generate intelligence reports.'}
            </p>
            <button className="btn-primary" onClick={() => navigate('/dashboard')}>
              Launch Mission Station
            </button>
          </div>
        ) : (
          <div className="reports-layout-grid">
            {/* Reports List */}
            <div className="reports-list-column">
              <div className="reports-column-header">
                <span>REPORTS ({filteredReports.length})</span>
              </div>
              <div className="reports-cards-scroll">
                {filteredReports.map((report) => {
                  const id = report._id || report.id;
                  const isSelected = selectedReport && (selectedReport._id || selectedReport.id) === id;
                  const date = report.createdAt ? new Date(report.createdAt).toLocaleDateString() : 'Recent';
                  const citationsCount = report.citations?.length || 0;

                  return (
                    <div
                      key={id}
                      className={`report-item-card holo-card ${isSelected ? 'active' : ''}`}
                      onClick={() => setSelectedReport(report)}
                    >
                      <div className="report-item-top">
                        <span className="badge success">PUBLISHED</span>
                        <span className="report-date">
                          <Clock size={11} /> {date}
                        </span>
                      </div>
                      <h4 className="report-item-title">{report.title || 'Untitled Report'}</h4>
                      <p className="report-item-summary">
                        {report.summary || report.executiveSummary || report.content?.slice(0, 120) + '…'}
                      </p>
                      <div className="report-item-footer">
                        <span className="badge purple">
                          <FileText size={10} /> {citationsCount} Citations
                        </span>
                        <button
                          className="icon-btn-delete"
                          onClick={(e) => handleDelete(id, e)}
                          title="Delete Report"
                        >
                          <Trash2 size={13} />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Selected Report Viewer */}
            <div className="report-viewer-column">
              {selectedReport ? (
                <ReportViewer report={selectedReport} />
              ) : (
                <div className="holo-card empty-viewer-placeholder">
                  Select a report from the list to view full analysis.
                </div>
              )}
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
