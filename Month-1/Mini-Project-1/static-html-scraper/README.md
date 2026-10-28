# Static HTML Crypto Table Scraper

A lightweight Python scraper that extracts cryptocurrency data from a **static HTML table** using `requests` + `BeautifulSoup` — no browser automation required.

This project is a companion to the **Selenium-based CoinMarketCap Tracker** in the parent directory, demonstrating the *"right tool for the right job"* principle.

---

## Why No Selenium?

| Factor | Static Page (this project) | Dynamic Page (Selenium project) |
|---|---|---|
| **Data in initial HTML?** | ✅ Yes — `<table>` rows are in the raw source | ❌ No — data is rendered by JavaScript after page load |
| **JavaScript required?** | ❌ None | ✅ Must execute JS to populate the DOM |
| **Tool needed** | `requests.get()` returns complete content | Selenium WebDriver must render the page first |
| **Speed** | Milliseconds | Seconds (browser startup + rendering + waits) |
| **Dependencies** | `requests`, `beautifulsoup4` | `selenium`, `webdriver-manager`, Chrome browser |
| **Resource usage** | Minimal (single HTTP call) | Heavy (spawns a full Chrome process) |

### How to verify a page is static

1. **View Page Source** (`Ctrl+U`) — if the data is visible here, the page is static.
2. **Compare to Inspect Element** — if the rendered DOM differs significantly from the source, JavaScript is adding content dynamically.
3. **Disable JavaScript** in DevTools → reload — if the data disappears, Selenium is needed.
4. **`curl` the URL** — if the response already contains the data, `requests` is sufficient.

---

## Project Structure

```
static-html-scraper/
├── main.py              # Entry point — Fetch → Parse → Clean → Export
├── scraper.py           # requests + BeautifulSoup fetching & parsing
├── data_handler.py      # Cleaning + CSV export (mirrors Selenium project schema)
├── config.py            # Page source, output path, settings
├── requirements.txt     # requests, beautifulsoup4, pandas, tabulate
├── data/
│   └── static_prices.csv   # Output (created on first run)
└── README.md            # This file
```

---

## Setup & Run

```bash
# 1. Create and activate a virtual environment (optional but recommended)
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the scraper
python main.py
```

The scraper reads from the mock HTML page in `../data/mock_coinmarketcap.html` by default. To change the source, edit `PAGE_SOURCE` in `config.py`.

---

## CSV Schema

Both this scraper and the Selenium project produce **identical CSV columns**:

| Column | Type | Description |
|---|---|---|
| `Timestamp` | string | When the scrape was executed |
| `Rank` | int | Market cap ranking |
| `Name` | string | Full coin name |
| `Symbol` | string | Ticker symbol |
| `Price` | string | Raw display price (e.g. `$79,512.00`) |
| `Clean_Price` | float | Numeric price value |
| `24h_Change` | string | Raw display change (e.g. `-1.73%`) |
| `Clean_24h_Change` | float | Numeric change value |
| `Market_Cap` | string | Raw display market cap |
| `Clean_Market_Cap` | float | Numeric market cap value |

This means CSVs from both scrapers can be **concatenated** into a single dataset for analysis — same schema, two different collection methods.

---

## Configuration

Edit `config.py` to customize:

| Setting | Default | Description |
|---|---|---|
| `PAGE_SOURCE` | `../data/mock_coinmarketcap.html` | Local file path or URL |
| `TOP_N` | `10` | Max coins to extract |
| `PRICE_THRESHOLD` | `None` | Min USD price filter |
| `TOP_GAINERS_ONLY` | `False` | Keep only positive 24h coins |
| `CSV_PATH` | `data/static_prices.csv` | Output CSV location |

---

## Append-Mode Logging

Each run **appends** new rows to the CSV with a fresh `Timestamp`. This builds a historical log of prices over time — it never overwrites previous data. To reset, simply delete the CSV file.

---

## Relationship to the Selenium Project

```
Mini project 1 (month -1)/
├── main.py, scraper.py, ...    ← Selenium-based (dynamic pages)
└── static-html-scraper/        ← This project (static pages)
    ├── main.py, scraper.py, ...
    └── data/static_prices.csv
```

Both projects share the same data schema. The key internship takeaway: **always identify whether a page is static or dynamic before choosing your scraping tool**. Using Selenium on a static page is like driving a truck to the corner store — it works, but it's overkill.
