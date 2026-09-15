"""Leaderboard endpoint — top miners served from Redis cache."""
import json
from flask import jsonify, g, current_app
from app.api.v1 import api_v1
from app.security.auth import require_auth
from app.models import MiningAccount, User
from app.database import db
from sqlalchemy import desc


@api_v1.route("/leaderboard", methods=["GET"])
@require_auth
def leaderboard():
    """Return top 100 miners. Tries Redis cache first, falls back to DB."""
    try:
        import redis
        r = redis.from_url(current_app.config["REDIS_URL"])
        cached = r.get("leaderboard:top100")
        if cached:
            top_users = json.loads(cached)
            my_rank = None
            for entry in top_users:
                entry["is_me"] = entry["telegram_id"] == g.user_id
                if entry["telegram_id"] == g.user_id:
                    my_rank = entry["rank"]
                # Remove telegram_id from public response
                entry.pop("telegram_id", None)
            return jsonify({"leaderboard": top_users, "my_rank": my_rank, "from_cache": True})
    except Exception:
        pass  # Fall through to DB query

    # DB fallback
    top_rows = db.session.query(
        User.telegram_id,
        User.first_name,
        User.username,
        MiningAccount.available_coins,
        MiningAccount.mined_coins_total,
        MiningAccount.mining_rate,
    ).join(
        MiningAccount, User.telegram_id == MiningAccount.user_id
    ).filter(
        User.is_banned == False
    ).order_by(
        desc(MiningAccount.mined_coins_total)
    ).limit(100).all()

    result = []
    my_rank = None
    for rank, row in enumerate(top_rows, 1):
        if row.telegram_id == g.user_id:
            my_rank = rank
        result.append({
            "rank": rank,
            "first_name": row.first_name,
            "username": row.username,
            "coins": row.mined_coins_total,
            "mined_coins_total": row.mined_coins_total,
            "available_coins": row.available_coins,
            "mining_rate": row.mining_rate,
            "is_me": row.telegram_id == g.user_id,
        })

    return jsonify({
        "leaderboard": result,
        "my_rank": my_rank,
        "from_cache": False,
    })
