import hashlib
import hmac
import json
import time
from urllib.parse import unquote, parse_qsl

import jwt
from flask import current_app


def validate_telegram_init_data(init_data: str) -> dict | None:
    """
    Validate Telegram Mini App initData per official Telegram documentation.
    Returns parsed user data dict if valid, None if invalid.

    Reference: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    try:
        # Parse the query string
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))

        # Extract and remove hash from data
        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        # Check auth_date is not too old (max 24 hours)
        auth_date = int(parsed.get("auth_date", 0))
        if time.time() - auth_date > 86400:
            current_app.logger.warning("Telegram initData expired (auth_date too old)")
            return None

        # Build the data check string (sorted alphabetically)
        data_check_string = "\n".join(
            f"{k}={v}" for k, v in sorted(parsed.items())
        )

        # Create secret key using HMAC-SHA256
        bot_token = current_app.config["TELEGRAM_BOT_TOKEN"]
        secret_key = hmac.new(
            b"WebAppData",
            bot_token.encode("utf-8"),
            hashlib.sha256
        ).digest()

        # Compute expected hash
        expected_hash = hmac.new(
            secret_key,
            data_check_string.encode("utf-8"),
            hashlib.sha256
        ).hexdigest()

        # Constant-time compare to prevent timing attacks
        if not hmac.compare_digest(expected_hash, received_hash):
            current_app.logger.warning("Telegram initData hash mismatch")
            return None

        # Parse user data
        user_data_str = parsed.get("user", "{}")
        user_data = json.loads(unquote(user_data_str))
        return user_data

    except Exception as e:
        current_app.logger.error(f"initData validation error: {e}")
        return None


def generate_jwt(user_id: int, extra: dict = None) -> str:
    """Generate a JWT token for the user."""
    payload = {
        "sub": str(user_id),
        "iat": int(time.time()),
        "exp": int(time.time()) + (current_app.config["JWT_EXPIRY_HOURS"] * 3600),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, current_app.config["JWT_SECRET_KEY"], algorithm="HS256")


def decode_jwt(token: str) -> dict | None:
    """Decode and verify a JWT token."""
    try:
        return jwt.decode(token, current_app.config["JWT_SECRET_KEY"], algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None
