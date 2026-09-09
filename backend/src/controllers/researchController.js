const Research = require("../models/Research");
const Report = require("../models/Report");

/**
 * @desc    Create new research project
 * @route   POST /research or POST /api/research
 * @access  Protected
 */
const createResearch = async (req, res) => {
    try {
        const { title, query, topic, depth, isPublic } = req.body;

        if (!title || !query) {
            return res.status(400).json({
                success: false,
                message: "Please provide a title and query for the research"
            });
        }

        const research = await Research.create({
            user: req.user._id,
            title,
            query,
            topic: topic || "",
            depth: depth || "standard",
            isPublic: !!isPublic,
            status: "pending"
        });

        return res.status(201).json({
            success: true,
            message: "Research created successfully",
            data: research
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to create research",
            error: error.message
        });
    }
};

/**
 * @desc    Get all research items
 *          - Regular user: returns ONLY their own research items
 *          - Admin: returns all research items (or filters by ?userId=...)
 * @route   GET /research or GET /api/research
 * @access  Protected
 */
const getAllResearch = async (req, res) => {
    try {
        let filter = {};

        if (req.user.role === "admin") {
            // Admin can view all or filter by specific user
            if (req.query.userId) {
                filter.user = req.query.userId;
            }
        } else {
            // Regular user: STRICT SCOPING TO OWNED RESOURCES
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
        // req.research is already attached and ownership-verified by checkOwnership middleware
        const research = req.research || (await Research.findById(req.params.id).populate("user", "name email role"));

        return res.status(200).json({
            success: true,
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
            "status",
            "depth",
            "findings",
            "sources",
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
            { new: true, runValidators: true }
        );

        return res.status(200).json({
            success: true,
            message: "Research updated successfully",
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
 * @desc    Delete research item and its reports (Resource-level authorization enforced)
 * @route   DELETE /research/:id
 * @access  Protected (Owner or Admin)
 */
const deleteResearch = async (req, res) => {
    try {
        const researchId = req.params.id;

        // Delete research
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
    deleteResearch
};
