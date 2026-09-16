"""
Day 96–100 — Production Deployment: Database Initialization & Indexing Script

Applies all production MongoDB compound indexes, unique constraints, and TTL indexes.
Can be executed during CI/CD or container entrypoint before starting the API server.
"""

import asyncio
import logging
import sys
from pathlib import Path

# Ensure the backend directory is on sys.path so 'app' is importable
# when this script is run directly (e.g., python scripts/init_production_db.py)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pymongo import ASCENDING, DESCENDING, IndexModel

from app.database.mongodb import connect_to_mongo, close_mongo_connection, get_database
from app.config.settings import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("init_production_db")


async def _ensure_indexes(collection, indexes: list[IndexModel]):
    """Create indexes, dropping any conflicting old indexes first.

    MongoDB raises IndexOptionsConflict (code 85) when an index with the
    same key pattern but a different name already exists.  This helper
    catches that, drops the offending auto-generated indexes, and retries.
    """
    try:
        await collection.create_indexes(indexes)
    except Exception as exc:
        if getattr(exc, "code", None) == 85:  # IndexOptionsConflict
            logger.warning(f"  ⚠ Dropping conflicting indexes on '{collection.name}' and retrying...")
            # Build a set of key patterns we intend to create
            desired_keys = {tuple(idx.document["key"].items()) for idx in indexes}
            existing = await collection.index_information()
            for idx_name, idx_info in existing.items():
                if idx_name == "_id_":
                    continue
                existing_keys = tuple((k, int(v)) for k, v in idx_info["key"])
                if existing_keys in desired_keys:
                    logger.info(f"    Dropping old index '{idx_name}' on '{collection.name}'")
                    await collection.drop_index(idx_name)
            # Retry after dropping conflicts
            await collection.create_indexes(indexes)
        else:
            raise


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
        await _ensure_indexes(db.users, [
            IndexModel([("email", ASCENDING)], unique=True, name="idx_users_email_unique"),
            IndexModel([("id", ASCENDING)], unique=True, name="idx_users_id_unique"),
            IndexModel([("api_keys.key", ASCENDING)], name="idx_users_api_keys"),
        ])
        logger.info("  ✓ Users indexes created.")

        # 2. Research jobs collection
        await _ensure_indexes(db.research_jobs, [
            IndexModel([("id", ASCENDING)], unique=True, name="idx_jobs_id_unique"),
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="idx_jobs_user_created"),
            IndexModel([("status", ASCENDING), ("created_at", ASCENDING)], name="idx_jobs_status_created"),
            IndexModel([("organization_id", ASCENDING)], name="idx_jobs_org_id"),
        ])
        logger.info("  ✓ Research jobs indexes created.")

        # 3. Reports collection
        await _ensure_indexes(db.reports, [
            IndexModel([("id", ASCENDING)], unique=True, name="idx_reports_id_unique"),
            IndexModel([("research_id", ASCENDING)], name="idx_reports_research_id"),
            IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)], name="idx_reports_user_created"),
        ])
        logger.info("  ✓ Reports indexes created.")

        # 4. Sources collection
        await _ensure_indexes(db.sources, [
            IndexModel([("research_id", ASCENDING)], name="idx_sources_research_id"),
            IndexModel([("url", ASCENDING)], name="idx_sources_url"),
        ])
        logger.info("  ✓ Sources indexes created.")

        # 5. Organizations collection
        await _ensure_indexes(db.organizations, [
            IndexModel([("id", ASCENDING)], unique=True, name="idx_orgs_id_unique"),
            IndexModel([("owner_id", ASCENDING)], name="idx_orgs_owner_id"),
        ])
        logger.info("  ✓ Organizations indexes created.")

        # 6. Tasks collection (Day 11)
        await _ensure_indexes(db.tasks, [
            IndexModel([("id", ASCENDING)], unique=True, name="idx_tasks_id_unique"),
            IndexModel([("user_id", ASCENDING), ("status", ASCENDING)], name="idx_tasks_user_status"),
        ])
        logger.info("  ✓ Tasks indexes created.")

        # 7. Cache entries (TTL expiration)
        await _ensure_indexes(db.cache_entries, [
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
