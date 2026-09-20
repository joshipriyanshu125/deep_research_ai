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

        // Clean up legacy id indexes across collections if present
        try {
            const db = mongoose.connection.db;
            const collections = await db.listCollections().toArray();
            for (const col of collections) {
                const collection = db.collection(col.name);
                const indexes = await collection.indexes();
                for (const idx of indexes) {
                    if (
                        idx.name !== "_id_" &&
                        (idx.key?.id !== undefined || idx.name.includes("id_unique") || idx.name.includes("_id_unique"))
                    ) {
                        await collection.dropIndex(idx.name);
                        console.log(`Auto-cleaned legacy index on [${col.name}]: ${idx.name}`);
                    }
                }
            }
        } catch (idxErr) {
            // Non-fatal if index scan fails
        }
    } catch (error) {
        console.error("MongoDB connection failed:", error.message);
        if (process.env.NODE_ENV === "production") {
            process.exit(1);
        }
    }
};

module.exports = connectDB;