const express = require("express");
const router = express.Router();
const {
    register,
    login,
    logout,
    refresh,
    getMe,
    forgotPassword,
    resetPassword
} = require("../controllers/authController");
const { protect } = require("../middleware/authMiddleware");

// Authentication routes
router.post("/register", register);
router.post("/login", login);
router.post("/logout", logout);
router.post("/refresh", refresh);
router.get("/me", protect, getMe);
router.post("/forgot-password", forgotPassword);
router.post("/reset-password", resetPassword);

module.exports = router;
