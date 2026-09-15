"""Mining API endpoints."""
from flask import jsonify, g
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.services.mining import start_mining, get_mining_status, claim_mining


@api_v1.route("/mining/start", methods=["POST"])
@require_auth
def mining_start():
    result, status = start_mining(g.user)
    return jsonify(result), status


@api_v1.route("/mining/status", methods=["GET"])
@require_auth
def mining_status():
    result, status = get_mining_status(g.user)
    return jsonify(result), status


@api_v1.route("/mining/claim", methods=["POST"])
@require_auth
def mining_claim():
    result, status = claim_mining(g.user)
    return jsonify(result), status
