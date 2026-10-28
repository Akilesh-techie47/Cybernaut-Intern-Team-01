# Scraping Documentation

## Overview

The scraping module uses Selenium WebDriver with headless Chrome to extract product reviews from e-commerce websites. It follows a modular architecture with a base class and site-specific implementations.

## Architecture

```
BaseScraper (abstract)
├── AmazonScraper
└── FlipkartScraper
```

### BaseScraper Interface

```python
class BaseScraper(ABC):
    def search_product(self, query: str) -> Optional[ScrapedProduct]:
        """Search for a product and return first result."""
        pass

    def scrape_reviews(self, product_url: str, limit: int) -> List[ScrapedReview]:
        """Scrape reviews from product page."""
        pass

    def cleanup(self):
        """Close browser session."""
        pass
```

### Data Models

```python
@dataclass
class ScrapedProduct:
    name: str
    url: str
    source: str

@dataclass
class ScrapedReview:
    product_name: str
    product_url: str
    review_text: str
    rating: int
    review_date: str
    reviewer: str
    source: str
```

## Amazon Scraper

### Search
- URL: `https://www.amazon.com/s?k={query}`
- Selector: `[data-component-type='s-search-result']`
- Extracts: First product link and name

### Reviews
- URL: `{product_url}/product-reviews/`
- Pagination: `.a-pagination .a-last a`
- Review selector: `[data-hook='review']`
- Fields:
  - Text: `[data-hook='review-body']`
  - Rating: `[data-hook='review-star-rating']`
  - Date: `[data-hook='review-date']`
  - Reviewer: `.a-profile-name`

## Flipkart Scraper

### Search
- URL: `https://www.flipkart.com/search?q={query}`
- Selector: `[class*='_1AtVbE']` (product cards)
- Extracts: First product link with `/p/` in href

### Reviews
- URL: `{product_url}/product-reviews/`
- Pagination: `a[class*='_1LKTO3']:last-child`
- Review selector: `[class*='_1AtVbE'], .col`
- Fields:
  - Text: `[class*='_6KkbIX'], [class*='t-ZTKy']`
  - Rating: `[class*='_3LWZlK'], [class*='XQDdHH']`
  - Date: `[class*='_2sc7ZR'], [class*='_2rpwqI']`
  - Reviewer: `[class*='_2sc7ZR']`

## Configuration

Settings in `backend/app/config/settings.py`:

```python
SCRAPER_DELAY_MIN = 2      # Minimum delay between requests (seconds)
SCRAPER_DELAY_MAX = 5      # Maximum delay between requests (seconds)
SCRAPER_TIMEOUT = 30       # Page load timeout (seconds)
SCRAPER_MAX_PAGES = 5      # Maximum pages to scrape
SCRAPER_MAX_REVIEWS = 200  # Maximum reviews per product
```

## Safety Features

1. **Random Delays**: `random.uniform(delay_min, delay_max)` between requests
2. **Timeout Handling**: 30-second page load timeout
3. **Retry Logic**: Implicit via Selenium waits
4. **Browser Cleanup**: Context manager ensures driver.quit()
5. **Pagination Limits**: Max 5 pages per product
6. **Duplicate Detection**: Database-level unique index
7. **Error Logging**: Structured logging for debugging
8. **Graceful Degradation**: Returns partial results on failure

## Headless Chrome Options

```python
chrome_options = Options()
chrome_options.add_argument("--headless=new")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")
chrome_options.add_argument("--window-size=1920,1080")
chrome_options.add_argument("--user-agent=Mozilla/5.0...")
```

## Adding New Scrapers

1. Create `backend/app/scrapers/newsite_scraper.py`
2. Extend `BaseScraper`
3. Implement `search_product()` and `scrape_reviews()`
4. Register in `backend/app/scrapers/factory.py`
5. Add to `SUPPORTED_SOURCES` list

## Legal & Ethical Considerations

- Respect `robots.txt` and Terms of Service
- Implement rate limiting
- No CAPTCHA bypassing
- No anti-bot evasion
- User-Agent identification
- Graceful failure on blocks

## Testing

Use stored HTML fixtures for unit tests:

```python
def test_parse_review():
    with open('tests/fixtures/amazon_review.html') as f:
        html = f.read()
    soup = BeautifulSoup(html, 'html.parser')
    review = scraper._parse_review(soup)
    assert review.rating == 5
    assert 'battery' in review.review_text.lower()
```

## Troubleshooting

### Common Issues

1. **ChromeDriver version mismatch**
   - Use `webdriver-manager` (auto-installs matching version)

2. **Element not found**
   - Site structure changed - update selectors
   - Add explicit waits

3. **Timeout**
   - Increase `SCRAPER_TIMEOUT`
   - Check network connectivity

4. **Blocked by anti-bot**
   - Reduce request frequency
   - Add more realistic headers
   - Consider proxy rotation (not implemented)

### Debugging

Enable debug logging:
```python
logging.getLogger('app.scrapers').setLevel(logging.DEBUG)
```

Save page source on failure:
```python
with open('debug_page.html', 'w') as f:
    f.write(driver.page_source)
```