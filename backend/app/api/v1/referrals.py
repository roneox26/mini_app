"""Referral endpoints."""
from flask import jsonify, g, current_app
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.referral import get_referral_stats
from app.models import Referral, User


@api_v1.route("/referrals", methods=["GET"])
@require_auth
def list_referrals():
    referrals = Referral.query.filter_by(referrer_id=g.user_id).all()
    return jsonify({
        "referrals": [r.to_dict() for r in referrals],
        "total": len(referrals),
    })


@api_v1.route("/referrals/stats", methods=["GET"])
@require_auth
def referral_stats():
    stats = get_referral_stats(g.user)
    bot_username = (current_app.config.get("TELEGRAM_BOT_USERNAME") or "YourBot").lstrip("@")
    stats["referral_link"] = f"https://t.me/{bot_username}?start={g.user.referral_code}"
    return jsonify(stats)
