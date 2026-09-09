const jwt = require("jsonwebtoken");

const ACCESS_SECRET = process.env.JWT_ACCESS_SECRET || "default_access_secret_key_deep_research";
const REFRESH_SECRET = process.env.JWT_REFRESH_SECRET || "default_refresh_secret_key_deep_research";
const ACCESS_EXPIRES_IN = process.env.JWT_ACCESS_EXPIRES_IN || "15m";
const REFRESH_EXPIRES_IN = process.env.JWT_REFRESH_EXPIRES_IN || "7d";

/**
 * Generate short-lived Access Token (JWT)
 */
const generateAccessToken = (user) => {
    return jwt.sign(
        {
            id: user._id || user.id,
            email: user.email,
            role: user.role
        },
        ACCESS_SECRET,
        {
            expiresIn: ACCESS_EXPIRES_IN
        }
    );
};

/**
 * Generate long-lived Refresh Token (JWT)
 */
const generateRefreshToken = (user) => {
    return jwt.sign(
        {
            id: user._id || user.id
        },
        REFRESH_SECRET,
        {
            expiresIn: REFRESH_EXPIRES_IN
        }
    );
};

/**
 * Verify Access Token
 */
const verifyAccessToken = (token) => {
    try {
        return jwt.verify(token, ACCESS_SECRET);
    } catch (error) {
        return null;
    }
};

/**
 * Verify Refresh Token
 */
const verifyRefreshToken = (token) => {
    try {
        return jwt.verify(token, REFRESH_SECRET);
    } catch (error) {
        return null;
    }
};

module.exports = {
    generateAccessToken,
    generateRefreshToken,
    verifyAccessToken,
    verifyRefreshToken,
    ACCESS_SECRET,
    REFRESH_SECRET
};
