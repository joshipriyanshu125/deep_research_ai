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
const getGeminiModel = () => process.env.GEMINI_MODEL || "gemini-flash-lite-latest";

// Fallback models in case the primary configured model suffers transient overload (503)
const FALLBACK_MODELS = [
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
    "gemini-3.8-flash"
];

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

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Ask Gemini a single question and return the text answer.
 *
 * @param {string} question  Validated, trimmed question string.
 * @returns {Promise<{ answer: string, model: string }>}
 */
async function askGemini(question) {
    const client = getClient();
    const primaryModel = getGeminiModel();

    // Deduplicate candidate models starting with primary
    const candidateModels = [
        primaryModel,
        ...FALLBACK_MODELS.filter((m) => m !== primaryModel)
    ];

    const prompt = `You are a helpful, knowledgeable AI assistant. Answer the following question clearly and concisely.\n\nQuestion: ${question}`;

    let lastError = null;

    for (const modelName of candidateModels) {
        try {
            const timeoutPromise = new Promise((_, reject) => {
                setTimeout(() => {
                    const err = new Error("Gemini API request timed out. Please try again.");
                    err.status = 504;
                    err.code = "GEMINI_TIMEOUT";
                    reject(err);
                }, REQUEST_TIMEOUT_MS);
            });

            const geminiPromise = client.models.generateContent({
                model: modelName,
                contents: prompt,
            });

            const response = await Promise.race([geminiPromise, timeoutPromise]);
            const answer = response?.text;

            if (answer && typeof answer === "string" && answer.trim() !== "") {
                return {
                    answer: answer.trim(),
                    model: modelName
                };
            }
        } catch (err) {
            lastError = err;
            const status = err.status || err.code;
            const msg = (err.message || "").toLowerCase();

            // If it's a transient overload (503) or 404 on this specific model, try next candidate
            const isModelSpecific = status === 503 || status === 404 || msg.includes("demand") || msg.includes("not found");
            if (isModelSpecific && candidateModels.indexOf(modelName) < candidateModels.length - 1) {
                console.warn(`[GeminiService] Model ${modelName} returned status ${status}. Trying fallback model...`);
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
    const controller = new AbortController();
    const onAbort = () => controller.abort();
    signal?.addEventListener("abort", onAbort, { once: true });
    try {
        const response = await client.models.generateContent({
            model: modelName,
            contents: prompt,
            config: { temperature: 0.2 }
        });
        if (signal?.aborted) throw new Error("Research report generation cancelled");
        const text = response?.text;
        if (!text || !text.trim()) throw new Error("Gemini returned an empty report");
        return text.trim();
    } finally {
        signal?.removeEventListener?.("abort", onAbort);
        controller.abort();
    }
}

/**
 * Analyze extracted evidence using Gemini.
 * Synthesizes key findings, cross-source observations, trends, and executive summary.
 */
async function geminiAnalyzeEvidence({ query, evidence, sources, signal }) {
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

    const controller = new AbortController();
    const onAbort = () => controller.abort();
    signal?.addEventListener("abort", onAbort, { once: true });

    try {
        const response = await client.models.generateContent({
            model: modelName,
            contents: prompt,
            config: {
                temperature: 0.2,
                responseMimeType: "application/json"
            }
        });
        if (signal?.aborted) throw new Error("Gemini analysis cancelled");
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
    } finally {
        signal?.removeEventListener?.("abort", onAbort);
        controller.abort();
    }
}

/**
 * Fact-check claims using Gemini as an Epistemic Fact-Checking Judge.
 * Evaluates claims against primary evidence and independent web search results.
 */
async function geminiFactCheckClaims({ query, claims, evidence, independentSources = [], heuristicChecks = [], signal }) {
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

    const controller = new AbortController();
    const onAbort = () => controller.abort();
    signal?.addEventListener("abort", onAbort, { once: true });

    try {
        const response = await client.models.generateContent({
            model: modelName,
            contents: prompt,
            config: {
                temperature: 0.1,
                responseMimeType: "application/json"
            }
        });
        if (signal?.aborted) throw new Error("Gemini fact checking cancelled");
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
    } finally {
        signal?.removeEventListener?.("abort", onAbort);
        controller.abort();
    }
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
    const msg = (err.message || "").toLowerCase();
    const status = err.status || err.code;

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
    getGeminiModel,
};
