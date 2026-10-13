/**
 * AI Controller — Direct Quick Answer via Gemini
 *
 * Handles POST /api/ai/answer and the legacy alias
 * POST /api/v1/quick-answer that the frontend already calls.
 *
 * Follows the existing project conventions:
 *   - async/await + try/catch
 *   - { success, message, ... } response shape
 *   - Proper HTTP status codes
 *   - No internal error details exposed to the client
 */

const { askGemini, MAX_QUESTION_LENGTH } = require("../services/geminiService");

// ---------------------------------------------------------------------------
// POST /api/ai/answer  (also aliased to /api/v1/quick-answer)
// ---------------------------------------------------------------------------

/**
 * @desc   Send a question to Gemini and return a direct answer
 * @route  POST /api/ai/answer  |  POST /api/v1/quick-answer
 * @access Protected (JWT required — existing `protect` middleware applied in route)
 */
const getQuickAnswer = async (req, res) => {
    try {
        // ── 1. Validate input ──────────────────────────────────────────────
        let { question, query } = req.body;

        // Accept both "question" (new canonical field) and "query" (alias used
        // by the existing frontend quickAnswer() call in api/research.js).
        const raw = question || query;

        if (raw === undefined || raw === null) {
            return res.status(400).json({
                success: false,
                message: "Please provide a question."
            });
        }

        if (typeof raw !== "string") {
            return res.status(400).json({
                success: false,
                message: "Question must be a string."
            });
        }

        const trimmed = raw.trim();

        if (trimmed.length === 0) {
            return res.status(400).json({
                success: false,
                message: "Question cannot be empty."
            });
        }

        if (trimmed.length > MAX_QUESTION_LENGTH) {
            return res.status(400).json({
                success: false,
                message: `Question is too long. Maximum ${MAX_QUESTION_LENGTH} characters allowed.`
            });
        }

        // ── 2. Call Gemini ─────────────────────────────────────────────────
        // Pass client disconnects through to the SDK so a direct answer does
        // not keep running after the caller has gone away.
        const abortController = new AbortController();
        const onRequestAborted = () => abortController.abort();
        const onResponseClose = () => {
            if (!res.writableEnded) abortController.abort();
        };
        req.once?.("aborted", onRequestAborted);
        res.once?.("close", onResponseClose);
        if (req.aborted) abortController.abort();

        let answer;
        let model;
        try {
            ({ answer, model } = await askGemini(trimmed, { signal: abortController.signal }));
        } finally {
            req.removeListener?.("aborted", onRequestAborted);
            res.removeListener?.("close", onResponseClose);
        }

        // ── 3. Respond ─────────────────────────────────────────────────────
        // Return both the new canonical shape AND the fields the frontend
        // already inspects: data.mode, data.answer, data.model
        return res.status(200).json({
            success: true,
            mode: "quick",          // tells QueryInputCard this is a quick answer
            answer,
            model,
            question: trimmed
        });

    } catch (err) {
        if (err.name === "AbortError" || err.code === "ABORT_ERR" || req.aborted) return;
        // Log server-side (no sensitive data in message — geminiService already sanitised it)
        console.error(`[AI Controller] getQuickAnswer error: ${err.code || err.name} — ${err.message}`);

        const statusCode = err.status || 500;

        // Never expose internal stack traces
        return res.status(statusCode).json({
            success: false,
            message: err.message || "An unexpected error occurred. Please try again."
        });
    }
};

module.exports = {
    getQuickAnswer
};
