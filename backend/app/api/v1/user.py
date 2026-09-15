"""GET /api/v1/me and /api/v1/me/balance"""
from flask import jsonify, g
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.models import MiningAccount, Transaction, UserBoost
from app.services.economy import normal_mining_rate
from datetime import datetime, timezone


@api_v1.route("/me", methods=["GET"])
@require_auth
def get_profile():
    """Get current user's profile."""
    user = g.user
    account = user.mining_account

    # Active boost info
    active_boost = None
    if account and account.active_boost_id:
        boost = UserBoost.query.get(account.active_boost_id)
        if boost and boost.is_active:
            if boost.expires_at:
                if boost.expires_at.replace(tzinfo=timezone.utc) > datetime.now(timezone.utc):
                    active_boost = boost.to_dict()
                else:
                    # Boost expired — reset mining rate
                    account.mining_rate = normal_mining_rate()
                    account.active_boost_id = None
                    from app.database import db
                    db.session.commit()
            else:
                active_boost = boost.to_dict()

    return jsonify({
        "user": user.to_dict(),
        "balance": account.to_dict() if account else {},
        "active_boost": active_boost,
    })


@api_v1.route("/me/balance", methods=["GET"])
@require_auth
def get_balance():
    """Get balance summary."""
    account = g.user.mining_account
    if not account:
        return jsonify({"available_coins": 0, "pending_coins": 0, "total": 0})

    return jsonify({
        "available_coins": account.available_coins,
        "pending_coins": account.pending_coins,
        "total": account.available_coins + account.pending_coins,
        "mined_total": account.mined_coins_total,
        "purchased_total": account.purchased_coins,
    })


@api_v1.route("/me/transactions", methods=["GET"])
@require_auth
def get_transactions():
    """Get recent transactions (ledger history)."""
    txs = Transaction.query.filter_by(
        user_id=g.user_id
    ).order_by(Transaction.created_at.desc()).limit(50).all()
    return jsonify({"transactions": [t.to_dict() for t in txs]})
