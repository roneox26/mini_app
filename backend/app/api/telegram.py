"""Telegram bot webhook routes served by the main web service."""
import logging

import requests
from flask import Blueprint, current_app, jsonify, request

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

    pre_checkout = update.get("pre_checkout_query")
    if pre_checkout:
        requests.post(
            _telegram_url("answerPreCheckoutQuery"),
            json={"pre_checkout_query_id": pre_checkout["id"], "ok": True},
            timeout=15,
        )


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
