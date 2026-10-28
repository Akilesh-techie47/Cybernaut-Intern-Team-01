from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from dataclasses import dataclass
import logging
import time
import random

logger = logging.getLogger(__name__)


@dataclass
class ScrapedReview:
    product_name: str
    product_url: str
    review_text: str
    rating: int
    review_date: str
    reviewer: str
    source: str


@dataclass
class ScrapedProduct:
    name: str
    url: str
    source: str


class BaseScraper(ABC):
    def __init__(self, delay_min: float = 2.0, delay_max: float = 5.0, timeout: int = 30):
        self.delay_min = delay_min
        self.delay_max = delay_max
        self.timeout = timeout
        self.driver = None

    def _random_delay(self):
        time.sleep(random.uniform(self.delay_min, self.delay_max))

    @abstractmethod
    def search_product(self, query: str) -> Optional[ScrapedProduct]:
        pass

    @abstractmethod
    def scrape_reviews(self, product_url: str, limit: int = 50) -> List[ScrapedReview]:
        pass

    def cleanup(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()