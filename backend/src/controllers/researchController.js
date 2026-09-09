const Research = require("../models/Research");
const Report = require("../models/Report");
const researchQueue = require("../services/researchQueue");

/**
 * @desc    Create and enqueue a new research job
 * @route   POST /research or POST /api/research
 * @access  Protected
 */
const createResearch = async (req, res) => {
    try {
        const { query, title, topic, depth, isPublic } = req.body;

        if (!query) {
            return res.status(400).json({
                success: false,
                message: "Please provide a query for the research"
            });
        }

        const generatedTitle =
            title ||
            (query.length > 80 ? query.substring(0, 77) + "..." : query);

        // 1. Create research record with 'queued' status
        const research = await Research.create({
            user: req.user._id,
            query: query.trim(),
            title: generatedTitle,
            topic: topic || "",
            depth: depth || "standard",
            isPublic: !!isPublic,
            status: "queued",
            progress: 0,
            currentStep: "Queued for background processing"
        });

        // 2. Enqueue for background execution (does NOT block the HTTP request)
        await researchQueue.enqueue(research._id);

        // 3. Respond immediately with status 201
        return res.status(201).json({
            success: true,
            message: "Research job queued successfully",
            research_id: research._id.toString(),
            id: research._id.toString(),
            status: research.status,
            query: research.query,
            title: research.title,
            progress: research.progress,
            currentStep: research.currentStep,
            createdAt: research.createdAt,
            data: research
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to create research job",
            error: error.message
        });
    }
};

/**
 * @desc    Get all research items (scoped to logged-in user, or all for admin)
 * @route   GET /research or GET /api/research
 * @access  Protected
 */
const getAllResearch = async (req, res) => {
    try {
        let filter = {};

        if (req.user.role === "admin") {
            if (req.query.userId) {
                filter.user = req.query.userId;
            }
        } else {
            filter.user = req.user._id;
        }

        const researches = await Research.find(filter)
            .populate("user", "name email role")
            .sort({ createdAt: -1 });

        return res.status(200).json({
            success: true,
            count: researches.length,
            data: researches
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to fetch research items",
            error: error.message
        });
    }
};

/**
 * @desc    Get single research item by ID (Resource-level authorization enforced)
 * @route   GET /research/:id or GET /api/research/:id
 * @access  Protected (Owner or Admin)
 */
const getResearchById = async (req, res) => {
    try {
        const research =
            req.research ||
            (await Research.findById(req.params.id).populate(
                "user",
                "name email role"
            ));

        return res.status(200).json({
            success: true,
            research_id: research._id.toString(),
            id: research._id.toString(),
            status: research.status,
            query: research.query,
            progress: research.progress,
            currentStep: research.currentStep,
            data: research
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to fetch research item",
            error: error.message
        });
    }
};

/**
 * @desc    Update research item (Resource-level authorization enforced)
 * @route   PUT /research/:id or PATCH /research/:id
 * @access  Protected (Owner or Admin)
 */
const updateResearch = async (req, res) => {
    try {
        const allowedUpdates = [
            "title",
            "topic",
            "query",
            "depth",
            "isPublic"
        ];
        const updates = {};

        for (const key of allowedUpdates) {
            if (req.body[key] !== undefined) {
                updates[key] = req.body[key];
            }
        }

        const updatedResearch = await Research.findByIdAndUpdate(
            req.params.id,
            { $set: updates },
            { returnDocument: "after", runValidators: true }
        );

        return res.status(200).json({
            success: true,
            message: "Research updated successfully",
            research_id: updatedResearch._id.toString(),
            id: updatedResearch._id.toString(),
            data: updatedResearch
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to update research",
            error: error.message
        });
    }
};

/**
 * @desc    Cancel an ongoing or queued research job
 * @route   POST /research/:id/cancel or POST /api/research/:id/cancel
 * @access  Protected (Owner or Admin)
 */
const cancelResearch = async (req, res) => {
    try {
        const researchId = req.params.id;

        const cancelled = await researchQueue.cancel(researchId);

        return res.status(200).json({
            success: true,
            message: "Research job cancelled successfully",
            research_id: researchId,
            id: researchId,
            status: "cancelled",
            data: cancelled
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to cancel research job",
            error: error.message
        });
    }
};

/**
 * @desc    Resume a cancelled, paused, or failed research job
 * @route   POST /research/:id/resume or POST /api/research/:id/resume
 * @access  Protected (Owner or Admin)
 */
const resumeResearch = async (req, res) => {
    try {
        const researchId = req.params.id;

        const resumed = await researchQueue.resume(researchId);

        return res.status(200).json({
            success: true,
            message: "Research job resumed and queued for processing",
            research_id: researchId,
            id: researchId,
            status: resumed.status,
            data: resumed
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to resume research job",
            error: error.message
        });
    }
};

/**
 * @desc    Delete research item and associated reports
 * @route   DELETE /research/:id or DELETE /api/research/:id
 * @access  Protected (Owner or Admin)
 */
const deleteResearch = async (req, res) => {
    try {
        const researchId = req.params.id;

        // Cancel background job if running
        await researchQueue.cancel(researchId);

        // Delete research document
        await Research.findByIdAndDelete(researchId);

        // Delete associated reports
        await Report.deleteMany({ research: researchId });

        return res.status(200).json({
            success: true,
            message: "Research and associated reports deleted successfully"
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to delete research",
            error: error.message
        });
    }
};

module.exports = {
    createResearch,
    getAllResearch,
    getResearchById,
    updateResearch,
    cancelResearch,
    resumeResearch,
    deleteResearch
};
