import os
from pymongo import MongoClient
from pymongo.database import Database
from app.config.settings import config
import logging

logger = logging.getLogger(__name__)

_client: MongoClient = None
_db: Database = None


def get_db() -> Database:
    global _client, _db
    if _db is not None:
        return _db

    cfg = config[os.getenv("FLASK_ENV", "default")]
    try:
        _client = MongoClient(cfg.MONGODB_URI, serverSelectionTimeoutMS=5000)
        _client.admin.command("ping")
        _db = _client[cfg.DATABASE_NAME]
        logger.info(f"Connected to MongoDB: {cfg.DATABASE_NAME}")
        return _db
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        raise


def close_db():
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        logger.info("MongoDB connection closed")