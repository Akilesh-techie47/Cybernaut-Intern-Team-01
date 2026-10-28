from typing import Optional
from app.scrapers.base_scraper import BaseScraper
from app.scrapers.amazon_scraper import AmazonScraper
from app.scrapers.flipkart_scraper import FlipkartScraper
from app.config.settings import config
import os

cfg = config[os.getenv("FLASK_ENV", "default")]


def get_scraper(source: str) -> Optional[BaseScraper]:
    source = source.lower()
    if source == "amazon":
        return AmazonScraper(
            delay_min=cfg.SCRAPER_DELAY_MIN,
            delay_max=cfg.SCRAPER_DELAY_MAX,
            timeout=cfg.SCRAPER_TIMEOUT,
        )
    elif source == "flipkart":
        return FlipkartScraper(
            delay_min=cfg.SCRAPER_DELAY_MIN,
            delay_max=cfg.SCRAPER_DELAY_MAX,
            timeout=cfg.SCRAPER_TIMEOUT,
        )
    return None


SUPPORTED_SOURCES = ["amazon", "flipkart"]