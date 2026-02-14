import os
import sys

# Import the real Flask app with all blueprints/templates/routes.
from app import app  # noqa: E402


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "false").lower() in ("true", "1", "on")

    # Keep local startup checks minimal and explicit.
    if os.environ.get("FLASK_ENV") == "production":
        required = ["SECRET_KEY", "DATABASE_URL"]
        missing = [name for name in required if not os.environ.get(name)]
        if missing:
            print(f"ERROR: Missing required env vars: {', '.join(missing)}", file=sys.stderr)
            sys.exit(1)

    app.run(host="0.0.0.0", port=port, debug=debug)
