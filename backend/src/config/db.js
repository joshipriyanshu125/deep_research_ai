const mongoose = require("mongoose");
const dns = require("dns");

const RETRY_DELAY_MS = 5000;
let connectionAttempt = null;
let reconnectTimer = null;

// Use reliable DNS resolvers for MongoDB Atlas SRV lookups (_mongodb._tcp)
try {
    dns.setServers(["8.8.8.8", "8.8.4.4", "1.1.1.1"]);
} catch (e) {
    // Keep default DNS if setServers is unavailable
}

const scheduleReconnect = () => {
    if (reconnectTimer || process.env.NODE_ENV === "test") return;

    reconnectTimer = setTimeout(() => {
        reconnectTimer = null;
        connectDB();
    }, RETRY_DELAY_MS);
};

const connectDB = () => {
    if (mongoose.connection.readyState === 1) return Promise.resolve(true);
    if (connectionAttempt) return connectionAttempt;

    const uri = process.env.MONGODB_URL || process.env.MONGODB_URI || "mongodb://127.0.0.1:27017/deep_research_ai";

    connectionAttempt = mongoose.connect(uri, {
        // Fail quickly so the API can report a retryable 503 and keep
        // recovering when MongoDB starts after the Node process.
        serverSelectionTimeoutMS: 5000,
        connectTimeoutMS: 5000
    })
        .then(async () => {
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

            return true;
        })
        .catch((error) => {
            console.error("MongoDB connection failed; retrying:", error.message);
            scheduleReconnect();
            return false;
        })
        .finally(() => {
            connectionAttempt = null;
        });

    return connectionAttempt;
};

module.exports = connectDB;
