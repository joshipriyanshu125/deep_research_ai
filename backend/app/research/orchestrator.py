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

        # 2. Execution Phase (Search, Scrape, Extract across Web, Academic, Market)
        job.status = ResearchStatus.SEARCHING
        job.progress_percentage = 40
        job.current_step = "Executing parallel search & deep document scraping..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

        sources = await research_executor.execute_tasks(tasks, job.id)
        for s in sources:
            await research_repo.add_source(s)
            job.source_ids.append(s.id)

        job.progress_percentage = 60
        job.current_step = f"Retrieved and validated {len(sources)} authoritative sources."
        await research_repo.update_job(job)
        yield {"event": "sources_collected", "data": {"sources": [s.model_dump(mode="json") for s in sources]}}

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

        # 4. Fact Verification & Epistemic Audit
        job.status = ResearchStatus.ANALYZING
        job.progress_percentage = 80
        job.current_step = "Conducting epistemic cross-examination & fact verification..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

        verified_evidence = await fact_checker_agent.verify_evidence(all_evidence)
        analysis_result = await analyst_agent.analyze_findings(verified_evidence)
        yield {"event": "analysis_ready", "data": analysis_result}

        # 5. Citation Generation & Synthesis
        job.status = ResearchStatus.SYNTHESIZING
        job.progress_percentage = 90
        job.current_step = "Synthesizing multi-section publication report with inline citation anchors..."
        await research_repo.update_job(job)
        yield {"event": "status", "data": job.model_dump(mode="json")}

        citations = citation_engine.build_citations(sources)
        report: ResearchReport = await synthesizer_agent.synthesize_report(
            query=job.query,
            sources=sources,
            evidence=verified_evidence,
            citations=citations
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
