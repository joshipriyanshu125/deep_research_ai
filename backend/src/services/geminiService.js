/**
 * Gemini Service — Direct AI Answer
 *
 * Wraps the @google/genai SDK to provide a simple question → answer capability.
 * This service is intentionally isolated and does NOT touch the existing
 * Deep Research pipeline (researchEngine, researchStateMachine, researchQueue).
 *
 * Configuration (all via environment variables — never hardcoded):
 *   GEMINI_API_KEY  — required — Google AI Studio key
 *   GEMINI_MODEL    — optional — defaults to "gemini-flash-lite-latest"
 */

const { GoogleGenAI } = require("@google/genai");

// ---------------------------------------------------------------------------
// Configuration
// ---------------------------------------------------------------------------
const getGeminiApiKey = () => process.env.GEMINI_API_KEY;
const DEFAULT_GEMINI_MODEL = "gemini-flash-lite-latest";

const getGeminiModel = () => {
    const configuredModel = process.env.GEMINI_MODEL;
    return typeof configuredModel === "string" && configuredModel.trim()
        ? configuredModel.trim()
        : DEFAULT_GEMINI_MODEL;
};

// Current Gemini model aliases and stable model IDs. Keep the configured model first
// so supported custom/model-version choices continue to work unchanged.
const FALLBACK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite"
];

function getGeminiModelCandidates(primaryModel = getGeminiModel()) {
    return [
        primaryModel,
        ...FALLBACK_MODELS.filter((modelName) => modelName !== primaryModel)
    ];
}

// Lazy-initialised client
let _client = null;

