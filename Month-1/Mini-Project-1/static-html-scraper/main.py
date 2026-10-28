"""
Static HTML Crypto Table Scraper — Main Entry Point.

Pipeline:  Fetch HTML  →  Parse <table>  →  Clean data  →  (Optional filters)  →  Export CSV

Compared to the Selenium-based CoinMarketCap tracker:
  • No browser driver lifecycle (init / load / wait / quit).
  • No JavaScript execution or explicit waits.
  • Runs in milliseconds instead of seconds.

This is the "correct tool for the job" when the target page is static HTML:
  requests.get() already returns the complete page content because there is
  no client-side rendering to wait for.
"""

import sys
import logging

import config
import scraper
import data_handler

# ─── Logging ────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("StaticScraper")


def run_pipeline() -> None:
    """Orchestrate the full scrape → clean → filter → export pipeline."""

    logger.info("=" * 60)
    logger.info("  STATIC HTML CRYPTO TABLE SCRAPER")
    logger.info("=" * 60)
    logger.info(f"Source      : {config.PAGE_SOURCE}")
    logger.info(f"Top N       : {config.TOP_N}")
    logger.info(f"CSV Output  : {config.CSV_PATH}")
    logger.info("")

    try:
        # ── Step 1: Fetch raw HTML ──────────────────────────────────────────
        html = scraper.fetch_html(config.PAGE_SOURCE)

        # ── Step 2: Parse the crypto table ──────────────────────────────────
        raw_coins = scraper.parse_table(html, top_n=config.TOP_N)

        if not raw_coins:
            logger.error("No coin records could be extracted from the table!")
            sys.exit(1)

        # ── Step 3: Clean & structure ───────────────────────────────────────
        df = data_handler.clean_data(raw_coins)

        # ── Step 4: Optional filtering ──────────────────────────────────────
        filtered_df = data_handler.apply_filters(
            df,
            threshold=config.PRICE_THRESHOLD,
            top_gainers=config.TOP_GAINERS_ONLY,
        )

        # ── Step 5: Console display ─────────────────────────────────────────
        print()
        print("=" * 80)
        print(f" SCRAPED DATA SUMMARY  ({len(filtered_df)} coins retrieved)")
        print("=" * 80)

        display_cols = ["Rank", "Name", "Symbol", "Price", "24h_Change", "Market_Cap"]
        cols_present = [c for c in display_cols if c in filtered_df.columns]

        try:
            from tabulate import tabulate
            print(
                tabulate(
                    filtered_df[cols_present],
                    headers="keys",
                    tablefmt="pretty",
                    showindex=False,
                )
            )
        except ImportError:
            print(filtered_df[cols_present].to_string(index=False))

        print("=" * 80)
        print()

        # ── Step 6: Export to CSV ───────────────────────────────────────────
        data_handler.save_to_csv(filtered_df, config.CSV_PATH)

        logger.info("Pipeline completed successfully.")

    except FileNotFoundError as exc:
        logger.error(f"File error: {exc}")
        sys.exit(1)
    except ConnectionError as exc:
        logger.error(f"Network error: {exc}")
        sys.exit(1)
    except ValueError as exc:
        logger.error(f"Parsing error: {exc}")
        sys.exit(1)
    except Exception as exc:
        logger.error(f"Unexpected error: {exc}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    run_pipeline()
