import time
from datetime import datetime

import pandas as pd
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

IMDB_URL = "https://www.imdb.com/chart/top/"


def get_driver():
    options = uc.ChromeOptions()
    options.add_argument("--window-size=1920,1080")
    driver = uc.Chrome(options=options)
    return driver


def scrape_top_250():
    driver = get_driver()
    movies = []

    try:
        driver.get(IMDB_URL)
        time.sleep(3)
        deadline = time.time() + 120
        while time.time() < deadline:
            title = driver.title.lower()
            if "imdb" in title and "top" in title:
                break
            print("Waiting for CAPTCHA to be solved in the browser window "
                  "(or for the page to finish loading)...")
            time.sleep(3)
        print("Page title:", driver.title)
        try:
            consent_wait = WebDriverWait(driver, 5)
            consent_btn = consent_wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "button[data-testid='accept-button'], button#onetrust-accept-btn-handler")
            ))
            consent_btn.click()
            time.sleep(1)
        except Exception:
            pass
        wait = WebDriverWait(driver, 20)
        try:
            wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item")
            ))
        except Exception:
            with open("debug_page.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            driver.save_screenshot("debug_screenshot.png")
            print("Could not find movie rows. Saved debug_page.html and "
                  "debug_screenshot.png in the current folder for inspection.")
            return []

        time.sleep(2)

        rows = driver.find_elements(By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item")
        print(f"Found {len(rows)} row elements")

        for i, row in enumerate(rows):
            if i > 0 and i % 25 == 0:
                title = driver.title.lower()
                if not ("imdb" in title and "top" in title):
                    print("CAPTCHA appeared mid-scrape — please solve it in "
                          "the browser window.")
                    deadline = time.time() + 120
                    while time.time() < deadline:
                        if "imdb" in driver.title.lower() and "top" in driver.title.lower():
                            break
                        time.sleep(3)
                    rows = driver.find_elements(By.CSS_SELECTOR, "li.ipc-metadata-list-summary-item")

            time.sleep(0.05)
            try:
                title = row.find_element(By.CSS_SELECTOR, "h4.ipc-title__text").text

                rank_el = row.find_elements(By.CSS_SELECTOR, "[data-testid='title-list-item-ranking'] .ipc-signpost__text")
                rank = rank_el[0].text.lstrip("#") if rank_el else str(i + 1)

                year_items = row.find_elements(By.CSS_SELECTOR, "li.ipc-inline-list__item")
                year = year_items[0].text if year_items else ""

                rating = row.find_element(By.CSS_SELECTOR, "span.ipc-rating-star--rating").text

                movies.append({
                    "Rank": rank.strip(),
                    "Title": title.strip(),
                    "Year": year.strip(),
                    "Rating": rating.strip(),
                })
            except Exception as e:
                if i == 0:
                    with open("debug_row.html", "w", encoding="utf-8") as f:
                        f.write(row.get_attribute("outerHTML"))
                    print("Saved full row HTML to debug_row.html for inspection.")
                print(f"Skipped row {i + 1} due to: {type(e).__name__}")
                continue

    finally:
        driver.quit()

    return movies


def save_to_csv(movies):
    if not movies:
        print("No data scraped — nothing to save.")
        return

    df = pd.DataFrame(movies)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"imdb_top250_{timestamp}.csv"
    df.to_csv(filename, index=False)
    print(f"Saved {len(df)} movies to {filename}")


if __name__ == "__main__":
    data = scrape_top_250()
    save_to_csv(data)