"""
WSGI entry point for ResumeGhana.
"""

import os
import sys

from app import app

# Ensure required env vars for production
if os.environ.get("FLASK_ENV") == "production":
    required = ["SECRET_KEY", "HF_API_TOKEN"]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"ERROR: Missing: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "on")
    app.run(host="0.0.0.0", port=port, debug=debug)
