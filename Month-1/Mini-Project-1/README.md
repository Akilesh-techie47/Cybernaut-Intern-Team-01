# Cryptocurrency Price Tracker 🚀

A Python-based automation tool built with **Selenium WebDriver**, **pandas**, and **webdriver_manager** to scrape live top 10 cryptocurrency market data (Name, Symbol, Price, 24h Change %, Market Cap) from CoinMarketCap and log historical timestamped entries into a structured CSV file.

---

## 📌 Features

1. **Live & Dynamic Page Scraping**: Uses Selenium WebDriver with explicit `WebDriverWait` to load and parse JavaScript-rendered cryptocurrency tables.
2. **Headless Execution**: Configurable headless Chrome browser mode for silent background automation.
3. **Data Cleaning & Structure**: Strips non-numeric characters (`$`, `,`, `%`, `B`, `T`), formats values into numeric `pandas` DataFrames, and preserves formatted display strings.
4. **Historical CSV Logging**: Appends timestamped records (`YYYY-MM-DD HH:MM:SS`) to `data/crypto_prices.csv` without overwriting historical data.
5. **Custom Filtering**: Supports filtering coins by minimum price threshold (`PRICE_THRESHOLD`) and positive 24-hour performance (`TOP_GAINERS_ONLY`).
6. **Graceful Error Handling & Fallback**: Solves dynamic DOM shifts, selector breakage, network connection timeouts, and bot detection cleanly without raw tracebacks. Includes a dynamic fallback renderer for offline or restricted network environments.

---

## 📁 Project Structure

```text
crypto-price-tracker/
│
├── main.py                  # Entry point — orchestrates scrape → clean → filter → save
├── scraper.py                # Selenium WebDriver initialization, explicit waits, DOM extraction
├── data_handler.py           # pandas data cleaning, numeric parsing, filtering, CSV logger
├── config.py                  # Configuration constants (URL, top N, paths, headless flag, filters)
├── mock_server.py             # Fallback dynamic HTML renderer for offline / restricted networks
├── requirements.txt           # Project dependencies
├── data/
│   ├── crypto_prices.csv      # Output timestamped historical CSV log
│   └── mock_coinmarketcap.html# Local DOM template used during network fallbacks
└── README.md                  # Setup guide, architectural overview, & challenge write-up
```

---

## ⚙️ Installation & Setup

### 1. Prerequisites
- **Python 3.10+** (Python 3.13 verified)
- **Google Chrome** browser installed on system

### 2. Clone / Open Directory
```bash
cd "Mini project 1 (month -1)"
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

---

## 🚀 How to Run

Run the main orchestrator script:
```bash
python main.py
```

### Sample Console Output
```text
================================================================================
 SCRAPED DATA SUMMARY (10 coins retrieved)
================================================================================
+------+--------------+------------+------------+------------+--------------------+
| Rank |     Name     |   Symbol   |   Price    | 24h_Change |     Market_Cap     |
+------+--------------+------------+------------+------------+--------------------+
|  1   |   Bitcoin    |    BTC     | $79,265.00 |   -0.52%   | $1,591,692,893,137 |
|  2   |   Ethereum   |    ETH     | $2,449.51  |   -0.22%   |  $298,911,192,549  |
|  3   |    Tether    |    USDT    |  $0.9999   |   +0.01%   |  $183,370,525,932  |
|  4   |     BNB      |    BNB     |  $713.85   |   -0.67%   |  $95,058,046,504   |
|  5   |     XRP      |    XRP     |   $1.40    |   -0.99%   |  $87,670,449,162   |
|  6   |     USDC     |    USDC    |  $0.9999   |   -0.02%   |  $74,170,312,815   |
|  7   |    Solana    |    SOL     |  $101.00   |   -1.52%   |  $59,131,714,988   |
|  8   |     TRON     |    TRX     |  $0.3291   |   -0.05%   |  $31,238,645,557   |
|  9   | Figure Heloc | FIGR_HELOC |   $1.03    |   +1.93%   |  $22,975,328,971   |
|  10  | Hyperliquid  |    HYPE    |   $84.36   |   +0.97%   |  $18,764,297,741   |
+------+--------------+------------+------------+------------+--------------------+
================================================================================
```

---

## 🎛️ Configuration Options (`config.py`)

You can customize execution behavior in `config.py`:

```python
# Headless Mode (True = invisible browser, False = visible Chrome window)
HEADLESS = True

# Number of top coins to scrape
TOP_N = 10

# Optional Filters
PRICE_THRESHOLD = 50.0  # Only keep coins priced >= $50.00 (or None to disable)
TOP_GAINERS_ONLY = True # Only keep coins with positive 24h change (% > 0)
```

---

## 📊 CSV Export Format (`data/crypto_prices.csv`)

| Column | Description | Example |
| :--- | :--- | :--- |
| `Timestamp` | Run timestamp (ISO format) | `2026-09-04 20:12:16` |
| `Rank` | Coin position | `1` |
| `Name` | Cryptocurrency name | `Bitcoin` |
| `Symbol` | Ticker symbol | `BTC` |
| `Price` | Formatted price | `$79,265.00` |
| `Clean_Price` | Numeric float price | `79265.0` |
| `24h_Change` | Formatted 24h percentage | `-0.52%` |
| `Clean_24h_Change` | Numeric float percentage | `-0.52` |
| `Market_Cap` | Formatted market capitalization | `$1,591,692,893,137` |
| `Clean_Market_Cap` | Numeric float market cap | `1591692893137.0` |

---

## 📝 Internship Technical Write-Up: Challenges & Solutions

### Challenge 1: Dynamic JavaScript Rendering & Anti-Automation Detection
- **Issue**: CoinMarketCap uses dynamic Next.js rendering and dynamic CSS class names that change frequently. Additionally, headless Chrome can trigger anti-bot flags.
- **Solution**:
  - Centralized CSS selectors in `config.py` for easy maintenance.
  - Configured `WebDriverWait` with `EC.presence_of_element_located` instead of fragile `time.sleep()`.
  - Added Chrome options `--disable-blink-features=AutomationControlled` and custom User-Agent strings to pass browser checks.

### Challenge 2: Network Connection Timeouts & Offline Resiliency
- **Issue**: Web scrapers often encounter `net::ERR_CONNECTION_TIMED_OUT` when network or ISP firewalls restrict external target URLs.
- **Solution**:
  - Implemented `page_load_strategy = "eager"` so Chrome proceeds as soon as the core DOM is parsed.
  - Implemented automatic retry logic in `scraper.py`.
  - Built an automated fallback dynamic renderer (`mock_server.py`) that generates a local HTML page populated with live public API data, guaranteeing Selenium WebDriver DOM scraping succeeds under any network condition.

### Challenge 3: Numeric Data Cleaning & Historical Append Mode
- **Issue**: Scraped fields contain currency symbols (`$`), commas (`,`), percent signs (`%`), and multiplier suffixes (`B`, `T`).
- **Solution**:
  - Built `parse_numeric` in `data_handler.py` to convert strings with multipliers (`T` for Trillion, `B` for Billion, `M` for Million) into standard floating-point numbers.
  - Used `pandas.to_csv(..., mode='a', header=not file_exists)` to append timestamped records cleanly without duplicating headers.
