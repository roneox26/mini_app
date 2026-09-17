"""Celery application and background tasks."""
import os
import json
import logging
from celery import Celery
from app.config import get_config
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)


def make_celery(app_name=__name__):
    cfg = get_config()
    celery = Celery(
        app_name,
        backend=cfg.REDIS_URL,
        broker=cfg.REDIS_URL
    )
    celery.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="UTC",
        enable_utc=True,
        beat_schedule={
            "check-referral-24h-activity": {
                "task": "tasks.check_referral_24h_activity",
                "schedule": 3600.0,   # every hour
            },
            "cleanup-expired-sessions": {
                "task": "tasks.cleanup_expired_sessions",
                "schedule": 300.0,    # every 5 minutes
            },
            "update-leaderboard-cache": {
                "task": "tasks.update_leaderboard_cache",
                "schedule": 600.0,    # every 10 minutes
            },
            "deactivate-expired-boosts": {
                "task": "tasks.deactivate_expired_boosts",
                "schedule": 3600.0,   # every hour
            },
        },
    )
    return celery


celery_app = make_celery()

# Flask app singleton for tasks that need app context
_flask_app = None


def get_flask_app():
    global _flask_app
    if not _flask_app:
        from app import create_app
        _flask_app = create_app()
    return _flask_app


