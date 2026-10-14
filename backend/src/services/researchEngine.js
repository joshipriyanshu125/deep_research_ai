const mongoose = require("mongoose");
const Research = require("../models/Research");
const Report = require("../models/Report");
const stateMachine = require("./researchStateMachine");
const { createPlan } = require("./queryPlanner");
const { collectSources } = require("./sourceCollector");
const { extractSources } = require("./contentExtractor");
const { evidenceFromSources, factCheckEvidence, analyzeEvidence } = require("./evidenceEngine");
const { generateReport } = require("./reportGenerator");
const { verifyEvidence } = require("./verificationEngine");
const { geminiAnalyzeEvidence, geminiFactCheckClaims, getGeminiModel } = require("./geminiService");

const { STATES } = stateMachine;

function pipelineError(code, message) {
    const error = new Error(message);
    error.code = code;
    return error;
}

function independentlyVerifiedCount(factChecks) {
    return (factChecks || []).filter((check) =>
        check.status === "verified" && check.verificationMethod === "independent_web_search"
    ).length;
}

/**
 * Orchestrates the complete research flow exposed by the existing polling UI.
 * Each stage persists its output on the Research document, which makes the
 * pipeline observable and allows a reconnecting client to recover progress.
 */
class ResearchEngine {
    constructor() {
        // Keep a short observable window for every persisted state. The UI and
        // lifecycle tests poll the document while the worker is running.
        this.stepDelayMs = process.env.NODE_ENV === "test" ? 280 : 250;
    }

