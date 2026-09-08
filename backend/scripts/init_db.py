import asyncio
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.database.mongodb import connect_to_mongo, close_mongo_connection, db_manager
from app.database.models.user import UserCreate
from app.services.user_service import user_service
from app.utils.logger import logger


async def init_database():
    logger.info("Initializing database indices and default admin user...")
    await connect_to_mongo()
    
    try:
        # Create default demo user
        admin = UserCreate(
            email="admin@deepresearch.ai",
            password="adminpassword123",
            full_name="Principal Researcher",
            role="admin"
        )
        try:
            await user_service.register_user(admin)
            logger.info("Admin user created: admin@deepresearch.ai / adminpassword123")
        except Exception:
            logger.info("Admin user already exists.")
    finally:
        await close_mongo_connection()

if __name__ == "__main__":
    asyncio.run(init_database())
