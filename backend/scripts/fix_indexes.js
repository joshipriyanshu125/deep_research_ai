require("dotenv").config();
const mongoose = require("mongoose");

async function fix() {
  const uri = process.env.MONGODB_URL || process.env.MONGODB_URI;
  console.log("Connecting to MongoDB...");
  await mongoose.connect(uri);
  console.log("Connected.");

  const db = mongoose.connection.db;
  const collections = await db.listCollections().toArray();
  console.log("Found collections:", collections.map(c => c.name));

  for (const col of collections) {
    const name = col.name;
    try {
      const collection = db.collection(name);
      const indexes = await collection.indexes();
      console.log(`\nIndexes for collection [${name}]:`, JSON.stringify(indexes, null, 2));

      for (const idx of indexes) {
        if (
          idx.name !== "_id_" &&
          (idx.key.id !== undefined || idx.name.includes("id_unique") || idx.name.includes("_id_unique"))
        ) {
          console.log(`-> Dropping legacy index on [${name}]: ${idx.name}`);
          await collection.dropIndex(idx.name);
          console.log(`✓ Dropped index: ${idx.name}`);
        }
      }
    } catch (err) {
      console.error(`Error processing collection ${name}:`, err.message);
    }
  }

  console.log("\nFinished scanning and fixing all collection indexes.");
  await mongoose.connection.close();
}

fix().catch(err => {
  console.error("Index cleanup error:", err);
  process.exit(1);
});
