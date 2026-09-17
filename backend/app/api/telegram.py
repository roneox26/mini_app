"""Telegram bot webhook routes served by the main web service."""
import logging

import requests
from flask import Blueprint, current_app, jsonify, request
from app.models import BoostPlan, User
from app.services.payment import activate_boost

logger = logging.getLogger(__name__)
telegram_bp = Blueprint("telegram", __name__)


def _telegram_url(method):
    token = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
    return f"https://api.telegram.org/bot{token}/{method}"


def _send_message(chat_id, text, reply_markup=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return requests.post(_telegram_url("sendMessage"), json=payload, timeout=15)


def _handle_update(update):
    message = update.get("message")
    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = message.get("from", {})

        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            referral_code = parts[1] if len(parts) > 1 else None
            app_url = current_app.config.get("FRONTEND_URL", "")
            if referral_code:
                app_url = f"{app_url}?ref={referral_code}"

            first_name = user.get("first_name", "Miner")
            keyboard = {
                "inline_keyboard": [
                    [{"text": "Open Mining App", "web_app": {"url": app_url}}],
                    [{"text": "Invite Friends", "switch_inline_query": f"ref_{chat_id}"}],
                ]
            }
            _send_message(
                chat_id,
                (
                    f"<b>Welcome to Mining App, {first_name}!</b>\n\n"
                    "Open the app below to start mining coins."
                ),
                keyboard,
            )

        payment = message.get("successful_payment")
        if payment:
            _activate_successful_payment(user, payment)

    pre_checkout = update.get("pre_checkout_query")
    if pre_checkout:
        requests.post(
            _telegram_url("answerPreCheckoutQuery"),
            json={"pre_checkout_query_id": pre_checkout["id"], "ok": True},
            timeout=15,
        )


def _activate_successful_payment(telegram_user, payment):
    payload = payment.get("invoice_payload", "")
    parts = payload.split(":")
    if len(parts) != 3 or parts[0] != "boost":
        logger.warning("Unknown payment payload: %s", payload)
        return

    try:
        plan_id = int(parts[1])
        user_id = int(parts[2])
    except ValueError:
        logger.warning("Invalid payment payload: %s", payload)
        return
    if int(telegram_user.get("id", 0)) != user_id:
        logger.warning("Payment user mismatch for payload: %s", payload)
        return

    user = User.query.filter_by(telegram_id=user_id).first()
    plan = BoostPlan.query.filter_by(id=plan_id, is_active=True).first()
    if not user or not plan:
        logger.warning("Payment references missing user or plan: %s", payload)
        return

    result, status = activate_boost(
        user,
        plan.name,
        payment.get("telegram_payment_charge_id", ""),
        int(payment.get("total_amount", 0)),
    )
    if status != 200:
        logger.error("Boost activation failed for %s: %s", user_id, result)


@telegram_bp.post("/webhook")
def webhook():
    try:
        update = request.get_json(silent=True)
        if update:
            _handle_update(update)
        return jsonify({"ok": True}), 200
    except Exception as error:
        logger.exception("Telegram webhook failed: %s", error)
        return jsonify({"ok": False}), 500


@telegram_bp.post("/webhook/payment")
def payment_webhook():
    """Accept successful payments forwarded by the dedicated bot service."""
    data = request.get_json(silent=True) or {}
    telegram_user = data.get("user") or {}
    payment = data.get("payment") or {}
    if not telegram_user.get("id") or not payment.get("invoice_payload"):
        return jsonify({"ok": False, "error": "Invalid payment payload"}), 400

    _activate_successful_payment(telegram_user, payment)
    return jsonify({"ok": True}), 200
