"""
Rewards Service — Daily streak rewards + Ad rewards.

Daily 7-day streak schedule (total = 220,000 coins):
  Day 1:  5,000
  Day 2: 10,000
  Day 3: 15,000
  Day 4: 20,000
  Day 5: 30,000
  Day 6: 40,000
  Day 7: 100,000

Ad rewards:
  +250 coins per completed rewarded ad
  Max 5 ads/user/day = max 1,250 coins/day
  Per-user cooldown enforced via Redis
"""
from datetime import datetime, timezone, date, timedelta
from flask import current_app
import redis

from app.database import db
from app.models import UserDailyReward, AdReward, Transaction, TransactionType, MiningAccount

# Canonical daily reward schedule — matches spec exactly
DAILY_SCHEDULE = {
    1: 5000,
    2: 10000,
    3: 15000,
    4: 20000,
    5: 30000,
    6: 40000,
    7: 100000,
}


def claim_daily_reward(user: "User") -> tuple[dict, int]:
    """Claim today's daily login reward, maintaining streak."""
    today = date.today()

    record = UserDailyReward.query.filter_by(user_id=user.telegram_id).first()
    if not record:
        record = UserDailyReward(user_id=user.telegram_id, current_streak=0)
        db.session.add(record)
        db.session.flush()

    # Duplicate claim prevention
    if record.last_claimed_date == today:
        return {"error": "Daily reward already claimed today"}, 400

    # Streak logic
    yesterday = today - timedelta(days=1)
    if record.last_claimed_date == yesterday:
        # Continue streak, cap at 7 then cycle
        new_streak = (record.current_streak % 7) + 1
    else:
        # Missed a day — reset to day 1
        new_streak = 1

    record.current_streak = new_streak
    reward = DAILY_SCHEDULE[new_streak]

    account = (
        MiningAccount.query
        .filter_by(user_id=user.telegram_id)
        .with_for_update()
        .first()
    )
    if not account:
        return {"error": "Mining account not found"}, 404

    try:
        balance_before = account.available_coins
        account.available_coins += reward
        record.last_claimed_date = today
        record.total_days_claimed += 1

        tx = Transaction(
            user_id=user.telegram_id,
            type=TransactionType.DAILY_REWARD,
            amount=reward,
            balance_before=balance_before,
            balance_after=account.available_coins,
            source="available",
            reference_id=f"daily_day_{new_streak}_{today.isoformat()}",
        )
        db.session.add(tx)
        db.session.commit()

        next_day = (new_streak % 7) + 1
        return {
            "status": "claimed",
            "day": new_streak,
            "coins_earned": reward,
            "streak": new_streak,
            "new_balance": account.available_coins,
            "next_reward": DAILY_SCHEDULE[next_day],
            "schedule": DAILY_SCHEDULE,
        }, 200

    except Exception as e:
        db.session.rollback()
        return {"error": f"Claim failed: {str(e)}"}, 500


def get_daily_status(user: "User") -> dict:
    today = date.today()
    record = UserDailyReward.query.filter_by(user_id=user.telegram_id).first()

    if not record:
        return {
            "current_streak": 0,
            "can_claim_today": True,
            "last_claimed_date": None,
            "next_reward": DAILY_SCHEDULE[1],
            "schedule": DAILY_SCHEDULE,
        }

    can_claim = record.last_claimed_date != today
    next_day = (record.current_streak % 7) + 1 if can_claim else ((record.current_streak % 7) + 1)
    return {
        "current_streak": record.current_streak,
        "can_claim_today": can_claim,
        "last_claimed_date": record.last_claimed_date.isoformat() if record.last_claimed_date else None,
        "next_reward": DAILY_SCHEDULE.get(next_day, DAILY_SCHEDULE[1]),
        "schedule": DAILY_SCHEDULE,
    }


