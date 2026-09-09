const express = require("express");
const router = express.Router();
const {
    createReport,
    getAllReports,
    getReportById,
    deleteReport
} = require("../controllers/reportController");
const { protect } = require("../middleware/authMiddleware");
const { checkOwnership } = require("../middleware/authorize");
const Report = require("../models/Report");

// All report routes require authentication
router.use(protect);

router.post("/", createReport);
router.get("/", getAllReports);

// Resource-level authorization: User must own the report, or be an admin
router.get("/:id", checkOwnership(Report, "id", "report"), getReportById);
router.delete("/:id", checkOwnership(Report, "id"), deleteReport);

module.exports = router;
