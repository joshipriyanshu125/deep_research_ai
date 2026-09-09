/**
 * Role-Based Access Control (RBAC) Middleware
 * Restricts access to specific user roles (e.g. 'admin', 'user')
 */
const restrictTo = (...roles) => {
    return (req, res, next) => {
        if (!req.user) {
            return res.status(401).json({
                success: false,
                message: "Authentication required. Please log in."
            });
        }

        if (!roles.includes(req.user.role)) {
            return res.status(403).json({
                success: false,
                message: `Forbidden: Access denied. Required role: [${roles.join(", ")}]. Your role: [${req.user.role}].`
            });
        }

        next();
    };
};

/**
 * Resource Ownership Validation Middleware
 * Ensures only the owner of a resource or an Admin can access / modify it
 *
 * @param {Mongoose.Model} Model - The Mongoose model to query
 * @param {string} idParam - The URL param name containing resource ID (default: 'id')
 * @param {string} attachName - Property name to attach document on `req` (default: 'resource')
 */
const checkOwnership = (Model, idParam = "id", attachName = "resource") => {
    return async (req, res, next) => {
        try {
            const resourceId = req.params[idParam];

            if (!resourceId) {
                return res.status(400).json({
                    success: false,
                    message: `Missing parameter :${idParam}`
                });
            }

            const resource = await Model.findById(resourceId);

            if (!resource) {
                return res.status(404).json({
                    success: false,
                    message: `${Model.modelName || "Resource"} not found`
                });
            }

            // Check if user is authenticated
            if (!req.user) {
                return res.status(401).json({
                    success: false,
                    message: "Authentication required"
                });
            }

            // Authorization: Admin can access anything, or user must be the resource owner
            const isOwner = resource.user && resource.user.toString() === req.user._id.toString();
            const isAdmin = req.user.role === "admin";

            if (!isOwner && !isAdmin) {
                return res.status(403).json({
                    success: false,
                    message: "Forbidden: You do not have permission to access or modify this resource"
                });
            }

            // Attach resource to req for controller reuse
            req[attachName] = resource;
            next();
        } catch (error) {
            // Handle invalid ObjectId format
            if (error.name === "CastError") {
                return res.status(404).json({
                    success: false,
                    message: `${Model.modelName || "Resource"} not found`
                });
            }
            return res.status(500).json({
                success: false,
                message: "Authorization check error",
                error: error.message
            });
        }
    };
};

/**
 * Utility helper function to verify ownership programmatically
 */
const isOwnerOrAdmin = (resource, user) => {
    if (!resource || !user) return false;
    if (user.role === "admin") return true;
    return resource.user && resource.user.toString() === user._id.toString();
};

module.exports = {
    restrictTo,
    checkOwnership,
    isOwnerOrAdmin
};
