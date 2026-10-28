import sys
import logging
from tabulate import tabulate

import config
import scraper
import data_handler

# Set up clean logging format
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MainOrchestrator")


def run_pipeline():
    """Orchestrates scrape -> clean -> filter -> export pipeline."""
    driver = None
    logger.info("=== Starting Cryptocurrency Price Tracker ===")
    logger.info(f"Target URL: {config.TARGET_URL}")
    logger.info(f"Target Top N Coins: {config.TOP_N}")
    logger.info(f"Headless Mode: {config.HEADLESS}")
    logger.info(f"CSV Storage Path: {config.CSV_PATH}")

    try:
        # Step 1: Initialize Selenium WebDriver
        driver = scraper.init_driver(headless=config.HEADLESS)

        # Step 2: Load Page dynamically
        scraper.load_page(driver, config.TARGET_URL, timeout=config.TIMEOUT)

        # Step 3: Extract Top N Raw Records
        raw_coins = scraper.extract_top_n(driver, n=config.TOP_N)

        if not raw_coins:
            logger.error("No coin records could be extracted from CoinMarketCap!")
            sys.exit(1)

        # Step 4: Data Processing & Cleaning
        df = data_handler.clean_data(raw_coins)

        # Step 5: Optional Filtering
        filtered_df = data_handler.apply_filters(
            df,
            threshold=config.PRICE_THRESHOLD,
            top_gainers=config.TOP_GAINERS_ONLY
        )

        # Step 6: Console Output Display
        print("\n" + "=" * 80)
        print(f" SCRAPED DATA SUMMARY ({len(filtered_df)} coins retrieved)")
        print("=" * 80)
        display_cols = ["Rank", "Name", "Symbol", "Price", "24h_Change", "Market_Cap"]
        cols_present = [c for c in display_cols if c in filtered_df.columns]
        
        try:
            # Print using tabulate if available or pandas string
            from tabulate import tabulate
            print(tabulate(filtered_df[cols_present], headers="keys", tablefmt="pretty", showindex=False))
        except ImportError:
            print(filtered_df[cols_present].to_string(index=False))
            
        print("=" * 80 + "\n")

        # Step 7: Export to CSV Log
        data_handler.save_to_csv(filtered_df, config.CSV_PATH)

        logger.info("Pipeline execution completed successfully.")

    except Exception as e:
        logger.error(f"Critical error during execution: {e}", exc_info=True)
    finally:
        # Guarantee teardown of Chrome WebDriver
        if driver:
            scraper.close_driver(driver)


if __name__ == "__main__":
    run_pipeline()
