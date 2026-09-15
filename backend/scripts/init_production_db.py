"""
Day 96–100 — Production Deployment: Database Initialization & Indexing Script

Applies all production MongoDB compound indexes, unique constraints, and TTL indexes.
Can be executed during CI/CD or container entrypoint before starting the API server.
"""

import asyncio
import logging
from pymongo import ASCENDING, DESCENDING, IndexModel

from app.database.mongodb import connect_to_mongo, close_mongo_connection, get_database
from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_production_db")


async def init_production_database():
    """Initialize database and build all production indexes."""
    logger.info(f"Connecting to MongoDB at {settings.MONGODB_URL} (db: {settings.MONGODB_DB_NAME})...")
    await connect_to_mongo()
    db = get_database()

    if db is None:
        logger.error("Failed to connect to MongoDB.")
        return False

    logger.info("Building production database indexes...")

    try:
        # 1. Users collection
        await db.users.create_indexes([
            IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
            IndexModel([("id", ASCENDING)], unique=True, name="idx_users_id_unique"),
            IndexModel([("api_keys.key", ASCENDING)], name="idx_users_api_keys"),
        ])
        logger.info("  ✓ Users indexes created.")

        # 2. Research jobs collection
        await db.research_jobs.create_indexes([
            IndexModel([("id", ASCENDING)], unique=True, name="idx_jobs_id_unique"),
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="idx_jobs_user_created"),
            IndexModel([("status", ASCENDING), ("created_at", ASCENDING)], name="idx_jobs_status_created"),
            IndexModel([("organization_id", ASCENDING)], name="idx_jobs_org_id"),
        ])
        logger.info("  ✓ Research jobs indexes created.")

        # 3. Reports collection
        await db.reports.create_indexes([
            IndexModel([("id", ASCENDING)], unique=True, name="idx_reports_id_unique"),
            IndexModel([("research_id", ASCENDING)], name="idx_reports_research_id"),
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="idx_reports_user_created"),
        ])
        logger.info("  ✓ Reports indexes created.")

        # 4. Sources collection
        await db.sources.create_indexes([
            IndexModel([("research_id", ASCENDING)], name="idx_sources_research_id"),
            IndexModel([("url", ASCENDING)], name="idx_sources_url"),
        ])
        logger.info("  ✓ Sources indexes created.")

        # 5. Organizations collection
        await db.organizations.create_indexes([
            IndexModel([("id", ASCENDING)], unique=True, name="idx_orgs_id_unique"),
            IndexModel([("owner_id", ASCENDING)], name="idx_orgs_owner_id"),
        ])
        logger.info("  ✓ Organizations indexes created.")

        # 6. Tasks collection (Day 11)
        await db.tasks.create_indexes([
            IndexModel([("id", ASCENDING)], unique=True, name="idx_tasks_id_unique"),
            IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="idx_tasks_user_status"),
        ])
        logger.info("  ✓ Tasks indexes created.")

        # 7. Cache entries (TTL expiration)
        await db.cache_entries.create_indexes([
            IndexModel([("key", ASCENDING)], unique=True, name="idx_cache_key_unique"),
            IndexModel([("expires_at", ASCENDING)], expireAfterSeconds=0, name="idx_cache_ttl"),
        ])
        logger.info("  ✓ Cache TTL indexes created.")

        logger.info("All production database indexes initialized successfully.")
        return True

    except Exception as e:
        logger.error(f"Error initializing indexes: {e}")
        return False
    finally:
        await close_mongo_connection()


if __name__ == "__main__":
    asyncio.run(init_production_database())
