const crypto = require("crypto");
const User = require("../models/User");
const {
    generateAccessToken,
    generateRefreshToken,
    verifyRefreshToken
} = require("../utils/token");

/**
 * @desc    Register a new user
 * @route   POST /auth/register or POST /api/auth/register
 * @access  Public
 */
const register = async (req, res) => {
    try {
        const { name, email, password, role } = req.body;

        // Validation
        if (!email || !password) {
            return res.status(400).json({
                success: false,
                message: "Please provide email and password"
            });
        }

        if (password.length < 6) {
            return res.status(400).json({
                success: false,
                message: "Password must be at least 6 characters long"
            });
        }

        // Check if user already exists
        const existingUser = await User.findOne({ email: email.toLowerCase() });
        if (existingUser) {
            return res.status(409).json({
                success: false,
                message: "User with this email already exists"
            });
        }

        // Create user (password will be automatically hashed by pre-save hook)
        const user = new User({
            name: name || "",
            email: email.toLowerCase(),
            password,
            role: role === "admin" ? "admin" : "user"
        });

        // Generate tokens
        const accessToken = generateAccessToken(user);
        const refreshToken = generateRefreshToken(user);

        // Save refresh token to user
        user.refreshToken = refreshToken;
        await user.save();

        return res.status(201).json({
            success: true,
            message: "User registered successfully",
            accessToken,
            refreshToken,
            user: {
                id: user._id,
                name: user.name,
                email: user.email,
                role: user.role,
                createdAt: user.createdAt
            }
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Registration failed",
            error: error.message
        });
    }
};

/**
 * @desc    Login user
 * @route   POST /auth/login or POST /api/auth/login
 * @access  Public
 */
const login = async (req, res) => {
    try {
        const { email, password } = req.body;

        // Validation
        if (!email || !password) {
            return res.status(400).json({
                success: false,
                message: "Please provide email and password"
            });
        }

        // Find user by email and explicitly select password & refreshToken fields
        const user = await User.findOne({ email: email.toLowerCase() }).select("+password +refreshToken");
        if (!user) {
            return res.status(401).json({
                success: false,
                message: "Invalid email or password"
            });
        }

        // Compare password
        const isMatch = await user.comparePassword(password);
        if (!isMatch) {
            return res.status(401).json({
                success: false,
                message: "Invalid email or password"
            });
        }

        // Generate new tokens
        const accessToken = generateAccessToken(user);
        const refreshToken = generateRefreshToken(user);

        // Update refresh token in DB
        user.refreshToken = refreshToken;
        await user.save();

        return res.status(200).json({
            success: true,
            message: "Login successful",
            accessToken,
            refreshToken,
            user: {
                id: user._id,
                name: user.name,
                email: user.email,
                role: user.role,
                createdAt: user.createdAt
            }
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Login failed",
            error: error.message
        });
    }
};

/**
 * @desc    Logout user / invalidate refresh token
 * @route   POST /auth/logout or POST /api/auth/logout
 * @access  Public / Protected
 */
const logout = async (req, res) => {
    try {
        const { refreshToken } = req.body || {};
        let userId = req.user ? req.user._id : null;

        if (userId) {
            // If authenticated via middleware
            await User.findByIdAndUpdate(userId, { refreshToken: null });
        } else if (refreshToken) {
            // If refresh token is supplied in body
            const decoded = verifyRefreshToken(refreshToken);
            if (decoded && decoded.id) {
                await User.findByIdAndUpdate(decoded.id, { refreshToken: null });
            } else {
                // Find by refreshToken string directly
                await User.findOneAndUpdate({ refreshToken }, { refreshToken: null });
            }
        }

        return res.status(200).json({
            success: true,
            message: "Logged out successfully"
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Logout failed",
            error: error.message
        });
    }
};

/**
 * @desc    Refresh Access Token using Refresh Token
 * @route   POST /auth/refresh or POST /api/auth/refresh
 * @access  Public
 */
