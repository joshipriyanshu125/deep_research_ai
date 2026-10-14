import { Globe, ShieldCheck, Search, Cpu, AlertTriangle, Square } from 'lucide-react';
import TaskTrackList from './TaskTrackList';
import SourcesList from './SourcesList';

function getProgress(job) {
  if (!job) return 10;
  if (typeof job.progress === 'number' && Number.isFinite(job.progress)) return Math.max(0, Math.min(100, job.progress));
  const s = job.status?.toLowerCase();
  if (s === 'queued' || s === 'pending') return 5;
  if (s === 'planning') return 15;
  if (s === 'searching') return 40;
  if (s === 'collecting' || s === 'extracting') return 65;
  if (s === 'analyzing') return 80;
  if (s === 'verifying' || s === 'synthesizing') return 90;
  if (s === 'processing' || s === 'running' || s === 'in_progress') return 45;
  if (s === 'completed' || s === 'done') return 100;
  return 0;
}

function getStepText(job) {
  if (!job) return 'Decomposing research query…';
  if (job.currentStep || job.current_step) return job.currentStep || job.current_step;
  const s = job.status?.toLowerCase();
  if (s === 'queued' || s === 'pending') return 'JOB QUEUED · Waiting for worker node…';
  if (s === 'planning') return 'PLANNER ACTIVE · Decomposing research query…';
  if (s === 'searching') return 'SEARCH ACTIVE · Gathering market intelligence and live web sources…';
  if (s === 'collecting' || s === 'extracting') return 'EXTRACTION ACTIVE · Gathering source-grounded evidence…';
  if (s === 'analyzing') return 'ANALYSIS ACTIVE · Comparing evidence and claims…';
  if (s === 'verifying') return 'FACT CHECK ACTIVE · Cross-checking claims…';
  if (s === 'synthesizing') return 'SYNTHESIS ACTIVE · Writing the grounded report…';
  if (s === 'processing' || s === 'running' || s === 'in_progress') return 'AGENT SYSTEM ACTIVE · Processing query vectors…';
  if (s === 'completed' || s === 'done') return 'RESEARCH COMPLETE ✓';
  if (s === 'failed') return 'ERROR · Research failed.';
  if (s === 'cancelled') return 'RESEARCH STOPPED · No further work is running.';
  return 'INITIALIZING AGENT PIPELINE…';
}

export default function MissionControl({ job, jobId, onCancel, isCancelling }) {
  const progress = getProgress(job);
  const stepText = getStepText(job);
  const tasks = job?.tasks || job?.subTasks || job?.plan?.tasks || [];
  const sources = Array.isArray(job?.sources) ? job.sources : [];
  const sourceCount = sources.length || job?.sourceIds?.length || job?.source_ids?.length || 0;
  const evidenceCount = job?.evidence?.length
    || job?.evidenceIds?.length
    || job?.evidence_ids?.length
    || job?.analysis?.evidenceCount
    || 0;
  const factCheckCount = job?.factChecks?.length || 0;
  const citationCount = job?.citations?.length || 0;
  const verification = job?.verificationSummary || {};
  const gemini = verification.geminiIntegration || {};
  const providers = verification.providers || [];
  const status = job?.status?.toLowerCase();
  const canCancel = Boolean(onCancel)
    && !['completed', 'done', 'failed', 'cancelled'].includes(status);

  return (
    <>
      {/* Header */}
      <div className="mission-header">
        <div className="mission-title-group">
          <div className="pulse-ring" />
          <div>
            <div className="mission-step">{stepText}</div>
            <div className="job-id">JOB_ID: {jobId || '—'}</div>
          </div>
        </div>
        <div className="progress-group">
          <div className="progress-track">
            <div className="progress-fill" style={{ width: `${progress}%` }} />
          </div>
          <span className="progress-pct">{progress}%</span>
          {canCancel && (
            <button
              type="button"
              className="btn-cancel"
              onClick={onCancel}
              disabled={isCancelling}
              aria-label="Stop research"
            >
              <Square size={12} fill="currentColor" />
              {isCancelling ? 'CANCELLING…' : 'STOP RESEARCH'}
            </button>
          )}
        </div>
      </div>

      {/* Dashboard grid */}
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-title">// VECTOR TRACKS</span>
            <span className="badge">{status === 'cancelled' ? 'STOPPED' : `${tasks.length} ACTIVE`}</span>
          </div>
          <div className="card-body">
            <TaskTrackList tasks={tasks} status={status} />
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-title">// HARVESTED EVIDENCE</span>
            <span className="badge success">{sourceCount} SOURCES</span>
          </div>
          <div className="card-body">
            <SourcesList
              sources={sources}
              emptyMessage={['completed', 'done', 'failed', 'cancelled'].includes(status)
                ? 'No source records were returned for this run.'
                : undefined}
            />
          </div>
        </div>
      </div>

      {/* Pipeline telemetry strip */}
      <div className="pipeline-summary" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginTop: 12 }}>
        {[
          ['PLAN', tasks.length],
           ['SOURCES', sourceCount],
          ['EVIDENCE', evidenceCount],
          ['FACT CHECKS', factCheckCount],
          ['CITATIONS', citationCount],
        ].map(([label, value]) => (
          <span className="badge" key={label}>{label}: {value}</span>
        ))}

        {/* Live web status */}
        <span className={`badge ${verification.liveWebResearch ? 'success' : 'amber'}`}>
          {verification.liveWebResearch
            ? <><Globe size={11} /> LIVE WEB: CONFIRMED</>
            : <><AlertTriangle size={11} /> LIVE WEB: NOT CONFIRMED</>
          }
        </span>

        {/* Gemini integration status */}
        <span className={`badge ${gemini.active ? 'success' : 'amber'}`}>
          {gemini.active
            ? <><Cpu size={11} /> GEMINI: ACTIVE {gemini.model ? `(${gemini.model})` : ''}</>
            : <><AlertTriangle size={11} /> GEMINI: NOT DETECTED</>
          }
        </span>

        {/* Fact-check status */}
        <span className={`badge ${(verification.independentVerification) ? 'success' : 'amber'}`}>
          {verification.independentVerification
            ? <><ShieldCheck size={11} /> CHECKS: {verification.verifiedClaims || 0}/{verification.attemptedClaims || 0} VERIFIED</>
            : <><AlertTriangle size={11} /> CHECKS: PENDING</>
          }
        </span>

        {/* Search providers */}
        {providers.length > 0 && (
          <span className="badge success">
            <Search size={11} /> {providers.join(', ').toUpperCase()}
          </span>
        )}
      </div>
    </>
  );
}
