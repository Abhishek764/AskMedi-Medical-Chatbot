"""Application-wide error handlers."""
from flask import jsonify, render_template, request

from app.extensions import db


def register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(e):
        if request.path.startswith("/api/"):
            return jsonify(error="not found"), 404
        return render_template("error.html", code=404, message="Page not found"), 404

    @app.errorhandler(429)
    def too_many(e):
        if request.path.startswith("/api/"):
            return jsonify(error="rate limit exceeded"), 429
        return render_template("error.html", code=429, message="Too many requests"), 429

    @app.errorhandler(500)
    def server_error(e):
        db.session.rollback()
        app.logger.exception("Unhandled server error")
        if request.path.startswith("/api/"):
            return jsonify(error="internal server error"), 500
        return render_template("error.html", code=500, message="Something went wrong"), 500
