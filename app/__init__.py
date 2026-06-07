"""Application factory for AskMedi."""
import logging

from flask import Flask

from app.config import get_config
from app.extensions import csrf, db, limiter, login_manager, migrate


def create_app(config_object=None):
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_object or get_config())

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    # Logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    # Models must be imported so migrations/user_loader see them
    from app import models  # noqa: F401

    @login_manager.user_loader
    def load_user(user_id):
        try:
            return db.session.get(models.User, int(user_id))
        except (TypeError, ValueError):
            return None

    # Blueprints
    from app.auth.routes import auth_bp
    from app.chat.routes import chat_bp
    from app.main.routes import main_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)

    # Error handlers
    from app.errors import register_error_handlers

    register_error_handlers(app)

    # CLI: create tables for first deploy (idempotent). Use Flask-Migrate
    # (`flask db upgrade`) once migrations are generated for schema changes.
    @app.cli.command("init-db")
    def init_db():
        """Create database tables if they do not exist."""
        db.create_all()
        app.logger.info("Database tables ensured.")

    return app
