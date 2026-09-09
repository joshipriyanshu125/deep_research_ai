const User = require("../models/User");
const Research = require("../models/Research");
const Report = require("../models/Report");

/**
 * @desc    Get all registered users (Admin only)
 * @route   GET /admin/users or GET /api/admin/users
 * @access  Protected (Admin only)
 */
const getAllUsers = async (req, res) => {
    try {
        const users = await User.find().select("-password").sort({ createdAt: -1 });

        return res.status(200).json({
            success: true,
            count: users.length,
            data: users
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to fetch users",
            error: error.message
        });
    }
};

/**
 * @desc    Change user role (Admin only)
 * @route   PATCH /admin/users/:id/role
 * @access  Protected (Admin only)
 */
const updateUserRole = async (req, res) => {
    try {
        const { role } = req.body;

        if (!role || !["user", "admin"].includes(role)) {
            return res.status(400).json({
                success: false,
                message: "Please provide a valid role: 'user' or 'admin'"
            });
        }

        const user = await User.findByIdAndUpdate(
            req.params.id,
            { role },
            { new: true, runValidators: true }
        ).select("-password");

        if (!user) {
            return res.status(404).json({
                success: false,
                message: "User not found"
            });
        }

        return res.status(200).json({
            success: true,
            message: `User role updated to ${role}`,
            data: user
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to update user role",
            error: error.message
        });
    }
};

/**
 * @desc    Delete user and cascade delete their data (Admin only)
 * @route   DELETE /admin/users/:id
 * @access  Protected (Admin only)
 */
const deleteUser = async (req, res) => {
    try {
        const userId = req.params.id;

        const user = await User.findByIdAndDelete(userId);
        if (!user) {
            return res.status(404).json({
                success: false,
                message: "User not found"
            });
        }

        // Delete all research and reports created by this user
        await Research.deleteMany({ user: userId });
        await Report.deleteMany({ user: userId });

        return res.status(200).json({
            success: true,
            message: "User and all associated data deleted successfully"
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to delete user",
            error: error.message
        });
    }
};

/**
 * @desc    Get system overview / statistics (Admin only)
 * @route   GET /admin/stats
 * @access  Protected (Admin only)
 */
const getSystemStats = async (req, res) => {
    try {
        const totalUsers = await User.countDocuments();
        const totalResearch = await Research.countDocuments();
        const totalReports = await Report.countDocuments();

        return res.status(200).json({
            success: true,
            stats: {
                totalUsers,
                totalResearch,
                totalReports
            }
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to fetch stats",
            error: error.message
        });
    }
};

module.exports = {
    getAllUsers,
    updateUserRole,
    deleteUser,
    getSystemStats
};
