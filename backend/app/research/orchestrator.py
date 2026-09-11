import asyncio
from typing import AsyncGenerator, Dict, Any, List
from datetime import datetime, timezone
from app.database.models.research import ResearchJob, ResearchStatus
from app.database.models.report import ResearchReport
from app.database.repositories.research_repo import research_repo
from app.database.repositories.report_repo import report_repo
from app.research.planner import research_planner
from app.research.executor import research_executor
from app.research.evidence import evidence_extractor
from app.research.citation import citation_engine
from app.rag.retriever import rag_retriever
from app.agents.analyst import analyst_agent
from app.agents.fact_checker import fact_checker_agent
from app.agents.synthesizer import synthesizer_agent
from app.utils.logger import logger


class ResearchOrchestrator:
    async def run_pipeline_stream(self, job: ResearchJob) -> AsyncGenerator[Dict[str, Any], None]:
        job.status = ResearchStatus.PLANNING
        job.progress_percentage = 10
        job.current_step = "Decomposing research objective and constructing hypothesis plan..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

        # 1. Planning Phase
        tasks = await research_planner.create_plan(job.query, depth=job.depth, breadth=job.breadth)
        job.tasks = tasks
        job.progress_percentage = 25
        job.current_step = f"Generated {len(tasks)} parallel exploration vectors across Web, Academic, and Market."
        await research_repo.update_job(job)
        yield {"event": "plan_ready", "data": {"tasks": [t.model_dump() for t in tasks]}}

        # 2. Execution Phase (Search, Scrape, Extract across Web, Academic, Market in parallel)
        job.status = ResearchStatus.SEARCHING
        job.progress_percentage = 40
        job.current_step = f"Executing {len(tasks)} parallel exploration vectors across Web, Papers, and Market..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

        async def _on_task_finished(task_obj: ResearchTask, task_sources: List[Source]):
            for s in task_sources:
                await research_repo.add_source(s)
                job.source_ids.append(s.id)

        sources = await research_executor.execute_tasks(
            tasks=tasks,
            research_id=job.id,
            on_task_complete=_on_task_finished,
        )

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
        job.progress_percentage = 70
        job.current_step = "Indexing RAG knowledge vectors and harvesting atomic evidence..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

        # RAG Indexing
        await rag_retriever.index_sources([s.model_dump() for s in sources])

        # Evidence Extraction
        all_evidence = []
        for s in sources:
            evs = evidence_extractor.extract_evidence(s, job.id)
            for ev in evs:
                await research_repo.add_evidence(ev)
                job.evidence_ids.append(ev.id)
                all_evidence.append(ev)

        # 4. Fact Verification & Epistemic Audit (Day 28)
        job.status = ResearchStatus.ANALYZING
        job.progress_percentage = 80
        job.current_step = "Conducting epistemic cross-examination & fact verification across source claims..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

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

        # 5. Citation Generation & Multi-Dimensional Synthesis (Day 27)
        job.status = ResearchStatus.SYNTHESIZING
        job.progress_percentage = 90
        job.current_step = "Synthesizing multi-section publication report across all findings, trends, and risks..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

        citations = citation_engine.build_citations(sources, verified_evidence)
        previous_context = {
            "query": job.query,
            "depth": job.depth,
            "breadth": job.breadth,
            "categories": job.categories,
            "task_count": len(tasks),
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

        # 6. Completion
        job.report_id = report.id
        job.status = ResearchStatus.COMPLETED
        job.progress_percentage = 100
        job.current_step = "Research successfully completed."
        job.completed_at = datetime.now(timezone.utc)
        await research_repo.update_job(job)

        yield {
            "event": "report_ready",
            "data": {
                "job": job.model_dump(mode="json"),
                "report": report.model_dump(mode="json")
            }
        }


research_orchestrator = ResearchOrchestrator()
