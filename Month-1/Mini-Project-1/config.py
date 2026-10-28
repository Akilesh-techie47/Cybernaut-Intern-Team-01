import os

# Target configuration
TARGET_URL = "https://coinmarketcap.com/"

# Scraping settings
HEADLESS = True
TOP_N = 10
TIMEOUT = 20  # Explicit wait timeout in seconds

# Data storage paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CSV_PATH = os.path.join(DATA_DIR, "crypto_prices.csv")

# Filter settings (Optional)
# PRICE_THRESHOLD: Set a minimum USD price filter (e.g., 100.0 or None)
PRICE_THRESHOLD = None

# TOP_GAINERS_ONLY: Set to True to filter only coins with positive 24h change
TOP_GAINERS_ONLY = False

# User agent string to prevent automation detection
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/122.0.0.0 Safari/537.36"
)

# Selectors (centralized for easy updates if DOM structure changes)
TABLE_ROW_SELECTOR = "table tbody tr"
