require("dotenv").config();

const express = require("express");
const connectDB = require("./config/db");
const authRoutes = require("./routes/authRoutes");
const researchRoutes = require("./routes/researchRoutes");
const reportRoutes = require("./routes/reportRoutes");
const adminRoutes = require("./routes/adminRoutes");
const aiRoutes = require("./routes/aiRoutes");
const databaseReady = require("./middleware/databaseReady");
const mongoose = require("mongoose");

const app = express();

// Body Parser Middleware
app.use(express.json());
app.use(express.urlencoded({ extended: true }));

// Connect MongoDB
connectDB();

// Root route
app.get(["/", "/api"], (req, res) => {
    res.json({
        message: "Deep Research AI Backend is running",
        version: "1.0.0",
        endpoints: {
            auth: "/auth",
            research: "/research",
            reports: "/reports",
            admin: "/admin"
        }
    });
});

app.get(["/health", "/api/health"], (req, res) => {
    const databaseConnected = mongoose.connection.readyState === 1;
    res.status(databaseConnected ? 200 : 503).json({
        status: databaseConnected ? "ok" : "starting",
        database: databaseConnected ? "connected" : "connecting",
        gemini: {
            configured: Boolean(process.env.GEMINI_API_KEY),
            model: process.env.GEMINI_MODEL || "gemini-flash-lite-latest",
            integration: "active",
            sdk: "@google/genai",
            capabilities: ["direct_answers", "evidence_analysis", "epistemic_fact_checking", "grounded_synthesis"]
        },
        searchProviders: {
            tavily: Boolean(process.env.TAVILY_API_KEY),
            serper: Boolean(process.env.SERPER_API_KEY),
            duckduckgo: true,
            googleNews: true,
            wikipedia: true,
            openalex: true,
            crossref: true,
            liveSearchEnabled: process.env.RESEARCH_LIVE_SEARCH !== "false"
        },
        pipeline: [
            { stage: 1, name: "User Research Query & Planner", status: "active" },
            { stage: 2, name: "Multi-Track Web Search", status: "active" },
            { stage: 3, name: "Source Extraction & Evidence Harvesting", status: "active" },
            { stage: 4, name: "Gemini Analysis & Fact-Checking", status: "active" },
            { stage: 5, name: "Citation Mapping & Structured Report", status: "active" },
            { stage: 6, name: "Deep Research Report UI", status: "active" }
        ]
    });
});

// Mount Routes (mounted at standard, /api/, and /api/v1/ prefixed paths)
app.use("/auth", databaseReady, authRoutes);
app.use("/api/auth", databaseReady, authRoutes);
app.use("/api/v1/auth", databaseReady, authRoutes);

app.use("/research", databaseReady, researchRoutes);
app.use("/api/research", databaseReady, researchRoutes);
app.use("/api/v1/research", databaseReady, researchRoutes);

app.use("/reports", databaseReady, reportRoutes);
app.use("/api/reports", databaseReady, reportRoutes);
app.use("/api/v1/reports", databaseReady, reportRoutes);

app.use("/admin", adminRoutes);
app.use("/api/admin", adminRoutes);
app.use("/api/v1/admin", adminRoutes);

// ── Gemini Quick Answer routes ───────────────────────────────────────────────
// Canonical endpoint:  POST /api/ai/answer
// Frontend alias:      POST /api/v1/quick-answer  (matches api/research.js quickAnswer())
app.use("/ai", aiRoutes);
app.use("/api/ai", aiRoutes);
app.use("/api/v1/ai", aiRoutes);
app.use("/api/v1/quick-answer", aiRoutes);

// 404 Handler
app.use((req, res, next) => {
    res.status(404).json({
        success: false,
        message: `Route ${req.originalUrl} not found`
    });
});

// Global Error Handler
app.use((err, req, res, next) => {
    console.error("Server Error:", err.stack || err.message);
    res.status(err.status || 500).json({
        success: false,
        message: err.message || "Internal Server Error"
    });
});

const PORT = process.env.PORT || 5000;

// The research queue is in-memory, so any interrupted (in-flight) document
// must be re-queued once the process is up and MongoDB is reachable. This runs
// on every successful (re)connection so a database that comes up after the
// server also releases stalled jobs.
function startResearchRecovery() {
    const researchQueue = require("./queue/researchQueue");
    const recover = () => {
        researchQueue.recoverInterruptedJobs().catch((error) => {
            console.error("[ResearchQueue] Recovery failed:", error.message);
        });
    };

    if (mongoose.connection.readyState === 1) recover();
    else mongoose.connection.on("connected", recover);
}

if (process.env.NODE_ENV !== "test" && require.main === module) {
    app.listen(PORT, "0.0.0.0", () => {
        console.log(`Server running on http://127.0.0.1:${PORT} and http://localhost:${PORT}`);
        startResearchRecovery();
    });
}

module.exports = app;
