"""
Telegram Bot — Main handler
Sends Mini App button, handles referral links, and processes webhooks.
"""
import os
import logging
import json
from dotenv import load_dotenv
import requests
from flask import Flask, request, jsonify

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
MINI_APP_URL = os.getenv("FRONTEND_URL", "https://yourdomain.com")
BACKEND_URL = os.getenv("BACKEND_URL", "http://backend:5000")
API_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Flask app for webhook endpoint
app = Flask(__name__)


def send_message(chat_id, text, reply_markup=None):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if reply_markup:
        payload["reply_markup"] = reply_markup
    return requests.post(f"{API_URL}/sendMessage", json=payload)


def handle_update(update: dict):
    """Process incoming Telegram updates."""
    # Handle message (commands, text)
    message = update.get("message")
    if message:
        chat_id = message["chat"]["id"]
        text = message.get("text", "")
        user = message.get("from", {})

        # /start command
        if text.startswith("/start"):
            parts = text.split(maxsplit=1)
            ref_code = parts[1] if len(parts) > 1 else None

            app_url = MINI_APP_URL
            if ref_code:
                app_url = f"{MINI_APP_URL}?ref={ref_code}"

            first_name = user.get("first_name", "Miner")

            welcome_text = (
                f"⛏️ <b>Welcome to Mining App, {first_name}!</b>\n\n"
                f"🪙 Auto-mine coins 24/7\n"
                f"🚀 Boost your mining rate\n"
                f"👥 Earn from referrals\n"
                f"🎁 Daily streak rewards\n\n"
                f"<i>Open the app below to start mining!</i>"
            )

            keyboard = {
                "inline_keyboard": [[
                    {
                        "text": "⛏️ Open Mining App",
                        "web_app": {"url": app_url}
                    }
                ], [
                    {
                        "text": "👥 Invite Friends",
                        "switch_inline_query": f"ref_{chat_id}"
                    }
                ]]
            }

            send_message(chat_id, welcome_text, keyboard)

        # Handle successful_payment (Telegram Stars payment confirmation)
        if message.get("successful_payment"):
            payment = message["successful_payment"]
            logger.info(f"Successful payment: {payment}")
            requests.post(
                f"{BACKEND_URL}/webhook/payment",
                json={"user": user, "payment": payment},
                timeout=15,
            )

    # Handle callback queries (inline button presses)
    callback_query = update.get("callback_query")
    if callback_query:
        logger.info(f"Callback query: {callback_query}")

    # Handle pre_checkout_query (for payment validation)
    pre_checkout = update.get("pre_checkout_query")
    if pre_checkout:
        # Always answer OK for now - in production validate the payload
        requests.post(f"{API_URL}/answerPreCheckoutQuery", json={
            "pre_checkout_query_id": pre_checkout["id"],
            "ok": True
        })


@app.route("/webhook", methods=["POST"])
def webhook():
    """Telegram webhook endpoint."""
    try:
        update = request.get_json()
        if update:
            handle_update(update)
        return jsonify({"ok": True}), 200
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "telegram-bot"}), 200


def set_webhook(webhook_url: str):
    """Set the Telegram webhook URL."""
    res = requests.post(f"{API_URL}/setWebhook", json={"url": webhook_url})
    return res.json()


def delete_webhook():
    """Delete the Telegram webhook."""
    res = requests.post(f"{API_URL}/deleteWebhook")
    return res.json()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        if sys.argv[1] == "set_webhook":
            url = sys.argv[2] if len(sys.argv) > 2 else ""
            print(set_webhook(url))
        elif sys.argv[1] == "delete_webhook":
            print(delete_webhook())
        elif sys.argv[1] == "run":
            # Run Flask app for webhook
            port = int(os.getenv("PORT", os.getenv("BOT_PORT", 8080)))
            app.run(host="0.0.0.0", port=port, debug=False)
    else:
        print("Usage: python bot.py [set_webhook|delete_webhook|run] [url]")
