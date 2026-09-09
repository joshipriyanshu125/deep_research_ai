const express = require("express");
const router = express.Router();
const {
    createResearch,
    getAllResearch,
    getResearchById,
    updateResearch,
    deleteResearch
} = require("../controllers/researchController");
const { protect } = require("../middleware/authMiddleware");
const { checkOwnership } = require("../middleware/authorize");
const Research = require("../models/Research");

// All research routes require authentication
router.use(protect);

router.post("/", createResearch);
router.get("/", getAllResearch);

// Resource-level authorization: User must own the research, or be an admin
router.get("/:id", checkOwnership(Research, "id", "research"), getResearchById);
router.put("/:id", checkOwnership(Research, "id"), updateResearch);
router.patch("/:id", checkOwnership(Research, "id"), updateResearch);
router.delete("/:id", checkOwnership(Research, "id"), deleteResearch);

module.exports = router;
