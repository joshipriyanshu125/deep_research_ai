/**
 * AI Routes — Direct Quick Answer
 *
 * Mounted in server.js at:
 *   /ai          → /ai/answer
 *   /api/ai      → /api/ai/answer       (primary canonical endpoint)
 *   /api/v1/quick-answer                (legacy alias — matches the existing
 *                                        frontend call in api/research.js)
 *
 * All routes require a valid JWT (the existing `protect` middleware).
 */

const express = require("express");
const router = express.Router();
const { getQuickAnswer } = require("../controllers/aiController");
const { protect } = require("../middleware/authMiddleware");

// Protect all AI routes — uses the same JWT middleware as all other routes
router.use(protect);

/**
 * POST /answer
 * (full path after mount: /api/ai/answer)
 * Body: { question: "..." }  or  { query: "..." }
 */
router.post("/answer", getQuickAnswer);

/**
 * POST /quick-answer
 * Alias so that POST /api/v1/quick-answer (called by the existing frontend
 * api/research.js quickAnswer() function) also resolves correctly.
 * Mounted at /api/v1 in server.js.
 */
router.post("/", getQuickAnswer);

module.exports = router;
