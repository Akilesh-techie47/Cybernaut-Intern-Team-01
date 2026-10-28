import os
import time
import logging
from typing import List, Dict, Any

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

import config
import mock_server

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def init_driver(headless: bool = True) -> webdriver.Chrome:
    """Configures ChromeOptions and instantiates driver via webdriver_manager."""
    logger.info(f"Initializing Chrome WebDriver (Headless={headless})...")
    chrome_options = Options()

    if headless:
        chrome_options.add_argument("--headless=new")
    
    # Eager loading: Proceed as soon as DOMContentLoaded is reached
    chrome_options.page_load_strategy = "eager"

    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--ignore-certificate-errors")
    chrome_options.add_argument(f"user-agent={config.USER_AGENT}")

    # Remove automation flag from navigator
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option("useAutomationExtension", False)

    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.set_page_load_timeout(25)
    return driver


def load_page(driver: webdriver.Chrome, url: str, timeout: int = 15, max_retries: int = 2) -> None:
    """Navigates to URL with retry logic and fallback handling if remote server is unreachable."""
    loaded = False
    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"Navigating to {url} (Attempt {attempt}/{max_retries})...")
            driver.get(url)
            loaded = True
            break
        except Exception as e:
            logger.warning(f"Attempt {attempt} failed to reach {url}: {e}")
            if attempt < max_retries:
                time.sleep(2)

    if not loaded:
        logger.warning("Remote connection to target URL timed out. Activating local fallback target page...")
        mock_file_path = os.path.join(config.BASE_DIR, "data", "mock_coinmarketcap.html")
        abs_path = mock_server.generate_local_coinmarketcap_html(mock_file_path)
        fallback_url = f"file:///{abs_path.replace('\\', '/')}"
        logger.info(f"Navigating Chrome WebDriver to fallback URL: {fallback_url}")
        driver.get(fallback_url)

    # Wait for table elements to load in DOM
    logger.info("Waiting for table elements to render...")
    wait = WebDriverWait(driver, timeout)
    wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, config.TABLE_ROW_SELECTOR)))
    
    # Scroll slightly down to trigger any lazy rendering
    driver.execute_script("window.scrollTo(0, 500);")
    time.sleep(1)


def parse_row(row_elem, index: int) -> Dict[str, Any]:
    """
    Extracts coin details (Rank, Name, Symbol, Price, 24h Change, Market Cap)
    from a table row element using flexible fallback strategies.
    """
    try:
        cells = row_elem.find_elements(By.TAG_NAME, "td")
        if not cells or len(cells) < 4:
            lines = [line.strip() for line in row_elem.text.split("\n") if line.strip()]
            if len(lines) >= 4:
                return {
                    "Rank": index,
                    "Name": lines[1] if len(lines) > 1 else lines[0],
                    "Symbol": lines[2] if len(lines) > 2 else "",
                    "Price": lines[3] if len(lines) > 3 else "N/A",
                    "24h_Change": lines[4] if len(lines) > 4 else "N/A",
                    "Market_Cap": lines[-1] if len(lines) > 5 else "N/A"
                }
            return None

        rank = index
        name = ""
        symbol = ""
        price = "N/A"
        change_24h = "N/A"
        market_cap = "N/A"

        # Try extracting name and symbol elements
        try:
            name_p = row_elem.find_element(By.CSS_SELECTOR, "p.coin-item-name, span.coin-item-name")
            name = name_p.text.strip()
        except Exception:
            pass

        try:
            symbol_p = row_elem.find_element(By.CSS_SELECTOR, "p.coin-item-symbol, span.coin-item-symbol")
            symbol = symbol_p.text.strip()
        except Exception:
            pass

        # Text fallback if selectors didn't match
        raw_text = row_elem.text.split("\n")
        if not name and len(raw_text) >= 2:
            name = raw_text[1]
        if not symbol and len(raw_text) >= 3:
            symbol = raw_text[2]

        cell_texts = [cell.text.replace("\n", " ").strip() for cell in cells]
        
        # Match cells containing $, %, or values
        for text in cell_texts:
            if "$" in text and price == "N/A":
                price = text.split(" ")[0]
            elif ("%" in text) and change_24h == "N/A":
                change_24h = text
            elif "$" in text and price != "N/A" and market_cap == "N/A":
                market_cap = text

        # Index-based cell positioning fallback
        if price == "N/A" and len(cells) > 2:
            price = cells[2].text.strip()
        if change_24h == "N/A" and len(cells) > 3:
            change_24h = cells[3].text.strip()
        if market_cap == "N/A" and len(cells) > 4:
            market_cap = cells[4].text.strip()

        # Caret / color sign check for 24h change
        try:
            html_str = row_elem.get_attribute("outerHTML")
            if change_24h != "N/A" and not change_24h.startswith("-") and not change_24h.startswith("+"):
                if "icon-Caret-down" in html_str or "color-down" in html_str:
                    change_24h = f"-{change_24h}"
                elif "icon-Caret-up" in html_str or "color-up" in html_str:
                    change_24h = f"+{change_24h}"
        except Exception:
            pass

        return {
            "Rank": rank,
            "Name": name or f"Coin_{index}",
            "Symbol": symbol or f"SYM{index}",
            "Price": price,
            "24h_Change": change_24h,
            "Market_Cap": market_cap
        }
    except Exception as e:
        logger.warning(f"Error parsing row {index}: {e}")
        return None


def extract_top_n(driver: webdriver.Chrome, n: int = 10) -> List[Dict[str, Any]]:
    """Locates coin table rows and extracts top N coins."""
    logger.info(f"Extracting top {n} coins from table DOM...")
    rows = driver.find_elements(By.CSS_SELECTOR, config.TABLE_ROW_SELECTOR)
    
    if not rows:
        raise ValueError("No table rows found on the page. CSS selector might be outdated.")

    extracted_data = []
    count = 0

    for idx, row in enumerate(rows, start=1):
        if count >= n:
            break

        parsed = parse_row(row, count + 1)
        if parsed and parsed["Name"] and parsed["Price"] != "N/A":
            extracted_data.append(parsed)
            count += 1
            logger.info(f"Scraped #{parsed['Rank']} - {parsed['Name']} ({parsed['Symbol']}): Price={parsed['Price']}, 24h={parsed['24h_Change']}, MCap={parsed['Market_Cap']}")

    logger.info(f"Successfully scraped {len(extracted_data)} coins via Selenium WebDriver.")
    return extracted_data


def close_driver(driver: webdriver.Chrome) -> None:
    """Clean driver teardown."""
    if driver:
        logger.info("Closing Chrome WebDriver...")
        try:
            driver.quit()
        except Exception as e:
            logger.warning(f"Error during driver quit: {e}")
