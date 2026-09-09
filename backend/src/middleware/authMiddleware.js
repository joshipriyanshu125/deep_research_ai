const jwt = require("jsonwebtoken");
const User = require("../models/User");
const { ACCESS_SECRET } = require("../utils/token");

/**
 * Authentication Middleware: Protect routes and verify JWT Access Token
 */
const protect = async (req, res, next) => {
    try {
        let token;

        // Check Authorization header for Bearer token
        if (
            req.headers.authorization &&
            req.headers.authorization.startsWith("Bearer ")
        ) {
            token = req.headers.authorization.split(" ")[1];
        } else if (req.cookies && req.cookies.accessToken) {
            token = req.cookies.accessToken;
        }

        if (!token) {
            return res.status(401).json({
                success: false,
                message: "Not authorized to access this route. Please provide a valid Bearer token."
            });
        }

        try {
            // Verify access token
            const decoded = jwt.verify(token, ACCESS_SECRET);

            // Fetch user from DB (excluding password)
            const user = await User.findById(decoded.id);

            if (!user) {
                return res.status(401).json({
                    success: false,
                    message: "User associated with this token no longer exists."
                });
            }

            // Attach user to request object
            req.user = user;
            next();
        } catch (jwtError) {
            if (jwtError.name === "TokenExpiredError") {
                return res.status(401).json({
                    success: false,
                    message: "Access token has expired. Please refresh your token."
                });
            }
            return res.status(401).json({
                success: false,
                message: "Invalid token. Authorization denied."
            });
        }
    } catch (error) {
        return res.status(500).json({
            success: false,
            message: "Authentication error",
            error: error.message
        });
    }
};

module.exports = {
    protect
};
