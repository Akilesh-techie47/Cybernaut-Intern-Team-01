"""
Static HTML Table Scraper — requests + BeautifulSoup.

This module replaces Selenium with a simple HTTP fetch (or local file read)
and DOM parsing via BeautifulSoup.  It is the correct tool when the target
page is **static HTML** (no JavaScript-rendered content).

Key design choice: `fetch_html()` branches on "http" prefix so the same
module works for both local files and hosted pages without any code changes.
"""

import logging
from typing import List, Dict, Any

import requests
from bs4 import BeautifulSoup

import config

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── HTML Fetching ──────────────────────────────────────────────────────────────

def fetch_html(source: str) -> str:
    """
    Return raw HTML as a string.

    • If *source* starts with ``http``, issue an HTTP GET request.
    • Otherwise treat *source* as a local file path and read from disk.

    This branching keeps the rest of the scraper unchanged regardless of
    whether the page is hosted or just a file on disk.
    """
    if source.lower().startswith("http"):
        logger.info(f"Fetching HTML from URL: {source}")
        headers = {"User-Agent": config.USER_AGENT}
        try:
            response = requests.get(
                source, headers=headers, timeout=config.REQUEST_TIMEOUT
            )
            response.raise_for_status()
            logger.info(
                f"HTTP {response.status_code} — received {len(response.text):,} bytes."
            )
            return response.text
        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Could not connect to {source}. Check the URL or your network."
            )
        except requests.exceptions.Timeout:
            raise TimeoutError(
                f"Request to {source} timed out after {config.REQUEST_TIMEOUT}s."
            )
        except requests.exceptions.HTTPError as exc:
            raise RuntimeError(
                f"HTTP error from {source}: {exc.response.status_code} {exc.response.reason}"
            )
    else:
        logger.info(f"Reading HTML from local file: {source}")
        try:
            with open(source, "r", encoding="utf-8") as fh:
                html = fh.read()
            logger.info(f"Read {len(html):,} bytes from {source}.")
            return html
        except FileNotFoundError:
            raise FileNotFoundError(
                f"Local HTML file not found: {source}\n"
                "Check the PAGE_SOURCE path in config.py."
            )


# ─── Table Parsing ──────────────────────────────────────────────────────────────

def parse_table(html: str, top_n: int = 10) -> List[Dict[str, Any]]:
    """
    Parse the first ``<table>`` in *html* and return up to *top_n* coin rows.

    Each row is returned as a dict with keys matching the Selenium project's
    schema:  ``Rank``, ``Name``, ``Symbol``, ``Price``, ``24h_Change``,
    ``Market_Cap``.

    Parsing strategy:
    1. Locate the ``<table>`` element (raises if none found).
    2. Detect header rows (``<th>``) and skip them automatically.
    3. Iterate ``<tr>`` elements in ``<tbody>`` (or the table body).
    4. For each row, extract ``<td>`` cell text.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")

    if table is None:
        raise ValueError(
            "No <table> element found in the HTML source. "
            "Ensure the page contains a crypto data table."
        )

    # Prefer <tbody> rows, fall back to all <tr> in the table
    tbody = table.find("tbody")
    rows = (tbody or table).find_all("tr")

    if not rows:
        raise ValueError(
            "Table found but contains no <tr> rows. "
            "The page may be empty or malformed."
        )

    extracted: List[Dict[str, Any]] = []
    skipped = 0

    for row in rows:
        # Skip header rows (contain <th> instead of <td>)
        if row.find("th"):
            continue

        cells = row.find_all("td")
        if len(cells) < 4:
            skipped += 1
            logger.warning(
                f"Skipping malformed row with only {len(cells)} cell(s): "
                f"{row.get_text(strip=True)[:80]}"
            )
            continue

        try:
            coin = _extract_coin_from_cells(cells, rank_fallback=len(extracted) + 1)
            extracted.append(coin)
            logger.info(
                f"Parsed #{coin['Rank']} — {coin['Name']} ({coin['Symbol']}): "
                f"Price={coin['Price']}, 24h={coin['24h_Change']}, "
                f"MCap={coin['Market_Cap']}"
            )
        except Exception as exc:
            skipped += 1
            logger.warning(f"Error parsing a row: {exc}")

        if len(extracted) >= top_n:
            break

    logger.info(
        f"Extracted {len(extracted)} coin(s) from the static table "
        f"({skipped} row(s) skipped)."
    )
    return extracted


# ─── Cell-level extraction ──────────────────────────────────────────────────────

def _extract_coin_from_cells(cells, rank_fallback: int) -> Dict[str, Any]:
    """
    Given a list of ``<td>`` BeautifulSoup elements from a single ``<tr>``,
    return a dict with keys:
        Rank, Name, Symbol, Price, 24h_Change, Market_Cap

    The function handles the mock CoinMarketCap layout where:
        cell[0] = rank
        cell[1] = name + symbol (nested <p> tags)
        cell[2] = price
        cell[3] = 24h change
        cell[4] = market cap  (optional)
    """
    # ── Rank ────────────────────────────────────────────────────────────────
    rank_text = cells[0].get_text(strip=True)
    try:
        rank = int(rank_text)
    except ValueError:
        rank = rank_fallback

    # ── Name & Symbol ───────────────────────────────────────────────────────
    name_cell = cells[1]

    # Try specific class selectors first (matches mock_coinmarketcap.html)
    name_tag = name_cell.find(class_="coin-item-name")
    symbol_tag = name_cell.find(class_="coin-item-symbol")

    if name_tag:
        name = name_tag.get_text(strip=True)
    else:
        # Fallback: first text chunk in the cell
        name = name_cell.get_text(" ", strip=True).split()[0] if name_cell.get_text(strip=True) else f"Coin_{rank}"

    if symbol_tag:
        symbol = symbol_tag.get_text(strip=True)
    else:
        # Fallback: second word or derive from name
        parts = name_cell.get_text(" ", strip=True).split()
        symbol = parts[1] if len(parts) > 1 else name[:4].upper()

    # ── Price ───────────────────────────────────────────────────────────────
    price = cells[2].get_text(strip=True) if len(cells) > 2 else "N/A"

    # ── 24h Change ──────────────────────────────────────────────────────────
    change_24h = cells[3].get_text(strip=True) if len(cells) > 3 else "N/A"

    # ── Market Cap ──────────────────────────────────────────────────────────
    market_cap = cells[4].get_text(strip=True) if len(cells) > 4 else "N/A"

    return {
        "Rank": rank,
        "Name": name,
        "Symbol": symbol,
        "Price": price,
        "24h_Change": change_24h,
        "Market_Cap": market_cap,
    }
