const mongoose = require("mongoose");

/**
 * Keep requests made while MongoDB is connecting from being buffered for
 * several seconds by Mongoose. The frontend can safely retry this response.
 */
const databaseReady = (req, res, next) => {
    if (mongoose.connection.readyState === 1) {
        return next();
    }

    res.set("Retry-After", "2");
    return res.status(503).json({
        success: false,
        message: "Backend is starting. Please retry in a moment."
    });
};

module.exports = databaseReady;
