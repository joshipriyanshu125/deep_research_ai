const express = require("express");
const router = express.Router();
const {
    getAllUsers,
    updateUserRole,
    deleteUser,
    getSystemStats
} = require("../controllers/adminController");
const { protect } = require("../middleware/authMiddleware");
const { restrictTo } = require("../middleware/authorize");

// Admin routes: Require authentication AND 'admin' role
router.use(protect);
router.use(restrictTo("admin"));

router.get("/users", getAllUsers);
router.patch("/users/:id/role", updateUserRole);
router.delete("/users/:id", deleteUser);
router.get("/stats", getSystemStats);

module.exports = router;
