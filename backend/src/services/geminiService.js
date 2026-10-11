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
async function askGroundedGemini({ query, analysis, evidence, factChecks, citations, signal }) {
    const client = getClient();
    const modelName = getGeminiModel();
    const evidenceText = (evidence || []).slice(0, 40).map((item) =>
        `- [${item.id}] ${item.claim} | quote: ${item.quote} | source: ${item.sourceUrl}`
    ).join("\n");
    const citationText = (citations || []).map((item) => `[${item.index}] ${item.title} — ${item.url}`).join("\n");
    const prompt = `You are the report writer in a research pipeline. Write a balanced Markdown report for this query: ${query}

Rules: use only the evidence supplied below; do not invent facts or citations; mark single-source or unverified claims as limitations; include inline citation markers such as [1]; include sections Executive Summary, Key Findings, Analysis, Fact Check, Limitations, and Sources & Citations.

Analysis:
${JSON.stringify(analysis)}

Evidence:
${evidenceText || "No evidence was extracted."}

Fact checks:
${JSON.stringify(factChecks || [])}

Citation index:
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
    MAX_QUESTION_LENGTH,
    getGeminiModel,
};
