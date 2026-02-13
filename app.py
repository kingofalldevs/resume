"""
WSGI entry point for ResumeGhana.
"""

import os
import sys

# Load environment variables from .env if available
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None

if load_dotenv is not None:
    load_dotenv(override=False)

# Ensure required env vars for production
if os.environ.get("FLASK_ENV") == "production":
    required = ["SECRET_KEY", "HF_API_TOKEN"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

from app import create_app


app = create_app()