const refresh = async (req, res) => {
    try {
        const refreshToken = req.body.refreshToken || req.headers["x-refresh-token"];

        if (!refreshToken) {
            return res.status(400).json({
                success: false,
                message: "Refresh token is required"
            });
        }

        // Verify refresh token signature & expiration
        const decoded = verifyRefreshToken(refreshToken);
        if (!decoded || !decoded.id) {
            return res.status(401).json({
                success: false,
                message: "Invalid or expired refresh token. Please log in again."
            });
        }

        // Check if user exists and stored refresh token matches
        const user = await User.findById(decoded.id).select("+refreshToken");
        if (!user || user.refreshToken !== refreshToken) {
            return res.status(401).json({
                success: false,
                message: "Refresh token is revoked or invalid. Please log in again."
            });
        }

        // Generate new access token and rotate refresh token
        const newAccessToken = generateAccessToken(user);
        const newRefreshToken = generateRefreshToken(user);

        // Update stored refresh token
        user.refreshToken = newRefreshToken;
        await user.save();

        return res.status(200).json({
            success: true,
            message: "Token refreshed successfully",
            accessToken: newAccessToken,
            refreshToken: newRefreshToken
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Token refresh failed",
            error: error.message
        });
    }
};

/**
 * @desc    Get currently logged in user profile
 * @route   GET /auth/me or GET /api/auth/me
 * @access  Protected
 */
const getMe = async (req, res) => {
    try {
        const user = req.user;

        return res.status(200).json({
            success: true,
            user: {
                id: user._id,
                name: user.name,
                email: user.email,
                role: user.role,
                createdAt: user.createdAt,
                updatedAt: user.updatedAt
            }
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Failed to get user profile",
            error: error.message
        });
    }
};

/**
 * @desc    Initiate forgot password request (generates reset token)
 * @route   POST /auth/forgot-password or POST /api/auth/forgot-password
 * @access  Public
 */
const forgotPassword = async (req, res) => {
    try {
        const { email } = req.body;

        if (!email) {
            return res.status(400).json({
                success: false,
                message: "Please provide an email address"
            });
        }

        const user = await User.findOne({ email: email.toLowerCase() });
        if (!user) {
            return res.status(404).json({
                success: false,
                message: "No user found with that email address"
            });
        }

        // Generate password reset token
        const resetToken = user.createPasswordResetToken();
        await user.save({ validateBeforeSave: false });

        return res.status(200).json({
            success: true,
            message: "Password reset token generated successfully. Valid for 15 minutes.",
            resetToken,
            instructions: "Send a POST request to /auth/reset-password with { resetToken, newPassword } to complete the password reset."
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Forgot password request failed",
            error: error.message
        });
    }
};

/**
 * @desc    Reset password using reset token
 * @route   POST /auth/reset-password or POST /api/auth/reset-password
 * @access  Public
 */
const resetPassword = async (req, res) => {
    try {
        const token = req.body.resetToken || req.body.token;
        const newPassword = req.body.newPassword || req.body.password;

        if (!token || !newPassword) {
            return res.status(400).json({
                success: false,
                message: "Please provide resetToken and newPassword"
            });
        }

        if (newPassword.length < 6) {
            return res.status(400).json({
                success: false,
                message: "New password must be at least 6 characters long"
            });
        }

        // Hash incoming reset token to match stored hash
        const hashedToken = crypto
            .createHash("sha256")
            .update(token)
            .digest("hex");

        // Find user with matching token and valid expiry
        const user = await User.findOne({
            resetPasswordToken: hashedToken,
            resetPasswordExpires: { $gt: Date.now() }
        }).select("+resetPasswordToken +resetPasswordExpires");

        if (!user) {
            return res.status(400).json({
                success: false,
                message: "Invalid or expired password reset token"
            });
        }

        // Set new password (pre-save hook will hash it)
        user.password = newPassword;
        user.resetPasswordToken = null;
        user.resetPasswordExpires = null;
        user.refreshToken = null; // Invalidate current sessions

        await user.save();

        return res.status(200).json({
            success: true,
            message: "Password reset successfully. Please log in with your new password."
        });
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Password reset failed",
            error: error.message
        });
    }
};

module.exports = {
    register,
    login,
    logout,
    refresh,
    getMe,
    forgotPassword,
    resetPassword
};
