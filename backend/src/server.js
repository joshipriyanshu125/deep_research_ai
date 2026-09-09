require("dotenv").config();

const express = require("express");
const connectDB = require("./config/db");
const authRoutes = require("./routes/authRoutes");
const researchRoutes = require("./routes/researchRoutes");
const reportRoutes = require("./routes/reportRoutes");
const adminRoutes = require("./routes/adminRoutes");

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

// Mount Routes (mounted at both standard and /api/ prefixed paths)
app.use("/auth", authRoutes);
app.use("/api/auth", authRoutes);

app.use("/research", researchRoutes);
app.use("/api/research", researchRoutes);

app.use("/reports", reportRoutes);
app.use("/api/reports", reportRoutes);

app.use("/admin", adminRoutes);
app.use("/api/admin", adminRoutes);

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
    app.listen(PORT, () => {
        console.log(`Server running on port ${PORT}`);
    });
}

module.exports = app;