def process_ad_reward(user: "User", ad_event_id: str, ad_type: str = "rewarded") -> tuple[dict, int]:
    """
    Process a validated ad reward.
    - Enforces per-user cooldown via Redis
    - Enforces daily limit (max 5 ads = max 1,250 coins/day)
    - Deduplicates by ad_event_id
    - Never rewards on button click alone — requires valid event ID
    """
    if not ad_event_id:
        return {"error": "ad_event_id is required"}, 400

    r = redis.from_url(current_app.config["REDIS_URL"])
    cooldown_key = f"ad_cooldown:{user.telegram_id}"
    daily_key = f"ad_daily:{user.telegram_id}:{date.today().isoformat()}"

    # Check cooldown
    if r.exists(cooldown_key):
        ttl = r.ttl(cooldown_key)
        return {"error": f"Ad cooldown active. Wait {ttl} seconds."}, 429

    # Check daily limit
    daily_count = int(r.get(daily_key) or 0)
    daily_limit = current_app.config.get("AD_DAILY_LIMIT", 5)
    if daily_count >= daily_limit:
        return {"error": f"Daily ad limit ({daily_limit}) reached. Max {daily_limit * current_app.config.get('AD_REWARD_COINS', 250):,} coins/day."}, 429

    # Deduplicate by event ID
    existing = AdReward.query.filter_by(ad_event_id=ad_event_id).first()
    if existing:
        return {"error": "Duplicate ad event"}, 409

    reward_coins = current_app.config.get("AD_REWARD_COINS", 250)
    account = (
        MiningAccount.query
        .filter_by(user_id=user.telegram_id)
        .with_for_update()
        .first()
    )
    if not account:
        return {"error": "Mining account not found"}, 404

    try:
        balance_before = account.available_coins
        account.available_coins += reward_coins

        ad_record = AdReward(
            user_id=user.telegram_id,
            ad_event_id=ad_event_id,
            coins_awarded=reward_coins,
            ad_type=ad_type,
        )
        db.session.add(ad_record)

        tx = Transaction(
            user_id=user.telegram_id,
            type=TransactionType.AD_REWARD,
            amount=reward_coins,
            balance_before=balance_before,
            balance_after=account.available_coins,
            source="available",
            reference_id=ad_event_id,
        )
        db.session.add(tx)
        db.session.commit()

        # Set cooldown and increment daily counter
        cooldown_secs = current_app.config.get("AD_COOLDOWN_MINUTES", 5) * 60
        r.setex(cooldown_key, cooldown_secs, 1)
        r.incr(daily_key)
        r.expire(daily_key, 86400)

        # Check if 2x mining boost should be applied
        boost_applied = _apply_ad_mining_boost(user, account, r)

        return {
            "status": "rewarded",
            "coins_earned": reward_coins,
            "new_balance": account.available_coins,
            "daily_count": daily_count + 1,
            "daily_limit": daily_limit,
            "daily_remaining": daily_limit - (daily_count + 1),
            "boost_applied": boost_applied,
        }, 200

    except Exception as e:
        db.session.rollback()
        return {"error": f"Ad reward failed: {str(e)}"}, 500


def _apply_ad_mining_boost(user: "User", account: MiningAccount, r: redis.Redis) -> bool:
    """
    Optionally apply 2x mining boost for 30 minutes from ad.
    Does not stack — only applies if no active boost.
    """
    boost_key = f"ad_boost:{user.telegram_id}"
    if r.exists(boost_key):
        return False  # Already has boost, no stacking

    boost_minutes = current_app.config.get("AD_2X_DURATION_MINUTES", 30)
    boost_expires = datetime.now(timezone.utc) + timedelta(minutes=boost_minutes)
    account.ad_boost_expires_at = boost_expires
    r.setex(boost_key, boost_minutes * 60, 1)
    return True


def get_ad_status(user: "User") -> dict:
    r = redis.from_url(current_app.config["REDIS_URL"])
    cooldown_key = f"ad_cooldown:{user.telegram_id}"
    daily_key = f"ad_daily:{user.telegram_id}:{date.today().isoformat()}"

    cooldown_ttl = r.ttl(cooldown_key) if r.exists(cooldown_key) else 0
    daily_count = int(r.get(daily_key) or 0)
    daily_limit = current_app.config.get("AD_DAILY_LIMIT", 5)
    reward_coins = current_app.config.get("AD_REWARD_COINS", 250)

    return {
        "can_watch": cooldown_ttl <= 0 and daily_count < daily_limit,
        "cooldown_seconds": max(0, cooldown_ttl),
        "daily_count": daily_count,
        "daily_limit": daily_limit,
        "daily_remaining": max(0, daily_limit - daily_count),
        "reward_coins": reward_coins,
        "max_daily_coins": daily_limit * reward_coins,
    }