function getClient() {
    const apiKey = getGeminiApiKey();
    if (!apiKey) {
        const err = new Error("GEMINI_API_KEY is not configured on the server.");
        err.status = 503;
        err.code = "GEMINI_KEY_MISSING";
        throw err;
    }
    if (!_client) {
        _client = new GoogleGenAI({ apiKey });
    }
    return _client;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------
const MAX_QUESTION_LENGTH = 2000; // characters
const REQUEST_TIMEOUT_MS = 30_000; // 30 s

function getGeminiErrorStatus(err) {
    const status = err?.status ?? err?.statusCode ?? err?.response?.status ?? err?.code;
    const numericStatus = Number(status);
    return Number.isNaN(numericStatus) ? status : numericStatus;
}

function isUnavailableModelError(err) {
    const status = getGeminiErrorStatus(err);
    const message = String(err?.message || "").toLowerCase();

    return status === 404 ||
        message.includes("not found") ||
        message.includes("unknown model") ||
        message.includes("model is unavailable") ||
        message.includes("model not supported") ||
        message.includes("deprecated model");
}

function isRetryableModelError(err) {
    const status = getGeminiErrorStatus(err);
    const message = String(err?.message || "").toLowerCase();

    return isUnavailableModelError(err) ||
        status === 503 ||
        message.includes("demand") ||
        message.includes("overloaded") ||
        message.includes("service unavailable");
}

function abortError(message) {
    const error = new Error(message);
    error.name = "AbortError";
    error.code = "ABORT_ERR";
    return error;
}

function throwIfAborted(signal, message) {
    if (signal?.aborted) throw abortError(message);
}

async function generateContentWithTimeout(client, request, signal) {
    let timeoutId;
    let onAbort;
    let onSignalAbort;
    const requestController = new AbortController();
    onAbort = () => requestController.abort();
    if (signal?.aborted) onAbort();
    else signal?.addEventListener("abort", onAbort, { once: true });

    const requestWithSignal = {
        ...request,
        config: {
            ...(request.config || {}),
            abortSignal: requestController.signal
        }
    };

    try {
        throwIfAborted(signal, "Gemini request cancelled");
        const abortPromise = signal
            ? new Promise((_, reject) => {
                onSignalAbort = () => reject(abortError("Gemini request cancelled"));
                signal.addEventListener("abort", onSignalAbort, { once: true });
            })
            : null;
        const response = await Promise.race([
            client.models.generateContent(requestWithSignal),
            new Promise((_, reject) => {
                timeoutId = setTimeout(() => {
                    requestController.abort();
                    const err = new Error("Gemini API request timed out. Please try again.");
                    err.status = 504;
                    err.code = "GEMINI_TIMEOUT";
                    reject(err);
                }, REQUEST_TIMEOUT_MS);
            }),
            ...(abortPromise ? [abortPromise] : [])
        ]);
        throwIfAborted(signal, "Gemini request cancelled");
        return response;
    } finally {
        clearTimeout(timeoutId);
        signal?.removeEventListener("abort", onAbort);
        signal?.removeEventListener("abort", onSignalAbort);
        requestController.abort();
    }
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Ask Gemini a single question and return the text answer.
 *
 * @param {string} question  Validated, trimmed question string.
 * @param {{ signal?: AbortSignal }} options
 * @returns {Promise<{ answer: string, model: string }>}
 */
async function askGemini(question, { signal } = {}) {
    throwIfAborted(signal, "Gemini request cancelled");
    const client = getClient();
    const candidateModels = getGeminiModelCandidates();

    const prompt = `You are a helpful, knowledgeable AI assistant. Answer the following question clearly and concisely.\n\nQuestion: ${question}`;

    let lastError = null;

    for (const modelName of candidateModels) {
        try {
            const response = await generateContentWithTimeout(client, {
                model: modelName,
                contents: prompt,
            }, signal);
            throwIfAborted(signal, "Gemini request cancelled");

            const answer = response?.text;

            if (answer && typeof answer === "string" && answer.trim() !== "") {
                return {
                    answer: answer.trim(),
                    model: modelName
                };
            }
        } catch (err) {
            if (signal?.aborted || err.name === "AbortError" || err.code === "ABORT_ERR") throw err;
            lastError = err;

            // An old/deprecated model commonly returns 404. Treat it like an
            // unavailable model and continue to a currently supported candidate.
            if (isRetryableModelError(err) && candidateModels.indexOf(modelName) < candidateModels.length - 1) {
                console.warn(`[GeminiService] Model ${modelName} is unavailable. Trying fallback model...`);
                continue;
            }

            // Otherwise map and throw
            _mapGeminiError(err);
        }
    }

    if (lastError) {
        _mapGeminiError(lastError);
    }

    const err = new Error("Gemini returned an empty response. Please rephrase your question.");
    err.status = 502;
    err.code = "GEMINI_EMPTY_RESPONSE";
    throw err;
}

/**
 * Generate a report from already collected evidence. The prompt deliberately
 * includes the evidence and citation identifiers so the model is used as a
 * grounded writer rather than as an unsourced search engine.
 */
async function askGroundedGemini({ query, analysis, evidence, factChecks, citations, verificationSummary, signal }) {
    throwIfAborted(signal, "Research report generation cancelled");
    const client = getClient();
    const modelName = getGeminiModel();
    const evidenceText = (evidence || []).slice(0, 40).map((item) =>
        `- [${item.id}] ${item.claim} | verification: ${item.verificationStatus || "pending"} | quote: ${item.quote} | source: ${item.sourceUrl}`
    ).join("\n");
    const citationText = (citations || []).map((item) =>
        `[${item.index}] ${item.title} — ${item.url}${item.isVerificationSource ? " (independent verification source)" : ""}`
    ).join("\n");
    const prompt = `You are the lead report writer in an autonomous research pipeline. Write an authoritative, grounded Markdown research report for the user query: "${query}"

Guidelines:
1. Executive Summary: High-level synthesis of findings with verified facts and methodology overview.
2. Key Findings: 4-7 specific findings. Every finding MUST include traceable citation markers like [1], [2].
3. Analysis & Cross-Source Insights: Comparative breakdown across dimensions, synthesizing multiple perspectives.
4. Fact Check: Explicitly present the fact-checked claims. Distinctly label each finding as either "VERIFIED (Corroborated by independent web sources)" or "SINGLE-SOURCE (Limitation: single perspective, lacks independent verification)" or "CONTRADICTED". Include citation markers.
5. Limitations & Risks: Transparently document single-source findings, potential biases, or data access limits.
6. Sources & Citations: Numbered list of all genuine sources [1], [2] with title and URL.

Verification Telemetry:
${JSON.stringify(verificationSummary || {}, null, 2)}

Analysis:
${JSON.stringify(analysis, null, 2)}

Evidence Extract:
${evidenceText || "No evidence was extracted."}

Fact-Check Results:
${JSON.stringify(factChecks || [], null, 2)}

Citation Index:
${citationText || "No citations available."}`;
    const response = await client.models.generateContent({
        model: modelName,
        contents: prompt,
        config: { temperature: 0.2, abortSignal: signal }
    });
    throwIfAborted(signal, "Research report generation cancelled");
    const text = response?.text;
    if (!text || !text.trim()) throw new Error("Gemini returned an empty report");
    return text.trim();
}

/**
 * Analyze extracted evidence using Gemini.
 * Synthesizes key findings, cross-source observations, trends, and executive summary.
 */
async function geminiAnalyzeEvidence({ query, evidence, sources, signal }) {
    throwIfAborted(signal, "Gemini analysis cancelled");
    const client = getClient();
    const modelName = getGeminiModel();

    const sampleEvidence = (evidence || []).slice(0, 30).map((e) => ({
        id: e.id,
        quote: e.quote,
        sourceTitle: e.sourceTitle,
        category: e.category,
        sourceUrl: e.sourceUrl
    }));

    const byCategory = (sources || []).reduce((res, s) => {
        const cat = s.category || s.sourceType || "web";
        res[cat] = (res[cat] || 0) + 1;
        return res;
    }, {});

    const prompt = `You are the Lead Analysis AI in an autonomous deep research pipeline.
Task: Analyze the verified evidence extracted from live web sources for this research query: "${query}".

Evidence items:
${JSON.stringify(sampleEvidence, null, 2)}

Categories covered:
${JSON.stringify(byCategory, null, 2)}

Provide a structured JSON output with this exact format:
{
  "findings": [
    {
      "topic": "category or topic name",
      "insight": "clear, factual insight grounded strictly in the evidence",
      "confidence": 0.85,
      "evidenceIds": ["evidence_1"]
    }
  ],
  "trends": [
    "key trend or consensus observed across the evidence"
  ],
  "comparisons": [
    {
      "dimension": "category or comparison axis",
      "observation": "comparative synthesis of evidence across sources"
    }
  ],
  "summary": "2-3 sentence executive synthesis of the findings grounded in the facts."
}

Rules:
- Base all insights strictly on the provided evidence quotes.
- Do not invent facts, companies, or figures not present in the evidence.
- Produce at least 3-6 distinct findings.`;

    const response = await client.models.generateContent({
        model: modelName,
        contents: prompt,
        config: {
            temperature: 0.2,
            responseMimeType: "application/json",
            abortSignal: signal
        }
    });
    throwIfAborted(signal, "Gemini analysis cancelled");
    const rawText = response?.text;
    if (!rawText) throw new Error("Gemini returned empty analysis response");
    const parsed = JSON.parse(rawText);
    return {
        findings: Array.isArray(parsed.findings) ? parsed.findings : [],
        trends: Array.isArray(parsed.trends) ? parsed.trends : [],
        comparisons: Array.isArray(parsed.comparisons) ? parsed.comparisons : [],
        summary: parsed.summary || `Synthesized analysis for query: ${query}`,
        evidenceCount: evidence.length,
        sourceCount: sources.length,
        highConfidenceCount: (parsed.findings || []).filter((f) => (f.confidence || 0) >= 0.7).length,
        engine: "gemini",
        model: modelName,
        analyzedAt: new Date()
    };
}

/**
 * Fact-check claims using Gemini as an Epistemic Fact-Checking Judge.
 * Evaluates claims against primary evidence and independent web search results.
 */
async function geminiFactCheckClaims({ query, claims, evidence, independentSources = [], heuristicChecks = [], signal }) {
    throwIfAborted(signal, "Gemini fact checking cancelled");
    const client = getClient();
    const modelName = getGeminiModel();

    const candidateClaims = (claims || []).slice(0, 10).map((c) => ({
        id: c.id,
        claim: c.claim || c.quote,
        sourceUrl: c.sourceUrl,
        sourceTitle: c.sourceTitle
    }));

    const independentList = (independentSources || []).slice(0, 10).map((s) => ({
        url: s.url,
        title: s.title,
        snippet: (s.snippet || s.content || "").slice(0, 300),
        provider: s.provider
    }));

    const prompt = `You are the Epistemic Fact-Checking Judge in an autonomous research system.
Evaluate the factual reliability and corroboration of the following claims extracted from web sources for the query: "${query}".

Candidate Claims:
${JSON.stringify(candidateClaims, null, 2)}

Independent Web Sources & Corroborating Pages:
${JSON.stringify(independentList, null, 2)}

For each claim:
1. Determine the status:
   - "verified": The claim is confirmed and corroborated by an independent web source (different domain/publisher from the primary source).
   - "single-source": The claim appears reliable in its primary source, but lacks independent second-source verification. (This is a valid finding with noted limitation).
   - "contradicted": There is conflicting or opposing data in other sources.
   - "unverified": The claim is speculative or lacks sufficient evidence.
2. Provide a 1-sentence "reasoning" explaining whether independent corroboration was found or why it is marked single-source.
3. List independentSourceUrls that corroborate the claim (from the independent sources list).
4. Assign confidence (0.40 - 0.98).

Return a JSON array of objects:
[
  {
    "claimId": "evidence_1",
    "claim": "text of claim",
    "status": "verified" | "single-source" | "contradicted" | "unverified",
    "confidence": 0.88,
    "reasoning": "Corroborated by independent reporting from...",
    "supported": true,
    "independentSourceUrls": ["https://..."]
  }
]`;

    const response = await client.models.generateContent({
        model: modelName,
        contents: prompt,
        config: {
            temperature: 0.1,
            responseMimeType: "application/json",
            abortSignal: signal
        }
    });
    throwIfAborted(signal, "Gemini fact checking cancelled");
    const rawText = response?.text;
    if (!rawText) throw new Error("Gemini returned empty fact-checking response");
    const parsed = JSON.parse(rawText);
    if (!Array.isArray(parsed) || parsed.length === 0) {
        throw new Error("Invalid format from Gemini fact-checker");
    }

    return parsed.map((item) => {
            const originalClaim = candidateClaims.find((c) => c.id === item.claimId || c.claim === item.claim) || {};
            const heuristic = (heuristicChecks || []).find((h) => h.claimId === item.claimId || h.claim === item.claim);
            const independentUrls = Array.isArray(item.independentSourceUrls) && item.independentSourceUrls.length > 0
                ? item.independentSourceUrls
                : (heuristic?.independentSourceUrls || []);
            const status = (item.status === "verified" && independentUrls.length === 0 && !heuristic?.independentSourceUrls?.length)
                ? "single-source"
                : (item.status || "single-source");

            return {
                claim: item.claim || originalClaim.claim,
                claimId: item.claimId || originalClaim.id,
                status,
                confidence: Number(item.confidence || 0.75),
                reasoning: item.reasoning || (status === "verified" ? "Independently verified across web sources." : "Single-source claim noted as a limitation."),
                supported: item.supported !== false,
                sourceUrls: [originalClaim.sourceUrl, ...independentUrls].filter(Boolean).filter((u, i, a) => a.indexOf(u) === i),
                independentSourceUrls: independentUrls,
                contradictionSourceUrls: item.status === "contradicted" ? (heuristic?.contradictionSourceUrls || []) : [],
                verificationMethod: "gemini_fact_checking",
                evaluatedBy: "gemini",
                geminiModel: modelName,
                verifiedAt: new Date()
            };
        });
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

/**
 * Map Gemini SDK / network errors to safe, user-visible errors.
 * Never leaks the API key or internal stack traces.
 * @param {Error} err
 */
function _mapGeminiError(err) {
    const msg = String(err?.message || "").toLowerCase();
    const status = getGeminiErrorStatus(err);

    // Invalid / expired key
    if (
        msg.includes("api key") ||
        msg.includes("api_key") ||
        msg.includes("invalid key") ||
        msg.includes("unauthorized") ||
        msg.includes("permission denied") ||
        status === 401 || status === 403
    ) {
        const e = new Error("Gemini API key is invalid or lacks permission. Contact the administrator.");
        e.status = 502;
        e.code = "GEMINI_AUTH_ERROR";
        throw e;
    }

    // Rate limit
    if (msg.includes("rate limit") || msg.includes("quota") || status === 429) {
        const e = new Error("Gemini API rate limit reached. Please wait a moment and try again.");
        e.status = 429;
        e.code = "GEMINI_RATE_LIMIT";
        throw e;
    }

    // Configured model was retired, renamed, or is not enabled for this API.
    if (isUnavailableModelError(err)) {
        const e = new Error("No configured Gemini model is currently available. Update GEMINI_MODEL or try again later.");
        e.status = 502;
        e.code = "GEMINI_MODEL_UNAVAILABLE";
        throw e;
    }

    // Overloaded / unavailable
    if (status === 503 || msg.includes("demand") || msg.includes("overloaded")) {
        const e = new Error("Gemini API is currently overloaded. Please retry in a few seconds.");
        e.status = 503;
        e.code = "GEMINI_SERVICE_UNAVAILABLE";
        throw e;
    }

    // Network / upstream unavailable
    if (
        msg.includes("network") ||
        msg.includes("econnrefused") ||
        msg.includes("enotfound") ||
        msg.includes("fetch failed")
    ) {
        const e = new Error("Could not reach the Gemini API. Check your network connection.");
        e.status = 503;
        e.code = "GEMINI_NETWORK_ERROR";
        throw e;
    }

    // Generic upstream error
    const e = new Error("Gemini API returned an error. Please try again later.");
    e.status = 502;
    e.code = "GEMINI_API_ERROR";
    throw e;
}

module.exports = {
    askGemini,
    askGroundedGemini,
    geminiAnalyzeEvidence,
    geminiFactCheckClaims,
    MAX_QUESTION_LENGTH,
    FALLBACK_MODELS,
    getGeminiModelCandidates,
    getGeminiModel,
};
