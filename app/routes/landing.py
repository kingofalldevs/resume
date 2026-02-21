"""
Landing page and public routes.
"""
from flask import Blueprint, redirect, url_for

landing_bp = Blueprint("landing", __name__)


@landing_bp.route("/")
def index():
    """Default entry now goes directly to dashboard."""
    return redirect(url_for("dashboard.index"))
