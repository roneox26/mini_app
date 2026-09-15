"""Daily reward endpoints."""
from flask import jsonify, g
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.rewards import claim_daily_reward, get_daily_status


@api_v1.route("/rewards/daily", methods=["GET"])
@require_auth
def daily_status():
    return jsonify(get_daily_status(g.user))


@api_v1.route("/rewards/daily", methods=["POST"])
@require_auth
def claim_daily():
    result, status = claim_daily_reward(g.user)
    return jsonify(result), status
