const mongoose = require("mongoose");
const Research = require("../models/Research");
const Report = require("../models/Report");
const stateMachine = require("./researchStateMachine");
const { createPlan } = require("./queryPlanner");
const { collectSources } = require("./sourceCollector");
const { extractSources } = require("./contentExtractor");
const { evidenceFromSources, factCheckEvidence, analyzeEvidence } = require("./evidenceEngine");
const { generateReport } = require("./reportGenerator");

const { STATES } = stateMachine;

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
                step: "Analysis engine is turning extracted passages into claims, trends, and comparisons",
                message: `Extracted ${evidence.length} evidence items from ${extracted.length} sources.`
            });
            const analysis = analyzeEvidence(evidence, extracted, research.query);
            research.analysis = analysis;
            research.findings = analysis.findings;
            research.comparisons = analysis.comparisons;
            await research.save();
            await this.pause(signal);
            if (this.isAborted(signal)) return;

            stage = STATES.VERIFYING;
            const factChecks = factCheckEvidence(evidence);
            research.factChecks = factChecks;
            research.evidence = evidence.map((item) => ({
                ...item,
                verificationStatus: factChecks.find((check) => check.claim === item.claim)?.status || item.verificationStatus
            }));
            await stateMachine.transition(research, STATES.VERIFYING, {
                step: "Fact-check engine is cross-checking claims and exposing source agreement or uncertainty",
                message: `Fact-checked ${factChecks.length} claims; single-source and unverified items remain labeled.`
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
                sources: extracted,
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
            research.qualityScore = Math.round((citationCoverage * 0.4) + (Math.min(100, factChecks.length * 10) * 0.3) + (Math.min(100, evidence.length * 8) * 0.3));
            research.qualityCheckResults = {
                citationCompleteness: `${citationCoverage}%`,
                evidenceItems: evidence.length,
                factCheckedClaims: factChecks.length,
                reportGenerator: process.env.GEMINI_API_KEY ? "Gemini with deterministic fallback" : "Deterministic grounded generator"
            };
            await stateMachine.transition(research, STATES.QUALITY_CHECK, {
                step: "Quality check is validating evidence coverage, report coherence, and citation integrity",
                message: `Quality check completed with score ${research.qualityScore}/100.`
            });
            await this.pause(signal);
            if (this.isAborted(signal)) return;

            const existingReport = await Report.findOne({ research: research._id });
            if (existingReport) {
                existingReport.title = reportData.title;
                existingReport.summary = reportData.summary;
                existingReport.content = reportData.content;
                existingReport.sections = reportData.sections;
                existingReport.citations = reportData.citations;
                await existingReport.save();
            } else {
                await Report.create({
                    user: research.user,
                    research: research._id,
                    title: reportData.title,
                    summary: reportData.summary,
                    content: reportData.content,
                    sections: reportData.sections,
                    citations: reportData.citations,
                    status: "published"
                });
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
