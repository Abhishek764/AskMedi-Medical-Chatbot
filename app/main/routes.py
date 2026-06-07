"""Public pages + health check."""
from flask import Blueprint, render_template
from flask_login import current_user

from app.extensions import db

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def landing():
    return render_template("landing.html", user=current_user)


@main_bp.route("/disclaimer")
def disclaimer():
    return render_template("disclaimer.html")


@main_bp.route("/healthz")
def healthz():
    # Lightweight readiness probe for Render
    try:
        db.session.execute(db.text("SELECT 1"))
        return {"status": "ok"}, 200
    except Exception:
        return {"status": "degraded"}, 503
