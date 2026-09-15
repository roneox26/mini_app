"""Boost plan listing and Telegram Stars purchase endpoints."""
from flask import request, jsonify, g, current_app
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.payment import get_boost_plans, activate_boost
from app.models import BoostPlan


@api_v1.route("/boosts", methods=["GET"])
@require_auth
def list_boosts():
    plans = get_boost_plans()
    # Attach active boost info for the current user
    from app.models import UserBoost
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    active = (
        UserBoost.query
        .filter_by(user_id=g.user_id, is_active=True)
        .filter(UserBoost.expires_at > now)
        .first()
    )
    return jsonify({
        "plans": plans,
        "active_boost": active.to_dict() if active else None,
    })


@api_v1.route("/boosts/<int:plan_id>/purchase", methods=["POST"])
@require_auth
def purchase_boost(plan_id):
    """Purchase a boost by plan ID after successful Telegram Stars payment."""
    data = request.get_json(silent=True) or {}
    charge_id = data.get("telegram_payment_charge_id")
    stars_paid = data.get("stars_paid")

    if not charge_id or stars_paid is None:
        return jsonify({"error": "telegram_payment_charge_id and stars_paid are required"}), 400

    plan = BoostPlan.query.filter_by(id=plan_id, is_active=True).first()
    if not plan:
        return jsonify({"error": "Boost plan not found"}), 404

    result, status = activate_boost(g.user, plan.name, charge_id, int(stars_paid))
    return jsonify(result), status


# Legacy route — keep for backward compatibility
@api_v1.route("/boosts/<plan_name>/buy", methods=["POST"])
@require_auth
def buy_boost_legacy(plan_name):
    data = request.get_json(silent=True) or {}
    charge_id = data.get("telegram_payment_charge_id")
    stars_paid = data.get("stars_paid")

    if not charge_id or stars_paid is None:
        return jsonify({"error": "telegram_payment_charge_id and stars_paid are required"}), 400

    result, status = activate_boost(g.user, plan_name, charge_id, int(stars_paid))
    return jsonify(result), status
