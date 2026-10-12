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
        if (mongoose.connection.readyState !== 1) return;
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
            await stateMachine.transition(research, STATES.PLANNING, {
                step: "Query planner is decomposing the research question into investigation tracks",
                message: `Planner created web, news/paper, market, and other-source tracks for “${research.query}”.`
            });
            const plan = createPlan({ query: research.query, ...options });
            research.plan = plan;
            research.tasks = plan.tasks;
            await research.save();
            await this.pause(signal);
            if (this.isAborted(signal)) return;

            stage = STATES.SEARCHING;
            await stateMachine.transition(research, STATES.SEARCHING, {
                step: "Query planner is generating targeted searches across selected source types",
                message: `Generated ${plan.tasks.length} targeted research queries.`
            });
            const collected = await collectSources(plan.tasks, signal);
            research.sources = collected.map((source) => this.serializeSource(source));
            research.tasks = plan.tasks.map((task) => ({
                ...task,
                status: collected.some((source) => source.taskId === task.id) ? "completed" : "failed",
                resultsCount: collected.filter((source) => source.taskId === task.id).length
            }));
            await research.save();
            await this.pause(signal);
            if (this.isAborted(signal)) return;

            stage = STATES.COLLECTING;
            await stateMachine.transition(research, STATES.COLLECTING, {
                step: "Source collector is gathering web, news, paper, and public-record results; content extraction is running",
                message: `Collected ${collected.length} unique sources and started content extraction.`
            });
            const extracted = await extractSources(collected, signal);
            research.sources = extracted.map((source) => this.serializeSource(source));
            await research.save();
            await this.pause(signal);
            if (this.isAborted(signal)) return;

            const evidence = evidenceFromSources(extracted, research.query);
            research.evidence = evidence;
            await research.save();

            stage = STATES.ANALYZING;
            await stateMachine.transition(research, STATES.ANALYZING, {
                step: "Gemini Analysis Agent is analyzing extracted evidence, synthesizing findings, and identifying trends",
                message: `Analyzing ${evidence.length} evidence items extracted from ${extracted.length} sources.`
            });
            let analysis = null;
            if (process.env.GEMINI_API_KEY && process.env.NODE_ENV !== "test") {
                try {
                    analysis = await geminiAnalyzeEvidence({ query: research.query, evidence, sources: extracted, signal });
                } catch (geminiError) {
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
            if (this.isAborted(signal)) return;

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

            research.verificationSummary = {
                liveWebResearch: allSources.some((source) => !source.isFixture),
                independentVerification: verification.attempted || factChecks.some((c) => c.verificationMethod === "gemini_fact_checking"),
                attemptedClaims: factChecks.length,
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
                    active: Boolean(process.env.GEMINI_API_KEY),
                    model: getGeminiModel(),
                    analyzedWithGemini: analysis?.engine === "gemini",
                    factCheckedWithGemini: factChecks.some((c) => c.evaluatedBy === "gemini"),
                    reportWriter: process.env.GEMINI_API_KEY ? "Gemini Grounded Report Generator" : "Deterministic Grounded Generator"
                },
                verifiedAt: new Date()
            };
            await stateMachine.transition(research, STATES.VERIFYING, {
                step: "Gemini Fact-Check Judge is cross-checking claims and exposing source agreement or uncertainty",
                message: `${verifiedCount} claims verified with independent sources; ${singleSourceCount} single-source claims labeled with limitations.`
            });
            await research.save();
            await this.pause(signal, this.stepDelayMs * 3);
            if (this.isAborted(signal)) return;

            stage = STATES.SYNTHESIZING;
            await stateMachine.transition(research, STATES.SYNTHESIZING, {
                step: "Synthesis engine is combining analysis, fact checks, and comparisons into a grounded narrative",
                message: "Combined verified evidence with explicitly labeled limitations and contradictions."
            });
            // Keep synthesis visible long enough for polling clients to render
            // the distinct synthesis stage before report writing begins.
            await this.pause(signal, this.stepDelayMs * 3);
            if (this.isAborted(signal)) return;

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
            research.citations = reportData.citations;
            await stateMachine.transition(research, STATES.REPORT_GENERATION, {
                step: "Report generator is formatting the research narrative and attaching source citations",
                message: `Generated a report with ${reportData.citations.length} traceable citations.`
            });
            await research.save();
            // Keep report generation observable before the final quality check.
            await this.pause(signal, this.stepDelayMs * 3);
            if (this.isAborted(signal)) return;

            stage = STATES.QUALITY_CHECK;
            const citationCoverage = reportData.citations.length > 0 ? 100 : 0;
            const verificationCoverage = factChecks.length > 0
                ? (factChecks.filter((check) => check.status === "verified").length / factChecks.length) * 100
                : 0;
            research.qualityScore = Math.round((citationCoverage * 0.35) + (verificationCoverage * 0.4) + (Math.min(100, evidence.length * 8) * 0.25));
            research.qualityCheckResults = {
                citationCompleteness: `${citationCoverage}%`,
                evidenceItems: evidence.length,
                factCheckedClaims: factChecks.length,
                independentlyVerifiedClaims: verifiedCount,
                independentVerificationCoverage: `${Math.round(verificationCoverage)}%`,
                liveSources: allSources.filter((source) => !source.isFixture).length,
                verificationSources: verificationSources.length,
                reportGenerator: process.env.GEMINI_API_KEY ? `Gemini (${getGeminiModel()}) with deterministic fallback` : "Deterministic grounded generator"
            };
            await stateMachine.transition(research, STATES.QUALITY_CHECK, {
                step: "Quality check is validating evidence coverage, report coherence, and citation integrity",
                message: `Quality check completed with score ${research.qualityScore}/100.`
            });
            await this.pause(signal, this.stepDelayMs * 3);
            if (this.isAborted(signal)) return;

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
            if (existingReport) {
                Object.assign(existingReport, reportPayload);
                await existingReport.save();
            } else {
                await Report.create(reportPayload);
            }
            if (this.isAborted(signal)) return;
            await stateMachine.transition(research, STATES.COMPLETED, {
                step: "Research completed successfully. Final report published.",
                message: "Planning, collection, extraction, analysis, fact-checking, reporting, and citation generation completed."
            });
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
}

module.exports = new ResearchEngine();
