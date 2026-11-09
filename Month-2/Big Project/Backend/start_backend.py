#!/usr/bin/env python3
"""Start the AeroDelay AI FastAPI backend."""

import os
import sys
import uvicorn

def main():
    # AVIATIONSTACK_ACCESS_KEY is loaded server-side from .env by app_backend.
    # Never hardcode credentials here and never print them.
    print("Starting AeroDelay AI Backend...")
    print("API will be available at http://127.0.0.1:8000")
    print("Press Ctrl+C to stop")
    uvicorn.run("app_backend:app", host="0.0.0.0", port=8000, reload=False)

if __name__ == "__main__":
    main()