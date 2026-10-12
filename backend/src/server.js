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
app.get("/", (req, res) => {
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

app.get("/health", (req, res) => {
    const databaseConnected = mongoose.connection.readyState === 1;
    res.status(databaseConnected ? 200 : 503).json({
        status: databaseConnected ? "ok" : "starting",
        database: databaseConnected ? "connected" : "connecting"
    });
});

// Mount Routes (mounted at both standard and /api/ prefixed paths)
app.use("/auth", databaseReady, authRoutes);
app.use("/api/auth", databaseReady, authRoutes);

app.use("/research", researchRoutes);
app.use("/api/research", researchRoutes);

app.use("/reports", reportRoutes);
app.use("/api/reports", reportRoutes);

app.use("/admin", adminRoutes);
app.use("/api/admin", adminRoutes);

// ── Gemini Quick Answer routes ───────────────────────────────────────────────
// Canonical endpoint:  POST /api/ai/answer
// Frontend alias:      POST /api/v1/quick-answer  (matches api/research.js quickAnswer())
app.use("/ai", aiRoutes);
app.use("/api/ai", aiRoutes);
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

if (process.env.NODE_ENV !== "test") {
    app.listen(PORT, "127.0.0.1", () => {
        console.log(`Server running on http://127.0.0.1:${PORT}`);
    });
}

module.exports = app;
