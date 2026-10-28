import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "sentiment_analyzer")
    FLASK_ENV = os.getenv("FLASK_ENV", "development")
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    PORT = int(os.getenv("PORT", 5000))

    SENTIMENT_POSITIVE_THRESHOLD = 0.05
    SENTIMENT_NEGATIVE_THRESHOLD = -0.05

    SCRAPER_DELAY_MIN = 0.8
    SCRAPER_DELAY_MAX = 1.8
    SCRAPER_TIMEOUT = 30
    SCRAPER_MAX_PAGES = 3
    SCRAPER_MAX_REVIEWS = 200


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}