from typing import List, Optional
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup
import logging
import re
from datetime import datetime
from app.scrapers.base_scraper import BaseScraper, ScrapedProduct, ScrapedReview

logger = logging.getLogger(__name__)


class AmazonScraper(BaseScraper):
    BASE_URL = "https://www.amazon.com"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._init_driver()

    def _init_driver(self):
        chrome_options = Options()
        chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0 Safari/537.36")
        try:
            from selenium.webdriver.chrome.service import Service as ChromeService
            from webdriver_manager.chrome import ChromeDriverManager
            self.driver = webdriver.Chrome(
                service=ChromeService(ChromeDriverManager().install()),
                options=chrome_options,
            )
        except Exception:
            logger.warning("webdriver-manager failed, falling back to system chromedriver")
            self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(self.timeout)

    def search_product(self, query: str) -> Optional[ScrapedProduct]:
        try:
            search_url = f"{self.BASE_URL}/s?k={query.replace(' ', '+')}"
            self.driver.get(search_url)
            self._random_delay()

            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-component-type='s-search-result']")))

            soup = BeautifulSoup(self.driver.page_source, "html.parser")
            first_result = soup.select_one("[data-component-type='s-search-result']")
            if not first_result:
                return None

            link_elem = first_result.select_one("h2 a, .a-link-normal")
            if not link_elem or not link_elem.get("href"):
                return None

            product_url = link_elem["href"]
            if not product_url.startswith("http"):
                product_url = self.BASE_URL + product_url

            name_elem = first_result.select_one("h2 span, h2 a span")
            product_name = name_elem.get_text(strip=True) if name_elem else query

            return ScrapedProduct(name=product_name, url=product_url, source="amazon")
        except Exception as e:
            logger.error(f"Amazon search failed: {e}")
            return None

    def scrape_reviews(self, product_url: str, limit: int = 50) -> List[ScrapedReview]:
        reviews = []
        try:
            review_url = product_url.replace("/dp/", "/product-reviews/")
            if "/product-reviews/" not in review_url:
                review_url = product_url.rstrip("/") + "/product-reviews/"

            self.driver.get(review_url)
            self._random_delay()

            wait = WebDriverWait(self.driver, 10)
            wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "[data-hook='review']")))

            page = 1
            max_pages = 3
            while len(reviews) < limit and page <= max_pages:
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                review_elements = soup.select("[data-hook='review']")

                for elem in review_elements:
                    if len(reviews) >= limit:
                        break
                    review = self._parse_review(elem)
                    if review:
                        reviews.append(review)

                if len(reviews) >= limit:
                    break

                try:
                    next_btn = self.driver.find_element(By.CSS_SELECTOR, ".a-pagination .a-last a")
                    next_btn.click()
                    self._random_delay()
                    page += 1
                except NoSuchElementException:
                    break

        except Exception as e:
            logger.error(f"Amazon scraping failed: {e}")

        return reviews[:limit]

    def _parse_review(self, elem) -> Optional[ScrapedReview]:
        try:
            text_elem = elem.select_one("[data-hook='review-body']")
            review_text = text_elem.get_text(strip=True) if text_elem else ""

            rating_elem = elem.select_one("[data-hook='review-star-rating']")
            rating = 0
            if rating_elem:
                rating_text = rating_elem.get_text(strip=True)
                match = re.search(r"(\d+\.?\d*)", rating_text)
                if match:
                    rating = int(float(match.group(1)))

            date_elem = elem.select_one("[data-hook='review-date']")
            review_date = date_elem.get_text(strip=True) if date_elem else ""

            reviewer_elem = elem.select_one(".a-profile-name")
            reviewer = reviewer_elem.get_text(strip=True) if reviewer_elem else ""

            return ScrapedReview(
                product_name="",
                product_url="",
                review_text=review_text,
                rating=rating,
                review_date=review_date,
                reviewer=reviewer,
                source="amazon",
            )
        except Exception as e:
            logger.debug(f"Failed to parse review: {e}")
            return None