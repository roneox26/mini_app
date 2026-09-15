"""
POST /api/v1/auth/telegram
Authenticates via Telegram initData, returns JWT.
Creates user account on first login.
"""
import secrets
from datetime import datetime, timezone
from flask import request, jsonify, current_app
from app.api.v1 import api_v1
from app.database import db
from app.models import User, MiningAccount, BoostPlan, UserBoost
from app.security.telegram import validate_telegram_init_data, generate_jwt
from app.services.referral import generate_referral_code
from app.models import seed_default_tasks


@api_v1.route("/auth/test", methods=["POST"])
def auth_test():
    """DEV ONLY: Create/login a test user without Telegram initData."""
    if not current_app.config.get("DEBUG"):
        return jsonify({"error": "Not available in production"}), 403

    data = request.get_json(silent=True) or {}
    telegram_id = int(data.get("telegram_id", 999999999))
    first_name = data.get("first_name", "Test")
    username = data.get("username", "testuser")

    try:
        user = User.query.filter_by(telegram_id=telegram_id).first()
        if not user:
            from app.services.referral import generate_referral_code
            user = User(
                id=telegram_id,
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                referral_code=generate_referral_code(telegram_id),
                is_admin=(telegram_id == current_app.config.get("FIRST_ADMIN_TELEGRAM_ID")),
            )
            db.session.add(user)
            db.session.flush()
            account = MiningAccount(
                user_id=telegram_id,
                mining_rate=current_app.config["DEFAULT_MINING_RATE"],
            )
            db.session.add(account)
            _seed_boost_plans_if_empty()
            seed_default_tasks()
            db.session.commit()
        token = generate_jwt(telegram_id)
        return jsonify({"token": token, "user": user.to_dict(), "is_new_user": True}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@api_v1.route("/auth/telegram", methods=["POST"])
def auth_telegram():
    """Authenticate with Telegram initData."""
    data = request.get_json(silent=True) or {}
    init_data = data.get("initData", "")

    if not init_data:
        return jsonify({"error": "initData is required"}), 400

    # ✅ Server-side validation per Telegram docs
    user_data = validate_telegram_init_data(init_data)
    if not user_data:
        return jsonify({"error": "Invalid Telegram authentication"}), 401

    telegram_id = user_data.get("id")
    if not telegram_id:
        return jsonify({"error": "User ID not found in initData"}), 401

    try:
        user = User.query.filter_by(telegram_id=telegram_id).first()
        is_new_user = False

        if not user:
            is_new_user = True
            ref_code = generate_referral_code(telegram_id)

            # Check if user was referred
            ref_code_used = data.get("referral_code", "")
            referrer = None
            if ref_code_used:
                referrer = User.query.filter_by(referral_code=ref_code_used).first()

            user = User(
                id=telegram_id,
                telegram_id=telegram_id,
                username=user_data.get("username"),
                first_name=user_data.get("first_name", "User"),
                last_name=user_data.get("last_name"),
                photo_url=user_data.get("photo_url"),
                language_code=user_data.get("language_code"),
                is_premium=user_data.get("is_premium", False),
                referral_code=ref_code,
                referred_by_id=referrer.telegram_id if referrer else None,
                is_admin=(telegram_id == current_app.config.get("FIRST_ADMIN_TELEGRAM_ID")),
            )
            db.session.add(user)
            db.session.flush()

            # Create mining account
            account = MiningAccount(
                user_id=telegram_id,
                mining_rate=current_app.config["DEFAULT_MINING_RATE"],
            )
            db.session.add(account)

            # Record referral relationship + award Milestone 1 (Telegram verify)
            if referrer:
                from app.services.referral import process_referral_on_signup
                process_referral_on_signup(user)

            # Seed default boost plans on first boot
            _seed_boost_plans_if_empty()

            # Seed default tasks
            seed_default_tasks()

        else:
            # Update user info on each login
            user.username = user_data.get("username", user.username)
            user.first_name = user_data.get("first_name", user.first_name)
            user.last_name = user_data.get("last_name", user.last_name)
            user.is_premium = user_data.get("is_premium", user.is_premium)
            user.last_seen_at = datetime.now(timezone.utc)

        db.session.commit()

        token = generate_jwt(telegram_id)

        return jsonify({
            "token": token,
            "user": user.to_dict(),
            "is_new_user": is_new_user,
        }), 200

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Auth error: {e}")
        return jsonify({"error": "Authentication failed"}), 500


def _seed_boost_plans_if_empty():
    """Seed boost plans from spec if none exist."""
    if BoostPlan.query.count() == 0:
        plans = [
            BoostPlan(name="normal", display_name="Normal", emoji="⛏️", mining_rate=5000,  price_stars=0,   duration_days=0),
            BoostPlan(name="bronze", display_name="Bronze", emoji="🥉", mining_rate=12000, price_stars=79,  duration_days=7),
            BoostPlan(name="silver", display_name="Silver", emoji="🥈", mining_rate=30000, price_stars=159, duration_days=7),
            BoostPlan(name="gold",   display_name="Gold",   emoji="🥇", mining_rate=60000, price_stars=299, duration_days=7),
        ]
        for p in plans:
            db.session.add(p)
