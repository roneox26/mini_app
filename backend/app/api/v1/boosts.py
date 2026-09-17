"""Boost plan listing and Telegram Stars purchase endpoints."""
import requests
from flask import request, jsonify, g, current_app
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.payment import get_boost_plans, activate_boost
from app.models import BoostPlan, seed_boost_plans


@api_v1.route("/boosts", methods=["GET"])
@require_auth
def list_boosts():
    if BoostPlan.query.count() == 0:
        seed_boost_plans()
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


@api_v1.route("/boosts/<int:plan_id>/invoice", methods=["POST"])
@require_auth
def create_boost_invoice(plan_id):
    """Create a Telegram Stars invoice for a paid boost plan."""
    plan = BoostPlan.query.filter_by(id=plan_id, is_active=True).first()
    if not plan:
        return jsonify({"error": "Boost plan not found"}), 404
    if plan.price_stars <= 0:
        return jsonify({"error": "This is a free plan"}), 400

    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        return jsonify({"error": "Telegram payments are not configured"}), 503

    response = requests.post(
        f"https://api.telegram.org/bot{token}/createInvoiceLink",
        json={
            "title": f"{plan.display_name} Mining Boost",
            "description": f"Increase your mining rate for {plan.duration_days} days.",
            "payload": f"boost:{plan.id}:{g.user_id}",
            "currency": "XTR",
            "prices": [{"label": plan.display_name, "amount": plan.price_stars}],
        },
        timeout=15,
    )
    data = response.json()
    if not response.ok or not data.get("ok"):
        current_app.logger.error("Telegram invoice creation failed: %s", data)
        return jsonify({"error": "Could not create payment invoice"}), 502
    return jsonify({"invoice_url": data["result"]})


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
