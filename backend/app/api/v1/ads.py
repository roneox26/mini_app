"""Ad reward endpoints — validates completed Monetag ad events."""
from flask import request, jsonify, g, current_app
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.rewards import process_ad_reward, get_ad_status


@api_v1.route("/ads/reward", methods=["POST"])
@require_auth
def ad_reward():
    data = request.get_json(silent=True) or {}
    ad_event_id = data.get("ad_event_id", "")
    ad_type = data.get("ad_type", "rewarded")

    result, status = process_ad_reward(g.user, ad_event_id, ad_type)
    return jsonify(result), status


@api_v1.route("/ads/config", methods=["GET"])
@require_auth
def ad_config():
    return jsonify({
        "enabled": bool(
            current_app.config.get("MONETAG_SDK_URL")
            and current_app.config.get("MONETAG_PUBLISHER_ID")
        ),
        "sdk_url": current_app.config.get("MONETAG_SDK_URL", ""),
        "publisher_id": current_app.config.get("MONETAG_PUBLISHER_ID", ""),
        "zone_id": current_app.config.get("MONETAG_ZONE_ID_REWARDED", ""),
    })


@api_v1.route("/ads/status", methods=["GET"])
@require_auth
def ad_status():
    return jsonify(get_ad_status(g.user))
