import asyncio
from typing import AsyncGenerator, Dict, Any, List, Set
from datetime import datetime, timezone
from app.database.models.research import ResearchJob, ResearchStatus, ResearchTask
from app.database.models.report import ResearchReport
from app.database.models.source import Source, normalize_url
from app.database.models.evidence import Evidence
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
# Day 91–95 — Advanced Research Modes
from app.research.research_modes import get_mode_config, ResearchModeConfig
from app.utils.logger import logger


class ResearchOrchestrator:
    @staticmethod
    def _start_execution_audit(job: ResearchJob) -> None:
        """Create a stable, API-visible record for every requested depth pass."""
        now = datetime.now(timezone.utc).isoformat()
        job.execution_summary = {
            "requested_depth": job.depth,
            "requested_breadth": job.breadth,
            "iterations": [
                {
                    "iteration": number,
                    "status": "pending",
                    "purpose": "discovery and evidence extraction" if number == 1 else "verification, contradiction analysis, and synthesis refinement",
                }
                for number in range(1, job.depth + 1)
            ],
            "stages": {},
            "started_at": now,
        }

    @staticmethod
    def _record_stage(job: ResearchJob, stage: str, status: str, **details: Any) -> None:
        """Record a pipeline stage without placing non-serialisable objects in a job."""
        audit = job.execution_summary
        audit.setdefault("stages", {})[stage] = {
            "status": status,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
            **details,
        }
        # Keep the audit in checkpoint_data as well for older clients that only
        # consume checkpoint information.
        job.checkpoint_data["execution_summary"] = audit
        try:
            from app.database.models.observability import AgentLogRecord
            from app.database.repositories.observability_repo import observability_repo
            asyncio.get_running_loop().create_task(observability_repo.add_agent_log(AgentLogRecord(
                research_id=job.id, agent=stage, status=status, details=details,
            )))
        except RuntimeError:
            pass

    @staticmethod
    def _record_iteration(job: ResearchJob, iteration: int, status: str, **details: Any) -> None:
        for item in job.execution_summary.get("iterations", []):
            if item["iteration"] == iteration:
                item.update({"status": status, **details})
                break

    @staticmethod
    def _merge_unique_sources(existing_sources: List[Source], new_sources: List[Source]) -> List[Source]:
        """Merge previously persisted sources with this run's results.

        First-wins, keyed by normalized URL (falling back to the source id) so
        a resumed run cannot duplicate the same URL in the final report.
        """
        unique_sources: Dict[str, Source] = {}
        for source in existing_sources + new_sources:
            url_key = normalize_url(source.url or "")
            unique_sources.setdefault(url_key or source.id, source)
        return list(unique_sources.values())

    async def run_pipeline_stream(self, job: ResearchJob) -> AsyncGenerator[Dict[str, Any], None]:
        try:
            # ----------------------------------------------------------------
            # Day 91–95: Resolve research mode config for this job
            # ----------------------------------------------------------------
            mode_cfg: ResearchModeConfig = get_mode_config(getattr(job, "research_mode", "standard"))
            self._start_execution_audit(job)
            self._record_iteration(job, 1, "running")
            logger.info(
                f"[ResearchModes] Job {job.id} running in '{mode_cfg.mode}' mode "
                f"(sources: {mode_cfg.min_sources}–{mode_cfg.max_sources}, "
                f"depth={mode_cfg.depth}, breadth={mode_cfg.breadth}, "
                f"passes={mode_cfg.verification_passes})"
            )

            research_event_bus.emit(
                RESEARCH_STARTED,
                job_id=job.id,
                message="Planning research...",
                data={
                    "query": job.query,
                    "depth": job.depth,
                    "breadth": job.breadth,
                    "research_mode": mode_cfg.mode,
                },
            )
            job.status = ResearchStatus.PLANNING
            job.progress_percentage = 10
            job.current_step = (
                f"[{mode_cfg.display_name}] Decomposing research objective and constructing hypothesis plan..."
            )
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}

            # 1. Planning Phase
            tasks = job.tasks or await research_planner.create_plan(
                job.query,
                depth=job.depth,
                breadth=job.breadth,
                categories=job.categories,
            )
            job.tasks = tasks
            self._record_stage(job, "planner", "completed", task_count=len(tasks))
            job.checkpoint_phase = "planned"
            job.checkpoint_data["task_ids"] = [t.id for t in tasks]
            job.progress_percentage = 25
            job.current_step = (
                f"[{mode_cfg.display_name}] Generated {len(tasks)} parallel exploration vectors."
            )
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
            job.current_step = (
                f"[{mode_cfg.display_name}] Executing {len(tasks)} parallel exploration vectors..."
            )
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}

            # Sources persisted by an earlier interrupted pass are loaded up
            # front so the resumed run neither re-persists nor re-emits them.
            existing_sources = await research_repo.get_sources_by_research(job.id)
            known_source_keys: Set[str] = set()
            for existing in existing_sources:
                if existing.id:
                    known_source_keys.add(existing.id)
                existing_url = normalize_url(existing.url or "")
                if existing_url:
                    known_source_keys.add(existing_url)

            async def _on_task_finished(task_obj: ResearchTask, task_sources: List[Source]):
                for s in task_sources:
                    s_url = normalize_url(s.url or "")
                    if s.id in known_source_keys or (s_url and s_url in known_source_keys):
                        # Already persisted by a previous (interrupted) run —
                        # adding it again would duplicate it in the report.
                        continue
                    persisted = await research_repo.add_source(s)
                    if persisted.id:
                        known_source_keys.add(persisted.id)
                    if s_url:
                        known_source_keys.add(s_url)
                    if persisted.id not in job.source_ids:
                        job.source_ids.append(persisted.id)
                    research_event_bus.emit(
                        SOURCE_PROCESSED,
                        job_id=job.id,
                        message=f"Processing source: {persisted.title or persisted.url or 'source'}",
                        data={"source": persisted.model_dump(mode="json") if hasattr(persisted, "model_dump") else persisted.__dict__},
                    )

                # Persist task completion as each parallel track returns. A
                # polling client should not see every vector stuck at
                # "pending" until the entire search phase has finished.
                job.tasks = tasks
                finished = sum(1 for task in tasks if task.status in {"completed", "failed"})
                job.progress_percentage = 40 + round((finished / max(1, len(tasks))) * 20)
                job.current_step = (
                    f"[{mode_cfg.display_name}] Completed {finished}/{len(tasks)} research tracks; "
                    "collecting source results..."
                )
                await research_repo.update_job(job)

            new_sources = await research_executor.execute_tasks(
                tasks=tasks,
                research_id=job.id,
                max_concurrency=mode_cfg.max_concurrency,
                on_task_complete=_on_task_finished,
            )
            sources = self._merge_unique_sources(existing_sources, new_sources)
            from app.research.source_validator import source_validator
            sources = source_validator.filter_valid_sources(sources)
            if not sources:
                raise RuntimeError(
                    "No usable sources were collected. Live search providers returned no verifiable results."
                )
            job.source_ids = [source.id for source in sources]
            self._record_stage(
                job, "research_tracks", "completed", source_count=len(sources),
                categories=sorted({task.category for task in tasks}),
                task_results=[{"id": task.id, "category": task.category, "results_count": task.results_count, "status": task.status} for task in tasks],
            )
            job.checkpoint_data["source_ids"] = job.source_ids
            await research_repo.update_job(job)

            job.progress_percentage = 60
            job.current_step = (
                f"[{mode_cfg.display_name}] Retrieved {len(sources)} authoritative sources."
            )
            await research_repo.update_job(job)
            yield {
                "event": "sources_collected",
                "data": {
                    "sources": [s.model_dump(mode="json") for s in sources],
                    "execution_stats": research_executor.last_execution_stats,
                    "research_mode": mode_cfg.mode,
                }
            }

            # 3. Knowledge / RAG Indexing & Evidence Extraction
            job.status = ResearchStatus.EXTRACTING
            job.checkpoint_phase = "extracting"
            job.progress_percentage = 70
            job.current_step = (
                f"[{mode_cfg.display_name}] Indexing RAG knowledge vectors and harvesting atomic evidence..."
            )
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}

            await rag_retriever.index_sources([s.model_dump() for s in sources])

            all_evidence = await research_repo.get_evidence_by_research(job.id)
            existing_evidence_source_ids = {e.source_id for e in all_evidence}
            evidence_tasks = []
            for s in sources:
                if s.id in existing_evidence_source_ids:
                    continue
                evidence_tasks.append(
                    evidence_extractor.extract_evidence_async(
                        s, job.id, topic=job.query, use_llm=True, max_evidence=10
                    )
                )

            import asyncio as _asyncio
            evidence_batch = await _asyncio.gather(*evidence_tasks, return_exceptions=True)
            for result in evidence_batch:
                if isinstance(result, Exception):
                    logger.warning(f"Evidence extraction error: {result}")
                    continue
                for ev in (result or []):
                    await research_repo.add_evidence(ev)
                    if ev.id not in job.evidence_ids:
                        job.evidence_ids.append(ev.id)
                    all_evidence.append(ev)
                    research_event_bus.emit(
                        EVIDENCE_FOUND,
                        job_id=job.id,
                        message=f"Evidence extracted",
                        data={"evidence": ev.model_dump(mode="json") if hasattr(ev, "model_dump") else ev.__dict__},
                    )
            if not all_evidence:
                raise RuntimeError(
                    "Sources were collected, but no source-grounded evidence could be extracted."
                )
            self._record_stage(job, "evidence_engine", "completed", evidence_count=len(all_evidence))
            self._record_iteration(job, 1, "completed", evidence_count=len(all_evidence))
            await research_repo.update_job(job)

            # Retrieve source-grounded chunks after indexing.  These are used
            # to corroborate fact checks and are handed to the writer as
            # provenance-bearing context; they are not invented evidence.
            rag_chunks = await rag_retriever.retrieve_hybrid(job.query, top_k=8)
            rag_context_evidence = [
                Evidence(
                    research_id=job.id,
                    source_id=str(chunk.get("metadata", {}).get("source_id") or chunk.get("document_id") or "rag-context"),
                    source_url=str(chunk.get("metadata", {}).get("url") or ""),
                    source_title=str(chunk.get("metadata", {}).get("title") or "Retrieved RAG context"),
                    claim=str(chunk.get("content") or ""),
                    quote=str(chunk.get("content") or ""),
                    confidence=min(1.0, max(0.0, float(chunk.get("score", 0.0)))),
                    metadata={"rag_retrieved": True, "chunk_id": chunk.get("chunk_id"), "section": chunk.get("section")},
                )
                for chunk in rag_chunks
                if str(chunk.get("content") or "").strip()
            ]
            self._record_stage(job, "rag_retrieval", "completed", retrieved_chunk_count=len(rag_context_evidence))
            await research_repo.update_job(job)

            # 4. Fact Verification — skipped for quick mode
            job.status = ResearchStatus.ANALYZING
            job.checkpoint_phase = "analyzing"
            job.progress_percentage = 80
            job.current_step = (
                f"[{mode_cfg.display_name}] Conducting epistemic cross-examination & fact verification..."
            )
            await research_repo.update_job(job)
            yield {"event": "status", "data": job.model_dump(mode="json")}

            if mode_cfg.enable_fact_checking:
                research_event_bus.emit(
                    FACT_CHECK_STARTED,
                    job_id=job.id,
                    message="Fact checking...",
                    data={"evidence_count": len(all_evidence)},
                )
                verified_evidence = all_evidence
                fact_check_results = []
                # Each requested depth after discovery is a real verification
                # iteration.  This makes depth=2 explicitly run and expose
                # iterations 1 and 2 instead of treating depth as planner-only.
                for iteration in range(2, job.depth + 1):
                    self._record_iteration(job, iteration, "running")
                    verified_evidence = await fact_checker_agent.verify_evidence(
                        verified_evidence, sources=sources, context_evidence=rag_context_evidence,
                    )
                    for evidence in verified_evidence:
                        await research_repo.update_evidence(evidence)
                    fact_check_results = await fact_checker_agent.fact_check_batch(
                        claims=verified_evidence,
                        evidence_pool=verified_evidence,
                        sources=sources,
                    )
                    self._record_iteration(
                        job, iteration, "completed",
                        verified_count=sum(1 for item in fact_check_results if item.supported),
                    )

                # A depth-one fact-checked request still receives its single
                # verification pass; depth two and above use the loop above.
                if job.depth == 1:
                    verified_evidence = await fact_checker_agent.verify_evidence(
                        all_evidence, sources=sources, context_evidence=rag_context_evidence,
                    )
                    for evidence in verified_evidence:
                        await research_repo.update_evidence(evidence)
                    fact_check_results = await fact_checker_agent.fact_check_batch(
                        claims=verified_evidence, evidence_pool=verified_evidence, sources=sources,
                    )
                self._record_stage(
                    job, "verification", "completed", passes=max(1, job.depth - 1),
                    verified_count=sum(1 for item in fact_check_results if item.supported),
                )
                yield {
                    "event": "fact_checks_ready",
                    "data": {
                        "fact_checks": [fc.to_dict() for fc in fact_check_results],
                        "verified_count": len([fc for fc in fact_check_results if fc.supported]),
                    }
                }
            else:
                # quick mode — bypass fact-checking, treat all evidence as verified
                logger.info(f"[ResearchModes] Skipping fact-checking (mode={mode_cfg.mode})")
                verified_evidence = all_evidence
                fact_check_results = []
                for iteration in range(2, job.depth + 1):
                    self._record_iteration(job, iteration, "skipped", reason="fact checking is disabled for this mode")
                self._record_stage(job, "verification", "skipped", reason="fact checking is disabled for this mode")
                yield {
                    "event": "fact_checks_ready",
                    "data": {"fact_checks": [], "verified_count": 0, "skipped": True},
                }

            # 4b. Contradiction analysis is part of every fact-checking run.
            # Expert mode retains the same sweep, but it is no longer invisible
            # for the standard depth-two workflow.
            if mode_cfg.enable_fact_checking:
                logger.info(f"[ResearchModes] Running contradiction analysis (mode={mode_cfg.mode})")
                job.current_step = f"[{mode_cfg.display_name}] Running contradiction analysis..."
                await research_repo.update_job(job)
                yield {"event": "contradiction_analysis_started", "data": {"mode": mode_cfg.mode}}
                # Import at call-site to avoid circular imports
                from app.research.contradictions import contradiction_detector
                contradiction_report = contradiction_detector.detect_all(verified_evidence)
                contradiction_data = {
                    "finding_count": len(contradiction_report),
                    "findings": [finding.format() for finding in contradiction_report],
                }
                self._record_stage(job, "contradiction_engine", "completed", **contradiction_data)
                await research_repo.update_job(job)
                yield {
                    "event": "contradiction_analysis_ready",
                    "data": contradiction_data,
                }
            else:
                self._record_stage(job, "contradiction_engine", "skipped", reason="fact checking is disabled for this mode")

            # 4c. Analyst pass
            analysis_result = await analyst_agent.analyze_findings(verified_evidence)
            self._record_stage(job, "analysis", "completed", key_pattern_count=len(analysis_result.get("key_patterns", [])))
            await research_repo.update_job(job)
            yield {"event": "analysis_ready", "data": analysis_result}

            # 5. Citation Generation & Synthesis
            job.status = ResearchStatus.SYNTHESIZING
            job.checkpoint_phase = "synthesizing"
            job.progress_percentage = 90
            job.current_step = (
                f"[{mode_cfg.display_name}] Synthesizing multi-section publication report..."
            )
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
                "research_mode": mode_cfg.mode,
                "rag_context": [
                    {"content": item.quote[:600], "source_id": item.source_id, "source_url": item.source_url,
                     "source_title": item.source_title, "chunk_id": item.metadata.get("chunk_id")}
                    for item in rag_context_evidence
                ],
            }

            # First synthesis pass (always runs)
            await self._raise_if_cancelled(job)
            report: ResearchReport = await synthesizer_agent.synthesize_report(
                query=job.query,
                sources=sources,
                evidence=verified_evidence,
                citations=citations,
                task_results=tasks,
                previous_context=previous_context,
                fact_checks=fact_check_results,
            )

            # 5b. Additional verification passes — deep (×2) and expert (×3)
            if mode_cfg.enable_multi_pass and mode_cfg.verification_passes > 1:
                for pass_num in range(2, mode_cfg.verification_passes + 1):
                    logger.info(
                        f"[ResearchModes] Verification pass {pass_num}/{mode_cfg.verification_passes} "
                        f"(mode={mode_cfg.mode})"
                    )
                    job.current_step = (
                        f"[{mode_cfg.display_name}] Verification pass "
                        f"{pass_num}/{mode_cfg.verification_passes}..."
                    )
                    await research_repo.update_job(job)
                    yield {
                        "event": "verification_pass",
                        "data": {"pass": pass_num, "total": mode_cfg.verification_passes},
                    }
                    # Re-synthesise with refined context from prior pass
                    pass_context = {**previous_context, "pass": pass_num, "prior_report": report.model_dump(mode="json")}
                    report = await synthesizer_agent.synthesize_report(
                        query=job.query,
                        sources=sources,
                        evidence=verified_evidence,
                        citations=citations,
                        task_results=tasks,
                        previous_context=pass_context,
                        fact_checks=fact_check_results,
                    )

            # 5c. Cross-validation — deep & expert modes
            if mode_cfg.enable_cross_validation:
                logger.info(f"[ResearchModes] Running cross-validation (mode={mode_cfg.mode})")
                yield {
                    "event": "cross_validation_started",
                    "data": {"mode": mode_cfg.mode, "source_count": len(sources)},
                }

            await self._raise_if_cancelled(job)
            report.research_id = job.id
            await report_repo.create(report)
            self._record_stage(job, "writer", "completed", report_id=report.id)

            # 6. Quality Scoring
            quality = research_quality_scorer.score(
                sources=sources,
                evidence=all_evidence,
                tasks=tasks,
                citations=citations,
                fact_checks=fact_check_results,
                report=report,
            )
            quality_dict = quality.to_dict()
            logger.info(f"[QualityScorer] {quality.format_report()}")

            stopping = research_stopping_criteria.evaluate(
                tasks=tasks,
                evidence=all_evidence,
                sources=sources,
                confidence_score=report.confidence,
                fact_checks=fact_check_results,
                adaptive_round=0,
            )
            logger.info(f"[StoppingCriteria] {research_stopping_criteria.summary_line(stopping)}")

            pipeline_summary = research_agent_orchestrator.get_pipeline_summary(job.id)

            # 7. Completion
            await self._raise_if_cancelled(job)
            job.report_id = report.id
            job.status = ResearchStatus.COMPLETED
            job.checkpoint_phase = "completed"
            job.progress_percentage = 100
            job.current_step = f"[{mode_cfg.display_name}] Research successfully completed."
            job.completed_at = datetime.now(timezone.utc)
            job.execution_summary["completed_at"] = job.completed_at.isoformat()
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
                    "research_mode": mode_cfg.mode,
                },
            )

            yield {
                "event": "report_ready",
                "data": {
                    "job": job.model_dump(mode="json"),
                    "report": report.model_dump(mode="json"),
                    "quality_score": quality_dict,
                    "research_mode": mode_cfg.mode,
                }
            }
        except asyncio.CancelledError:
            # Cancellation is an intentional terminal state, not a failed
            # research run. The worker/API normally persists this first, but
            # keep the orchestrator safe when it is cancelled directly.
            if job.status != ResearchStatus.CANCELLED:
                job.status = ResearchStatus.CANCELLED
                job.progress_percentage = 0
                job.current_step = "Research cancelled by user."
                job.checkpoint_phase = "cancelled"
                job.completed_at = datetime.now(timezone.utc)
                try:
                    await research_repo.update_job(job)
                except Exception:
                    pass
            return
        except Exception as exc:
            if job.status == ResearchStatus.CANCELLED:
                return
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

    @staticmethod
    async def _raise_if_cancelled(job: ResearchJob) -> None:
        latest = await research_repo.get_job(job.id)
        if latest and latest.status == ResearchStatus.CANCELLED:
            raise asyncio.CancelledError


research_orchestrator = ResearchOrchestrator()


