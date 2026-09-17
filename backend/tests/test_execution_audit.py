"""Regression coverage for the API-visible research execution audit."""

from app.database.models.research import ResearchJob
from app.research.orchestrator import research_orchestrator


def test_depth_two_audit_exposes_two_real_pipeline_iterations():
    job = ResearchJob(query="Indian EV market", depth=2, breadth=3)

    research_orchestrator._start_execution_audit(job)
    research_orchestrator._record_iteration(job, 1, "completed", evidence_count=8)
    research_orchestrator._record_iteration(job, 2, "completed", verified_count=6)
    research_orchestrator._record_stage(job, "evidence_engine", "completed", evidence_count=8)
    research_orchestrator._record_stage(job, "verification", "completed", passes=1, verified_count=6)
    research_orchestrator._record_stage(job, "contradiction_engine", "completed", finding_count=0, findings=[])
    research_orchestrator._record_stage(job, "analysis", "completed", key_pattern_count=3)
    research_orchestrator._record_stage(job, "writer", "completed", report_id="report-1")

    audit = job.model_dump(mode="json")["execution_summary"]
    assert audit["requested_depth"] == 2
    assert [item["status"] for item in audit["iterations"]] == ["completed", "completed"]
    assert audit["stages"]["evidence_engine"]["evidence_count"] == 8
    assert audit["stages"]["verification"]["passes"] == 1
    assert audit["stages"]["contradiction_engine"]["status"] == "completed"
    assert audit["stages"]["analysis"]["status"] == "completed"
    assert audit["stages"]["writer"]["report_id"] == "report-1"
    # Old checkpoint-only clients receive the same audit structure.
    assert job.checkpoint_data["execution_summary"] == audit
