const mongoose = require("mongoose");
const dns = require("dns");

// Use reliable DNS resolvers for MongoDB Atlas SRV lookups (_mongodb._tcp)
try {
    dns.setServers(["8.8.8.8", "8.8.4.4", "1.1.1.1"]);
} catch (e) {
    // Keep default DNS if setServers is unavailable
}

const connectDB = async () => {
    try {
        const uri = process.env.MONGODB_URL || process.env.MONGODB_URI || "mongodb://localhost:27017/deep_research_ai";
        await mongoose.connect(uri);

        console.log("MongoDB connected successfully");
    } catch (error) {
        console.error("MongoDB connection failed:", error.message);
        // Do not immediately crash the server on initial connection retry
        if (process.env.NODE_ENV === "production") {
            process.exit(1);
        }
    }
};

module.exports = connectDB;