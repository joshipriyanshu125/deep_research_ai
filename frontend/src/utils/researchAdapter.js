function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null);
}

export function normalizeTask(task = {}) {
  return {
    ...task,
    id: firstDefined(task.id, task._id),
    status: task.status || 'pending',
    resultsCount: firstDefined(task.resultsCount, task.results_count, 0),
    startedAt: firstDefined(task.startedAt, task.started_at),
    completedAt: firstDefined(task.completedAt, task.completed_at),
    errorMessage: firstDefined(task.errorMessage, task.error_message),
    sourceUrls: firstDefined(task.sourceUrls, task.source_urls, []),
  };
}

export function normalizeSource(source = {}) {
  return {
    ...source,
    id: firstDefined(source.id, source._id, source.source_id),
    sourceId: firstDefined(source.sourceId, source.source_id, source.id, source._id),
    title: source.title || source.name || source.url || 'Untitled source',
    url: source.url || source.sourceUrl || source.source_url || '',
    snippet: firstDefined(source.snippet, source.description, ''),
    sourceType: firstDefined(source.sourceType, source.source_type, source.type, source.category),
    relevanceScore: firstDefined(source.relevanceScore, source.relevance_score, source.score),
    credibilityScore: firstDefined(source.credibilityScore, source.credibility_score),
    extractionStatus: firstDefined(source.extractionStatus, source.extraction_status),
    isVerificationSource: Boolean(firstDefined(source.isVerificationSource, source.is_verification_source, false)),
  };
}

export function normalizeEvidence(evidence = {}) {
  return {
    ...evidence,
    id: firstDefined(evidence.id, evidence._id),
    sourceId: firstDefined(evidence.sourceId, evidence.source_id),
    sourceUrl: firstDefined(evidence.sourceUrl, evidence.source_url),
    sourceTitle: firstDefined(evidence.sourceTitle, evidence.source_title),
    verificationStatus: firstDefined(evidence.verificationStatus, evidence.verification_status),
    evidenceType: firstDefined(evidence.evidenceType, evidence.evidence_type),
  };
}

export function normalizeVerificationSummary(summary = {}) {
  return {
    ...summary,
    liveWebResearch: firstDefined(summary.liveWebResearch, summary.live_web_research, false),
    independentVerification: firstDefined(summary.independentVerification, summary.independent_verification, false),
    attemptedClaims: firstDefined(summary.attemptedClaims, summary.attempted_claims, 0),
    verifiedClaims: firstDefined(summary.verifiedClaims, summary.verified_claims, 0),
    singleSourceClaims: firstDefined(summary.singleSourceClaims, summary.single_source_claims, 0),
    contradictedClaims: firstDefined(summary.contradictedClaims, summary.contradicted_claims, 0),
    totalSources: firstDefined(summary.totalSources, summary.total_sources, 0),
    liveFetchedSources: firstDefined(summary.liveFetchedSources, summary.live_fetched_sources, 0),
    evidenceCount: firstDefined(summary.evidenceCount, summary.evidence_count, 0),
    providers: firstDefined(summary.providers, []),
    geminiIntegration: firstDefined(summary.geminiIntegration, summary.gemini_integration, {}),
  };
}

export function normalizeJob(payload) {
  const raw = payload?.research || payload?.data || payload || {};
  const tasks = Array.isArray(raw.tasks) ? raw.tasks.map(normalizeTask) : [];
  const sources = Array.isArray(raw.sources) ? raw.sources.map(normalizeSource) : [];
  const evidence = Array.isArray(raw.evidence) ? raw.evidence.map(normalizeEvidence) : [];
  const factChecks = firstDefined(raw.factChecks, raw.fact_checks, []);
  const citations = Array.isArray(raw.citations) ? raw.citations.map(normalizeSource) : [];
  const sourceIds = firstDefined(raw.sourceIds, raw.source_ids, []);
  const evidenceIds = firstDefined(raw.evidenceIds, raw.evidence_ids, []);

  return {
    ...raw,
    id: firstDefined(raw.id, raw._id, payload?.research_id, payload?.id),
    status: String(raw.status || payload?.status || 'pending').toLowerCase(),
    progress: Number(firstDefined(raw.progress, raw.progress_percentage, payload?.progress, 0)),
    currentStep: firstDefined(raw.currentStep, raw.current_step, payload?.currentStep, 'Initializing research…'),
    tasks,
    sources,
    evidence,
    factChecks,
    citations,
    sourceIds: Array.isArray(sourceIds) ? sourceIds : [],
    evidenceIds: Array.isArray(evidenceIds) ? evidenceIds : [],
    verificationSummary: normalizeVerificationSummary(
      firstDefined(raw.verificationSummary, raw.verification_summary, {}),
    ),
  };
}

export function normalizeReport(payload) {
  const raw = payload?.report || payload?.data || payload || {};
  const citations = firstDefined(raw.citations, raw.sources, []);
  const factChecks = firstDefined(raw.factChecks, raw.fact_checks, []);
  const evidence = Array.isArray(raw.evidence) ? raw.evidence.map(normalizeEvidence) : [];
  const sources = Array.isArray(raw.sources) ? raw.sources.map(normalizeSource) : [];

  return {
    ...raw,
    id: firstDefined(raw.id, raw._id),
    title: raw.title || 'Research Report',
    executiveSummary: firstDefined(raw.executiveSummary, raw.executive_summary, raw.summary, ''),
    markdownContent: firstDefined(raw.markdownContent, raw.markdown_content, raw.content, ''),
    citations: Array.isArray(citations) ? citations.map(normalizeSource) : [],
    sources,
    evidence,
    factChecks,
    qualityScore: firstDefined(raw.qualityScore, raw.quality_score),
    qualityCheckResults: firstDefined(raw.qualityCheckResults, raw.quality_check_results, {}),
    verificationSummary: normalizeVerificationSummary(
      firstDefined(raw.verificationSummary, raw.verification_summary, {}),
    ),
  };
}
