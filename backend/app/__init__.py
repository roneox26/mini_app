"""
Flask Application Factory
"""
from pathlib import Path
import hashlib

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from app.config import get_config
from app.database import init_db


def rate_limit_key():
    """Use the authenticated client as the quota key when available."""
    authorization = request.headers.get("Authorization", "")
    if authorization.startswith("Bearer "):
        token = authorization[7:].strip()
        if token:
            return f"token:{hashlib.sha256(token.encode()).hexdigest()}"

    # Telegram auth has no Bearer token yet; isolate users by their signed initData.
    if request.path.endswith("/auth/telegram"):
        data = request.get_json(silent=True) or {}
        init_data = data.get("initData", "")
        if init_data:
            return f"init:{hashlib.sha256(init_data.encode()).hexdigest()}"

    return f"ip:{get_remote_address()}"


limiter = Limiter(key_func=rate_limit_key)


def create_app(config=None):
    app = Flask(__name__)
    project_root = Path(__file__).resolve().parents[2]
    frontend_root = project_root / "frontend"
    admin_root = project_root / "admin"

    # Load config
    cfg = config or get_config()
    app.config.from_object(cfg)

    # CORS — allow Telegram WebApp origins
    CORS(app, origins=app.config.get("ALLOWED_ORIGINS", ["*"]), supports_credentials=True)

    # Rate limiting via Redis
    limiter.init_app(app)

    # Database
    init_db(app)

    # Register blueprints
    from app.api.v1 import api_v1
    app.register_blueprint(api_v1)

    from app.api.v1.admin import admin_bp
    app.register_blueprint(admin_bp)

    from app.api.telegram import telegram_bp
    app.register_blueprint(telegram_bp)

    # Health check
    @app.route("/")
    def root():
        return send_from_directory(frontend_root, "index.html")

    @app.route("/admin", defaults={"filename": "index.html"})
    @app.route("/admin/<path:filename>")
    def admin_files(filename):
        requested = admin_root / filename
        if requested.is_file():
            return send_from_directory(admin_root, filename)
        return send_from_directory(admin_root, "index.html")

    @app.route("/<path:filename>")
    def frontend_files(filename):
        if filename.startswith("api/"):
            return jsonify({"error": "Not found"}), 404
        requested = frontend_root / filename
        if requested.is_file():
            return send_from_directory(frontend_root, filename)
        return send_from_directory(frontend_root, "index.html")

    @app.route("/health")
    @limiter.exempt
    def health():
        return jsonify({"status": "ok", "service": "telegram-mining-api"}), 200

    # Error handlers
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": "Not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(e):
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(429)
    def rate_limit_exceeded(e):
        """Handle rate limit errors gracefully."""
        return jsonify({
            "error": "Too many requests",
            "message": "Please try again later. The system is handling many requests.",
            "retry_after": 60
        }), 429

    @app.errorhandler(500)
    def internal_error(e):
        """Handle internal server errors."""
        return jsonify({
            "error": "Internal server error",
            "message": "An unexpected error occurred. Please try again later."
        }), 500

    @app.before_request
    def before_request():
        """Optimize database connection handling."""
        pass

    @app.teardown_appcontext
    def shutdown_session(exception=None):
        """Ensure clean database session cleanup."""
        if exception and hasattr(db, 'session'):
            db.session.rollback()
        db.session.remove()

    @app.errorhandler(429)
    def rate_limited(e):
        return jsonify({"error": "Too many requests"}), 429

    @app.errorhandler(500)
    def internal_error(e):
        app.logger.error(f"Internal error: {e}")
        return jsonify({"error": "Internal server error"}), 500

    return app
