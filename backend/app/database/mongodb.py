from typing import Optional, List
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING
from app.config.settings import settings
from app.utils.logger import logger


class Database:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.is_connected: bool = False


db_manager = Database()


async def init_db_collections(db: AsyncIOMotorDatabase):
    """
    Day 16 — Initialize collections and indexes.
    Checks if `research_sources` collection exists, creates it if missing,
    and ensures indexes are set up.
    """
    try:
        existing_collections = await db.list_collection_names()
        
        # 1. Initialize research_sources collection if not present
        if "research_sources" not in existing_collections:
            logger.info("Creating 'research_sources' collection in MongoDB...")
            await db.create_collection("research_sources")
        else:
            logger.debug("'research_sources' collection already exists.")

        # 2. Setup indexes on research_sources
        sources_col = db["research_sources"]
        await sources_col.create_index([("source_id", ASCENDING)], unique=True, sparse=True)
        await sources_col.create_index([("id", ASCENDING)], sparse=True)
        await sources_col.create_index([("research_id", ASCENDING), ("content_hash", ASCENDING)])
        await sources_col.create_index([("research_id", ASCENDING), ("domain", ASCENDING)])
        await sources_col.create_index([("research_id", ASCENDING), ("source_type", ASCENDING)])
        await sources_col.create_index([("relevance_score", DESCENDING)])

        # 3. Setup indexes on research_tasks
        if "research_tasks" not in existing_collections:
            await db.create_collection("research_tasks")
        tasks_col = db["research_tasks"]
        await tasks_col.create_index([("id", ASCENDING)], unique=True, sparse=True)
        await tasks_col.create_index([("research_id", ASCENDING), ("status", ASCENDING)])

        logger.info("MongoDB collections and indexes initialized successfully.")
    except Exception as e:
        logger.warning(f"Collection/index initialization notice: {e}")


async def connect_to_mongo():
    """Establish connection to MongoDB with timeout and fallback support."""
    try:
        db_manager.client = AsyncIOMotorClient(
            settings.MONGODB_URL,
            serverSelectionTimeoutMS=2000
        )
        db_manager.db = db_manager.client[settings.MONGODB_DB_NAME]
        # Ping the database to verify active connection
        await db_manager.client.admin.command("ping")
        db_manager.is_connected = True
        logger.info(f"Connected to MongoDB at {settings.MONGODB_URL}")

        # Initialize collections & indexes
        await init_db_collections(db_manager.db)
    except Exception as e:
        if db_manager.client:
            try:
                db_manager.client.close()
            except Exception:
                pass
            db_manager.client = None
        db_manager.db = None
        db_manager.is_connected = False
        logger.warning(f"MongoDB connection failed ({e}). Operating in memory-fallback mode.")


async def close_mongo_connection():
    """Gracefully close MongoDB connection."""
    if db_manager.client:
        try:
            db_manager.client.close()
        except Exception:
            pass
        db_manager.client = None
        db_manager.db = None
        db_manager.is_connected = False
        logger.info("MongoDB connection closed.")


def get_database() -> Optional[AsyncIOMotorDatabase]:
    """Return active database instance or None if operating in-memory."""
    return db_manager.db if db_manager.is_connected else None