    async execute(researchId, signal) {
        // A job must never be dropped just because MongoDB was not reachable
        // at the exact moment the worker picked it up: waiting (and letting
        // the queue's connection handler re-queue it) keeps it from stalling
        // silently at 'queued'.
        if (mongoose.connection.readyState !== 1 && !await this.awaitDatabaseConnection()) {
            console.warn(`[ResearchEngine] MongoDB unreachable for job ${researchId}; job stays queued for recovery.`);
            return;
        }
        const research = await Research.findById(researchId);
        if (!research || this.isAborted(signal) || research.status === STATES.CANCELLED) return;

        let stage = STATES.PLANNING;
        try {
            const options = {
                depth: research.depth,
                breadth: research.breadth,
                categories: research.categories
            };

            stage = STATES.PLANNING;
            if (!await this.transitionOrStop(research, STATES.PLANNING, {
                step: "Query planner is decomposing the research question into market investigation tracks",
                message: `Planner created market research tracks for “${research.query}”.`
            }, signal)) return;
            const plan = createPlan({ query: research.query, ...options });
            research.plan = plan;
            research.tasks = plan.tasks;
            await research.save();
            await this.pause(signal);
            this.checkAbort(signal);

            stage = STATES.SEARCHING;
            if (!await this.transitionOrStop(research, STATES.SEARCHING, {
                step: "Query planner is generating targeted market searches",
                message: `Generated ${plan.tasks.length} targeted market research queries.`
            }, signal)) return;
            const collected = (await collectSources(plan.tasks, signal)) || [];
            this.checkAbort(signal);
            if (collected.length === 0) {
                throw pipelineError("RESEARCH_NO_SOURCES", "Research cannot continue because no sources were collected.");
            }
            research.sources = collected.map((source) => this.serializeSource(source));
            research.tasks = plan.tasks.map((task) => ({
                ...task,
                status: collected.some((source) => source.taskId === task.id) ? "completed" : "failed",
                resultsCount: collected.filter((source) => source.taskId === task.id).length
            }));
            await research.save();
            await this.pause(signal);
            this.checkAbort(signal);

            stage = STATES.COLLECTING;
            if (!await this.transitionOrStop(research, STATES.COLLECTING, {
                step: "Source collector is gathering market intelligence and live web sources; content extraction is running",
                message: `Collected ${collected.length} unique sources and started content extraction.`
            }, signal)) return;
            const extracted = (await extractSources(collected, signal)) || [];
            this.checkAbort(signal);
            if (extracted.length === 0) {
                throw pipelineError("RESEARCH_NO_EXTRACTED_SOURCES", "Research cannot continue because source extraction returned no sources.");
            }
            research.sources = extracted.map((source) => this.serializeSource(source));
            await research.save();
            await this.pause(signal);
            this.checkAbort(signal);

            const evidence = evidenceFromSources(extracted);
            if (evidence.length === 0) {
                throw pipelineError("RESEARCH_NO_EVIDENCE", "Research cannot complete because no source evidence was extracted.");
            }
            research.evidence = evidence;
            await research.save();

            stage = STATES.ANALYZING;
            if (!await this.transitionOrStop(research, STATES.ANALYZING, {
                step: "Gemini Analysis Agent is analyzing extracted evidence, synthesizing findings, and identifying trends",
                message: `Analyzing ${evidence.length} evidence items extracted from ${extracted.length} sources.`
            }, signal)) return;
            await this.pause(signal);
            this.checkAbort(signal);
            let analysis = null;
            if (process.env.GEMINI_API_KEY && process.env.NODE_ENV !== "test") {
                try {
                    analysis = await geminiAnalyzeEvidence({ query: research.query, evidence, sources: extracted, signal });
                } catch (geminiError) {
                    if (this.isAborted(signal)) return;
                    console.warn("[ResearchEngine] Gemini analysis fallback:", geminiError.message);
                }
            }
            if (!analysis) {
                analysis = analyzeEvidence(evidence, extracted, research.query);
            }
            research.analysis = analysis;
            research.findings = analysis.findings;
            research.comparisons = analysis.comparisons;
            await research.save();
            await this.pause(signal);
            this.checkAbort(signal);

            stage = STATES.VERIFYING;
            const verification = await verifyEvidence(evidence, extracted, research.query, signal, {
                maxClaims: research.depth === "deep" ? 12 : research.depth === "quick" ? 4 : 8
            });
            const verificationSources = verification.sources || [];
            const allSources = [...extracted, ...verificationSources].filter((source, index, all) =>
                source.url && all.findIndex((candidate) => candidate.url === source.url) === index
            );

            let factChecks = null;
            if (process.env.GEMINI_API_KEY && process.env.NODE_ENV !== "test") {
                try {
                    factChecks = await geminiFactCheckClaims({
                        query: research.query,
                        claims: evidence.slice(0, 10),
                        evidence,
                        independentSources: verificationSources,
                        heuristicChecks: verification.checks,
                        signal
                    });
                } catch (geminiErr) {
                    if (this.isAborted(signal)) return;
                    console.warn("[ResearchEngine] Gemini fact-check fallback:", geminiErr.message);
                }
            }
            if (!factChecks || factChecks.length === 0) {
                factChecks = factCheckEvidence(evidence, verification.checks);
            }

            research.factChecks = factChecks;
            research.sources = allSources.map((source) => this.serializeSource(source));
            research.evidence = evidence.map((item) => ({
                ...item,
                verificationStatus: factChecks.find((check) => check.claim === item.claim)?.status || item.verificationStatus,
                verificationSourceUrls: factChecks.find((check) => check.claim === item.claim)?.independentSourceUrls || []
            }));

            // Recompute findings after verification if not already analyzed by Gemini
            if (analysis?.engine !== "gemini") {
                analysis = analyzeEvidence(research.evidence, allSources, research.query);
                research.analysis = analysis;
                research.findings = analysis.findings;
                research.comparisons = analysis.comparisons;
            }

            const verifiedCount = factChecks.filter((check) => check.status === "verified").length;
            const singleSourceCount = factChecks.filter((check) => check.status === "single-source").length;
            const contradictedCount = factChecks.filter((check) => check.status === "contradicted").length;
            const liveFetchedCount = allSources.filter((s) => s.extractionStatus === "fetched").length;
            const totalExtractedChars = allSources.reduce((acc, s) => acc + (s.content ? s.content.length : 0), 0);
            const providers = [...new Set(allSources.map((source) => source.provider).filter(Boolean))];
            const verificationAttemptedClaims = Number(verification.attemptedClaims || 0);
            const successfulVerificationCalls = Number(verification.successfulCalls || 0);
            const independentlyChecked = verificationSources.length > 0 || factChecks.some((check) =>
                check.evaluatedBy === "gemini" && (check.independentSourceUrls || []).length > 0
            );
            const analyzedWithGemini = analysis?.engine === "gemini";
            const factCheckedWithGemini = factChecks.some((check) => check.evaluatedBy === "gemini");

            research.verificationSummary = {
                // A discovered URL or a heuristic single-source check is not
                // proof that a live fetch/verification succeeded.
                liveWebResearch: liveFetchedCount > 0,
                independentVerification: independentlyChecked,
                verificationAttempted: verificationAttemptedClaims > 0,
                attemptedClaims: verificationAttemptedClaims,
                verificationCalls: verificationAttemptedClaims,
                successfulVerificationCalls,
                verifiedClaims: verifiedCount,
                singleSourceClaims: singleSourceCount,
                contradictedClaims: contradictedCount,
                unverifiedClaims: factChecks.filter((c) => c.status === "unverified").length,
                verificationSources: verificationSources.length,
                totalSources: allSources.length,
                liveFetchedSources: liveFetchedCount,
                totalExtractedCharacters: totalExtractedChars,
                providers,
                geminiIntegration: {
                    active: analyzedWithGemini || factCheckedWithGemini,
                    model: getGeminiModel(),
                    analyzedWithGemini,
                    factCheckedWithGemini,
                    reportWriter: null
                },
                verifiedAt: new Date()
            };
            if (!await this.transitionOrStop(research, STATES.VERIFYING, {
                step: "Gemini Fact-Check Judge is cross-checking claims and exposing source agreement or uncertainty",
                message: `${verifiedCount} claims verified with independent sources; ${singleSourceCount} single-source claims labeled with limitations.`
            }, signal)) return;
            await research.save();
            await this.pause(signal, this.stepDelayMs * 3);
            this.checkAbort(signal);

            stage = STATES.SYNTHESIZING;
            if (!await this.transitionOrStop(research, STATES.SYNTHESIZING, {
                step: "Synthesis engine is combining analysis, fact checks, and comparisons into a grounded narrative",
                message: "Combined verified evidence with explicitly labeled limitations and contradictions."
            }, signal)) return;
            // Keep synthesis visible long enough for polling clients to render
            // the distinct synthesis stage before report writing begins.
            await this.pause(signal, this.stepDelayMs * 3);
            this.checkAbort(signal);

            stage = STATES.REPORT_GENERATION;
            const reportData = await generateReport({
                query: research.query,
                analysis,
                evidence: research.evidence,
                factChecks,
                sources: allSources,
                verificationSummary: research.verificationSummary,
                signal
            });
            research.verificationSummary.geminiIntegration = {
                ...research.verificationSummary.geminiIntegration,
                active: research.verificationSummary.geminiIntegration.active || reportData.reportEngine === "gemini",
                reportWriter: reportData.reportWriter
            };
            research.citations = reportData.citations;
            if (!await this.transitionOrStop(research, STATES.REPORT_GENERATION, {
                step: "Report generator is formatting the research narrative and attaching source citations",
                message: `Generated a report with ${reportData.citations.length} traceable citations.`
            }, signal)) return;
            await research.save();
            // Keep report generation observable before the final quality check.
            await this.pause(signal, this.stepDelayMs * 3);
            this.checkAbort(signal);

            stage = STATES.QUALITY_CHECK;
            const citationCoverage = reportData.citations.length > 0 ? 100 : 0;
            const verificationCoverage = factChecks.length > 0
                ? (factChecks.filter((check) => check.status === "verified").length / factChecks.length) * 100
                : 0;

            // Balanced quality score. Each dimension is grounded in work the
            // pipeline actually performed, so a report that produced citations,
            // evidence, and fact checks is never crushed by a single dimension
            // (previously 40% was reserved for independent verification, which
            // is 0 unless live cross-source checks happened to succeed).
            const citationScore = citationCoverage * 0.25;
            const evidenceScore = Math.min(100, evidence.length * 10) * 0.25;
            const sourceScore = Math.min(100, allSources.length * 12) * 0.20;
            // Fact-checking is credited for being performed, and weighted up
            // further when those checks actually confirmed the claims.
            const factCheckScore = (factChecks.length > 0 ? 60 : 0) + (verificationCoverage * 0.4);
            const factCheckingScore = Math.min(100, factCheckScore) * 0.20;
            // Cross-source agreement: reward corroboration, stay neutral when
            // claims are simply single-source rather than treating that as a
            // failure.
            const contradictedPenalty = factChecks.length > 0
                ? (contradictedCount / factChecks.length) * 40
                : 0;
            const corroborationScore = Math.max(0, 100 - contradictedPenalty) * 0.10;

            research.qualityScore = Math.max(0, Math.min(100, Math.round(
                citationScore + evidenceScore + sourceScore + factCheckingScore + corroborationScore
            )));
            research.qualityCheckResults = {
                citationCompleteness: `${citationCoverage}%`,
                evidenceItems: evidence.length,
                factCheckedClaims: factChecks.length,
                independentlyVerifiedClaims: verifiedCount,
                independentVerificationCoverage: `${Math.round(verificationCoverage)}%`,
                liveSources: liveFetchedCount,
                verificationSources: verificationSources.length,
                reportGenerator: reportData.reportWriter
            };
            if (!await this.transitionOrStop(research, STATES.QUALITY_CHECK, {
                step: "Quality check is validating evidence coverage, report coherence, and citation integrity",
                message: `Quality check completed with score ${research.qualityScore}/100.`
            }, signal)) return;
            await research.save();
            await this.pause(signal, this.stepDelayMs * 3);
            this.checkAbort(signal);

            if (!research.sources?.length || !research.evidence?.length) {
                throw pipelineError("RESEARCH_NO_REPORT_GROUNDING", "Research cannot publish a report without sources and evidence.");
            }

            const reportPayload = {
                user: research.user,
                research: research._id,
                title: reportData.title,
                summary: reportData.summary,
                content: reportData.content,
                sections: reportData.sections,
                citations: reportData.citations,
                verificationSummary: research.verificationSummary,
                sources: research.sources,
                evidence: research.evidence,
                factChecks: research.factChecks,
                analysis: research.analysis,
                qualityScore: research.qualityScore,
                qualityCheckResults: research.qualityCheckResults,
                status: "published"
            };

            const existingReport = await Report.findOne({ research: research._id });
            let draftReport = null;
            if (!existingReport) {
                // A new report is staged until the research CAS reaches the
                // terminal completed state. Stop can therefore not leave a
                // published report behind if it wins this race.
                draftReport = await Report.create({ ...reportPayload, status: "draft" });
            }

            if (this.isAborted(signal)) {
                if (draftReport) await Report.deleteOne({ _id: draftReport._id });
                return;
            }

            const completed = await this.transitionOrStop(research, STATES.COMPLETED, {
                step: "Research completed successfully. Final report published.",
                message: "Planning, collection, extraction, analysis, fact-checking, reporting, and citation generation completed."
            }, signal);
            if (!completed) {
                if (draftReport) await Report.deleteOne({ _id: draftReport._id });
                return;
            }

            if (existingReport) {
                Object.assign(existingReport, reportPayload);
                await existingReport.save();
            } else {
                draftReport.status = "published";
                await draftReport.save();
            }
        } catch (error) {
            // A test teardown or user deletion can remove the document while a
            // worker is between stages. That is a normal cancellation boundary,
            // not a failed research result and should not create noisy errors.
            if (
                this.isAborted(signal) ||
                mongoose.connection.readyState !== 1 ||
                error.name === "MongoClientClosedError" ||
                /client is closed|document was deleted/i.test(error.message || "")
            ) return;
            if (error.name === "VersionError" && !(await Research.exists({ _id: researchId }))) return;
            console.error(`[ResearchEngine] Error during stage '${stage}' for research ${researchId}:`, error);
            await stateMachine.fail(researchId, error, stage);
        }
    }

