from flask import Blueprint

api_v1 = Blueprint("api_v1", __name__, url_prefix="/api/v1")

from app.api.v1 import auth, user, mining, boosts, ads, referrals, tasks, rewards, leaderboard, coins, withdrawals
