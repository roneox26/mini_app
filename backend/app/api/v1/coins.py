"""Coins purchase endpoint — Telegram Stars coin packages."""
from flask import request, jsonify, g, current_app
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.payment import process_coin_purchase


@api_v1.route("/coins/purchase", methods=["GET"])
@require_auth
def list_packages():
    packages = current_app.config["COIN_PACKAGES"]
    return jsonify({"packages": packages})


@api_v1.route("/coins/purchase", methods=["POST"])
@require_auth
def buy_coins():
    data = request.get_json(silent=True) or {}
    stars_paid = data.get("stars_paid")
    charge_id = data.get("telegram_payment_charge_id")

    if not stars_paid or not charge_id:
        return jsonify({"error": "stars_paid and telegram_payment_charge_id are required"}), 400

    result, status = process_coin_purchase(g.user, int(stars_paid), charge_id)
    return jsonify(result), status
