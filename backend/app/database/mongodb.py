from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from app.config.settings import settings
from app.utils.logger import logger


class Database:
    def __init__(self):
        self.client: Optional[AsyncIOMotorClient] = None
        self.db: Optional[AsyncIOMotorDatabase] = None
        self.is_connected: bool = False


db_manager = Database()


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

