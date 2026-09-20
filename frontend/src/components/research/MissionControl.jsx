import TaskTrackList from './TaskTrackList';
import SourcesList from './SourcesList';

function getProgress(job) {
  if (!job) return 10;
  if (typeof job.progress === 'number') return job.progress;
  const s = job.status?.toLowerCase();
  if (s === 'queued') return 5;
  if (s === 'processing' || s === 'running') return 45;
  if (s === 'completed' || s === 'done') return 100;
  return 10;
}

function getStepText(job) {
  if (!job) return 'Decomposing research query…';
  if (job.currentStep) return job.currentStep;
  const s = job.status?.toLowerCase();
  if (s === 'queued') return 'JOB QUEUED · Waiting for worker node…';
  if (s === 'processing' || s === 'running') return 'AGENT SYSTEM ACTIVE · Processing query vectors…';
  if (s === 'completed' || s === 'done') return 'RESEARCH COMPLETE ✓';
  if (s === 'failed') return 'ERROR · Research failed.';
  return 'INITIALIZING AGENT PIPELINE…';
}

export default function MissionControl({ job, jobId }) {
  const progress = getProgress(job);
  const stepText = getStepText(job);
  const tasks = job?.tasks || job?.subTasks || job?.plan?.tasks || [];
  const sources = job?.sources || job?.evidence || [];

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
        </div>
      </div>

      {/* Dashboard grid */}
      <div className="dashboard-grid">
        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-title">// VECTOR TRACKS</span>
            <span className="badge">{tasks.length} ACTIVE</span>
          </div>
          <div className="card-body">
            <TaskTrackList tasks={tasks} />
          </div>
        </div>

        <div className="dashboard-card">
          <div className="card-header">
            <span className="card-title">// HARVESTED EVIDENCE</span>
            <span className="badge success">{sources.length} SOURCES</span>
          </div>
          <div className="card-body">
            <SourcesList sources={sources} />
          </div>
        </div>
      </div>
    </>
  );
}