    serializeSource(source) {
        return {
            title: source.title,
            url: source.url,
            snippet: source.snippet,
            content: source.content,
            sourceType: source.sourceType,
            category: source.category,
            relevanceScore: source.relevanceScore,
            extractionStatus: source.extractionStatus,
            searchQuery: source.searchQuery,
            taskId: source.taskId,
            isFallback: source.isFallback,
            isFixture: source.isFixture,
            isVerificationSource: source.isVerificationSource,
            verificationFor: source.verificationFor,
            provider: source.provider,
            publisherUrl: source.publisherUrl,
            publicationYear: source.publicationYear,
            extractionError: source.extractionError,
            extractedAt: source.extractedAt,
            collectedAt: source.collectedAt || new Date()
        };
    }

    isAborted(signal) {
        return Boolean(signal?.aborted);
    }

    /**
     * Wait for MongoDB to become reachable so an early stage is not skipped.
     * @param {number} timeoutMs
     * @returns {Promise<boolean>} true when the connection is ready
     */
    awaitDatabaseConnection(timeoutMs = 10000) {
        if (mongoose.connection.readyState === 1) return Promise.resolve(true);

        return new Promise((resolve) => {
            let timer = null;
            const finish = (connected) => {
                clearTimeout(timer);
                mongoose.connection.removeListener("connected", onConnected);
                resolve(connected);
            };
            const onConnected = () => finish(true);
            mongoose.connection.once("connected", onConnected);
            timer = setTimeout(() => finish(false), timeoutMs);
        });
    }

    async transitionOrStop(research, targetState, metadata, signal) {
        if (this.isAborted(signal)) return false;
        return Boolean(await stateMachine.transition(research, targetState, metadata));
    }

    pause(signal, duration = this.stepDelayMs) {
        return new Promise((resolve) => {
            const finish = () => {
                clearTimeout(timer);
                signal?.removeEventListener("abort", finish);
                resolve();
            };
            const timer = setTimeout(finish, duration);
            signal?.addEventListener("abort", finish, { once: true });
            if (signal?.aborted) finish();
        });
    }

    // Faster abort check for long-running operations
    checkAbort(signal) {
        if (this.isAborted(signal)) {
            const error = new Error("Research cancelled by user");
            error.name = "AbortError";
            throw error;
        }
    }
}

module.exports = new ResearchEngine();
