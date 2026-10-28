"""PhishShift Message Risk Scanner - Main Application Entrypoint.

Directly hostable on:
- Streamlit Community Cloud
- Hugging Face Spaces
- Docker / Render / Railway / Google Cloud Run
- Local machines (Windows / macOS / Linux)
"""
import sys
import os

# Add root and phishshift directories to system path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

PHISHSHIFT_DIR = os.path.join(ROOT_DIR, "phishshift")
if os.path.isdir(PHISHSHIFT_DIR) and PHISHSHIFT_DIR not in sys.path:
    sys.path.insert(0, PHISHSHIFT_DIR)

# Forward to the modern Streamlit UI implementation
from phishshift.src import streamlit_ui

if __name__ == "__main__":
    streamlit_ui.main()
