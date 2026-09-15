from functools import wraps
from flask import request, jsonify, g
from app.security.telegram import decode_jwt
from app.models import User


def require_auth(f):
    """Decorator: require a valid JWT Bearer token."""
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return jsonify({"error": "Missing or invalid Authorization header"}), 401

        token = auth_header[7:]
        payload = decode_jwt(token)
        if not payload:
            return jsonify({"error": "Invalid or expired token"}), 401

        user_id = int(payload.get("sub", 0))
        user = User.query.filter_by(telegram_id=user_id).first()
        if not user:
            return jsonify({"error": "User not found"}), 401
        if user.is_banned:
            return jsonify({"error": "Account is banned"}), 403

        g.user = user
        g.user_id = user_id
        return f(*args, **kwargs)
    return decorated


def require_admin(f):
    """Decorator: require admin privileges. Must be used after @require_auth."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not getattr(g, 'user', None) or not g.user.is_admin:
            return jsonify({"error": "Admin access required"}), 403
        return f(*args, **kwargs)
    return decorated
