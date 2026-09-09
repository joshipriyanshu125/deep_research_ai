const Report = require("../models/Report");
const Research = require("../models/Research");
const { isOwnerOrAdmin } = require("../middleware/authorize");

/**
 * @desc    Create a new research report
 * @route   POST /reports or POST /api/reports
 * @access  Protected
 */
const createReport = async (req, res) => {
    try {
        const { researchId, title, summary, content, sections, citations, isPublic } = req.body;

        if (!researchId || !title || !content) {
            return res.status(400).json({
                success: false,
                message: "Please provide researchId, title, and content"
            });
        }

        // Verify research exists
        const research = await Research.findById(researchId);
        if (!research) {
            return res.status(404).json({
                success: false,
                message: "Research item not found"
            });
        }

        // Verify user owns the research item or is admin
        if (!isOwnerOrAdmin(research, req.user)) {
            return res.status(403).json({
                success: false,
                message: "Forbidden: You cannot create a report for research that you do not own"
            });
        }

        const report = await Report.create({
            user: req.user._id,
            research: researchId,
            title,
            summary: summary || "",
            content,
            sections: sections || [],
            citations: citations || [],
            isPublic: !!isPublic
        });

        return res.status(201).json({
            success: true,
            message: "Report created successfully",
            data: report
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to create report",
            error: error.message
        });
    }
};

/**
 * @desc    Get all reports (scoped to current user, or all for admin)
 * @route   GET /reports or GET /api/reports
 * @access  Protected
 */
const getAllReports = async (req, res) => {
    try {
        let filter = {};

        if (req.user.role === "admin") {
            if (req.query.userId) {
                filter.user = req.query.userId;
            }
        } else {
            filter.user = req.user._id;
        }

        const reports = await Report.find(filter)
            .populate("user", "name email role")
            .populate("research", "title query status")
            .sort({ createdAt: -1 });

        return res.status(200).json({
            success: true,
            count: reports.length,
            data: reports
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to fetch reports",
            error: error.message
        });
    }
};

/**
 * @desc    Get single report by ID (Resource-level authorization enforced)
 * @route   GET /reports/:id or GET /api/reports/:id
 * @access  Protected (Owner or Admin)
 */
const getReportById = async (req, res) => {
    try {
        const report = req.report || (await Report.findById(req.params.id)
            .populate("user", "name email role")
            .populate("research", "title query status"));

        return res.status(200).json({
            success: true,
            data: report
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to fetch report",
            error: error.message
        });
    }
};

/**
 * @desc    Delete report (Resource-level authorization enforced)
 * @route   DELETE /reports/:id
 * @access  Protected (Owner or Admin)
 */
const deleteReport = async (req, res) => {
    try {
        await Report.findByIdAndDelete(req.params.id);

        return res.status(200).json({
            success: true,
            message: "Report deleted successfully"
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to delete report",
            error: error.message
        });
    }
};

module.exports = {
    createReport,
    getAllReports,
    getReportById,
    deleteReport
};
