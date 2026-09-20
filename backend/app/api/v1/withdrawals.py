"""Withdrawal endpoints."""
from flask import request, jsonify, g, current_app
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.withdrawal import request_withdrawal, get_withdrawal_history, get_available_methods


@api_v1.route("/withdrawals", methods=["GET"])
@require_auth
def list_withdrawals():
    history = get_withdrawal_history(g.user)
    return jsonify({
        "withdrawals": history,
        "available_methods": get_available_methods(),
        "minimum_coins": current_app.config["MIN_WITHDRAWAL_COINS"],
        "fee_percent": current_app.config["WITHDRAWAL_FEE_PERCENT"],
        "coin_value_bdt": current_app.config["COIN_REFERENCE_VALUE_BDT"],
    })


@api_v1.route("/withdrawals", methods=["POST"])
@require_auth
def create_withdrawal():
    data = request.get_json(silent=True) or {}
    amount = data.get("amount_coins")
    method = data.get("method", "")
    destination = data.get("destination", "")

    if not amount or not method:
        return jsonify({"error": "amount_coins and method are required"}), 400

    result, status = request_withdrawal(g.user, int(amount), method, destination)
    return jsonify(result), status
