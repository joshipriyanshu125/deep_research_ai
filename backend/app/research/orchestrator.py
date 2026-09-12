import asyncio
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime, timezone
from app.database.models.research import ResearchJob, ResearchStatus, ResearchTask
from app.database.models.report import ResearchReport
from app.database.models.source import Source
from app.database.repositories.research_repo import research_repo
from app.database.repositories.report_repo import report_repo
from app.research.planner import research_planner
from app.research.executor import research_executor
from app.research.evidence import evidence_extractor
from app.research.citation import citation_engine
from app.research.events import (
    RESEARCH_STARTED,
    PLAN_CREATED,
    SOURCE_PROCESSED,
    EVIDENCE_FOUND,
    FACT_CHECK_STARTED,
    REPORT_STARTED,
    REPORT_COMPLETED,
    RESEARCH_FAILED,
    research_event_bus,
)
from app.rag.retriever import rag_retriever
from app.agents.analyst import analyst_agent
from app.agents.fact_checker import fact_checker_agent
from app.agents.synthesizer import synthesizer_agent
from app.research.quality_scorer import research_quality_scorer
from app.research.stopping_criteria import research_stopping_criteria
from app.research.agent_orchestrator import research_agent_orchestrator, AgentRole
from app.utils.logger import logger


class ResearchOrchestrator:
    async def run_pipeline_stream(self, job: ResearchJob) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            research_event_bus.emit(
                RESEARCH_STARTED,
                job_id=job.id,
                message="Planning research...",
                data={"query": job.query, "depth": job.depth, "breadth": job.breadth},
            )
            job.status = ResearchStatus.PLANNING
            job.progress_percentage = 10
            job.current_step = "Decomposing research objective and constructing hypothesis plan..."
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}

            # 1. Planning Phase. Persisted tasks are reused after a worker restart.
            tasks = job.tasks or await research_planner.create_plan(job.query, depth=job.depth, breadth=job.breadth)
            job.tasks = tasks
            job.checkpoint_phase = "planned"
            job.checkpoint_data["task_ids"] = [t.id for t in tasks]
            job.progress_percentage = 25
            job.current_step = f"Generated {len(tasks)} parallel exploration vectors across Web, Academic, and Market."
            await research_repo.update_job(job)
            research_event_bus.emit(
                PLAN_CREATED,
                job_id=job.id,
                message="Planning research...",
                data={"tasks": [t.model_dump(mode="json") for t in tasks]},
            )
            yield {"event": "plan_ready", "data": {"tasks": [t.model_dump(mode="json") for t in tasks]}}

            # 2. Execution Phase
            job.status = ResearchStatus.SEARCHING
            job.checkpoint_phase = "searching"
            job.progress_percentage = 40
            job.current_step = f"Executing {len(tasks)} parallel exploration vectors across Web, Papers, and Market..."
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}

            async def _on_task_finished(task_obj: ResearchTask, task_sources: List[Source]):
                for s in task_sources:
                    await research_repo.add_source(s)
                    if s.id not in job.source_ids:
                        job.source_ids.append(s.id)
                    research_event_bus.emit(
                        SOURCE_PROCESSED,
                        job_id=job.id,
                        message=f"Processing source: {s.title or s.url or 'source'}",
                        data={"source": s.model_dump(mode="json") if hasattr(s, "model_dump") else s.__dict__},
                    )

            existing_sources = await research_repo.get_sources_by_research(job.id)
            sources = existing_sources + await research_executor.execute_tasks(
                tasks=tasks,
                research_id=job.id,
                on_task_complete=_on_task_finished,
            )
            unique_sources = {}
            for source in sources:
                unique_sources[source.id] = source
            sources = list(unique_sources.values())
            job.source_ids = [source.id for source in sources]
            job.checkpoint_data["source_ids"] = job.source_ids
            await research_repo.update_job(job)

            job.progress_percentage = 60
            job.current_step = f"Retrieved and validated {len(sources)} authoritative sources across parallel tracks."
            await research_repo.update_job(job)
            yield {
                "event": "sources_collected",
                "data": {
                    "sources": [s.model_dump(mode="json") for s in sources],
                    "execution_stats": research_executor.last_execution_stats,
                }
            }

            # 3. Knowledge / RAG Indexing & Evidence Extraction
            job.status = ResearchStatus.EXTRACTING
            job.checkpoint_phase = "extracting"
            job.progress_percentage = 70
            job.current_step = "Indexing RAG knowledge vectors and harvesting atomic evidence..."
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}

            await rag_retriever.index_sources([s.model_dump() for s in sources])

            all_evidence = await research_repo.get_evidence_by_research(job.id)
            existing_evidence_source_ids = {e.source_id for e in all_evidence}
            for s in sources:
                if s.id in existing_evidence_source_ids:
                    continue
                evs = evidence_extractor.extract_evidence(s, job.id)
                for ev in evs:
                    await research_repo.add_evidence(ev)
                    if ev.id not in job.evidence_ids:
                        job.evidence_ids.append(ev.id)
                    all_evidence.append(ev)
                    research_event_bus.emit(
                        EVIDENCE_FOUND,
                        job_id=job.id,
                        message=f"Evidence found in source: {s.title or s.url or 'source'}",
                        data={"evidence": ev.model_dump(mode="json") if hasattr(ev, "model_dump") else ev.__dict__},
                    )

            # 4. Fact Verification & Epistemic Audit
            job.status = ResearchStatus.ANALYZING
            job.checkpoint_phase = "analyzing"
            job.progress_percentage = 80
            job.current_step = "Conducting epistemic cross-examination & fact verification across source claims..."
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}
            research_event_bus.emit(
                FACT_CHECK_STARTED,
                job_id=job.id,
                message="Fact checking...",
                data={"evidence_count": len(all_evidence)},
            )

            verified_evidence = await fact_checker_agent.verify_evidence(all_evidence, sources=sources)
            fact_check_results = await fact_checker_agent.fact_check_batch(
                claims=verified_evidence,
                evidence_pool=all_evidence,
                sources=sources,
            )
            yield {
                "event": "fact_checks_ready",
                "data": {
                    "fact_checks": [fc.to_dict() for fc in fact_check_results],
                    "verified_count": len([fc for fc in fact_check_results if fc.supported]),
                }
            }

            analysis_result = await analyst_agent.analyze_findings(verified_evidence)
            yield {"event": "analysis_ready", "data": analysis_result}

            # 5. Citation Generation & Multi-Dimensional Synthesis
            job.status = ResearchStatus.SYNTHESIZING
            job.checkpoint_phase = "synthesizing"
            job.progress_percentage = 90
            job.current_step = "Synthesizing multi-section publication report across all findings, trends, and risks..."
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}
            research_event_bus.emit(
                REPORT_STARTED,
                job_id=job.id,
                message="Writing report...",
                data={"source_count": len(sources), "evidence_count": len(all_evidence)},
            )

            citations = citation_engine.build_citations(sources, verified_evidence)
            previous_context = {
                "query": job.query,
                "depth": job.depth,
                "breadth": job.breadth,
                "categories": job.categories,
                "task_count": len(tasks),
                "checkpoint": job.checkpoint_data,
                "parent_research_id": job.parent_research_id,
            }

            report: ResearchReport = await synthesizer_agent.synthesize_report(
                query=job.query,
                sources=sources,
                evidence=verified_evidence,
                citations=citations,
                task_results=tasks,
                previous_context=previous_context,
                fact_checks=fact_check_results,
            )
            report.research_id = job.id
            await report_repo.create(report)

            # 6. Quality Scoring (Day 50)
            quality = research_quality_scorer.score(
                sources=sources,
                evidence=all_evidence,
                tasks=tasks,
                citations=citations,
                fact_checks=fact_check_results,
                report=report,
            )
            quality_dict = quality.to_dict()
            logger.info(
                f"[QualityScorer] {quality.format_report()}"
            )

            # Stopping criteria evaluation (Day 49) — logged for transparency
            stopping = research_stopping_criteria.evaluate(
                tasks=tasks,
                evidence=all_evidence,
                sources=sources,
                confidence_score=report.confidence,
                fact_checks=fact_check_results,
                adaptive_round=0,
            )
            logger.info(f"[StoppingCriteria] {research_stopping_criteria.summary_line(stopping)}")

            # Orchestrator pipeline summary (Day 46)
            pipeline_summary = research_agent_orchestrator.get_pipeline_summary(job.id)

            # 7. Completion
            job.report_id = report.id
            job.status = ResearchStatus.COMPLETED
            job.checkpoint_phase = "completed"
            job.progress_percentage = 100
            job.current_step = "Research successfully completed."
            job.completed_at = datetime.now(timezone.utc)
            await research_repo.update_job(job)
            research_event_bus.emit(
                REPORT_COMPLETED,
                job_id=job.id,
                message="Report completed.",
                data={
                    "report_id": report.id,
                    "report": report.model_dump(mode="json"),
                    "quality_score": quality_dict,
                    "stopping_criteria": stopping.to_dict(),
                    "pipeline_summary": pipeline_summary,
                },
            )

            yield {
                "event": "report_ready",
                "data": {
                    "job": job.model_dump(mode="json"),
                    "report": report.model_dump(mode="json"),
                    "quality_score": quality_dict,
                }
            }
        except Exception as exc:
            logger.exception(f"Research pipeline failed for job {job.id}: {exc}")
            job.status = ResearchStatus.FAILED
            job.error_message = str(exc)
            job.current_step = "Research failed."
            job.completed_at = datetime.now(timezone.utc)
            try:
                await research_repo.update_job(job)
            except Exception:
                pass
            research_event_bus.emit(
                RESEARCH_FAILED,
                job_id=job.id,
                message="Research failed.",
                data={"error": str(exc), "job": job.model_dump(mode="json")},
            )
            yield {"event": "research_failed", "data": {"error": str(exc), "job": job.model_dump(mode="json")}}
            raise


research_orchestrator = ResearchOrchestrator()