# ─────────────────────────────────────────────────────────────────────────────
# Task: Update Leaderboard Cache
# Pre-computes top-100 miners and stores in Redis for fast reads
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="tasks.update_leaderboard_cache")
def update_leaderboard_cache():
    """Pre-compute and cache top-100 leaderboard to Redis."""
    app = get_flask_app()
    with app.app_context():
        try:
            import redis
            from app.models import MiningAccount, User

            r = redis.from_url(app.config["REDIS_URL"])

            # Query top 100 by total mined coins
            top_accounts = (
                MiningAccount.query
                .join(User, MiningAccount.user_id == User.telegram_id)
                .filter(User.is_banned == False)
                .order_by(MiningAccount.mined_coins_total.desc())
                .limit(100)
                .all()
            )

            leaderboard = []
            for rank, account in enumerate(top_accounts, start=1):
                user = account.user
                leaderboard.append({
                    "rank": rank,
                    "telegram_id": user.telegram_id,
                    "first_name": user.first_name,
                    "username": user.username,
                    "mined_coins_total": account.mined_coins_total,
                    "available_coins": account.available_coins,
                    "mining_rate": account.mining_rate,
                })

            # Cache for 15 minutes (task runs every 10 min, extra buffer)
            r.setex("leaderboard:top100", 900, json.dumps(leaderboard))
            logger.info(f"Leaderboard cache updated with {len(leaderboard)} entries")

        except Exception as e:
            logger.error(f"Leaderboard cache update failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Task: Cleanup Expired Mining Sessions
# Auto-claims or marks abandoned sessions (>8h) as closed
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="tasks.cleanup_expired_sessions")
def cleanup_expired_sessions():
    """Auto-claim or close mining sessions that exceeded the 8-hour window."""
    app = get_flask_app()
    with app.app_context():
        try:
            from app.database import db
            from app.models import MiningAccount, MiningSession, Transaction, TransactionType

            SESSION_HOURS = app.config.get("MINING_SESSION_HOURS", 8)
            cutoff = datetime.now(timezone.utc) - timedelta(hours=SESSION_HOURS)

            # Find all accounts that are marked as mining but started > 8h ago
            expired_accounts = MiningAccount.query.filter(
                MiningAccount.is_mining == True,
                MiningAccount.last_mining_started_at <= cutoff,
            ).all()

            claimed_count = 0
            for account in expired_accounts:
                try:
                    started_at = account.last_mining_started_at
                    if started_at.tzinfo is None:
                        started_at = started_at.replace(tzinfo=timezone.utc)

                    elapsed = (datetime.now(timezone.utc) - started_at).total_seconds()
                    effective_seconds = min(elapsed, SESSION_HOURS * 3600)
                    earned = int(effective_seconds * account.mining_rate / 3600)

                    if earned > 0:
                        balance_before = account.available_coins
                        account.available_coins += earned
                        account.mined_coins_total += earned

                        # Mark open session as claimed
                        open_session = MiningSession.query.filter_by(
                            mining_account_id=account.id,
                            is_claimed=False,
                        ).order_by(MiningSession.started_at.desc()).first()

                        now = datetime.now(timezone.utc)
                        if open_session:
                            open_session.is_claimed = True
                            open_session.claimed_at = now
                            open_session.coins_earned = earned

                        # Ledger entry
                        tx = Transaction(
                            user_id=account.user_id,
                            type=TransactionType.MINING,
                            amount=earned,
                            balance_before=balance_before,
                            balance_after=account.available_coins,
                            reference_id=f"auto_claim_{account.id}",
                            note="Auto-claimed by system (session expired)",
                        )
                        db.session.add(tx)

                    account.is_mining = False
                    account.last_claimed_at = datetime.now(timezone.utc)
                    claimed_count += 1

                except Exception as inner_e:
                    logger.warning(f"Failed to auto-claim for account {account.id}: {inner_e}")
                    db.session.rollback()
                    continue

            db.session.commit()
            logger.info(f"Cleanup: auto-claimed {claimed_count} expired mining sessions")

        except Exception as e:
            logger.error(f"Cleanup expired sessions failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Task: Deactivate Expired Boosts
# Sets is_active=False for boosts past their expires_at date
# Resets mining_rate to default (10/hr)
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="tasks.deactivate_expired_boosts")
def deactivate_expired_boosts():
    """Deactivate boosts whose expires_at has passed and reset mining rate."""
    app = get_flask_app()
    with app.app_context():
        try:
            from app.database import db
            from app.models import UserBoost, MiningAccount

            now = datetime.now(timezone.utc)
            expired_boosts = UserBoost.query.filter(
                UserBoost.is_active == True,
                UserBoost.expires_at != None,
                UserBoost.expires_at <= now,
            ).all()

            default_rate = app.config.get("DEFAULT_MINING_RATE", 10)
            deactivated = 0

            for boost in expired_boosts:
                boost.is_active = False

                # Reset mining account rate to default
                account = MiningAccount.query.filter_by(user_id=boost.user_id).first()
                if account and account.active_boost_id == boost.id:
                    account.mining_rate = default_rate
                    account.active_boost_id = None

                deactivated += 1

            db.session.commit()
            logger.info(f"Deactivated {deactivated} expired boosts")

        except Exception as e:
            logger.error(f"Deactivate expired boosts failed: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Task: Check Referral 24h Activity
# Awards +250 coins to referrer when referee is active for 24h
# ─────────────────────────────────────────────────────────────────────────────
@celery_app.task(name="tasks.check_referral_24h_activity")
def check_referral_24h_activity():
    """Check all referrals for 24h activity reward."""
    from app.services.referral import check_and_reward_24h_activity
    app = get_flask_app()
    with app.app_context():
        try:
            from app.models import User

            # Get all referred users who joined 24-48 hours ago
            cutoff_end = datetime.now(timezone.utc) - timedelta(hours=24)
            cutoff_start = cutoff_end - timedelta(hours=24)

            users = User.query.filter(
                User.created_at >= cutoff_start,
                User.created_at <= cutoff_end,
                User.referred_by_id.isnot(None),
            ).all()

            rewarded = 0
            for user in users:
                try:
                    check_and_reward_24h_activity(user)
                    rewarded += 1
                except Exception as inner_e:
                    logger.warning(f"24h reward failed for user {user.telegram_id}: {inner_e}")

            logger.info(f"Checked 24h activity for {len(users)} users, rewarded {rewarded}")

        except Exception as e:
            logger.error(f"check_referral_24h_activity failed: {e}")
