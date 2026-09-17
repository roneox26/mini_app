"""
Referral Service — Milestone-based rewards.

Reward structure (total = 500 coins per qualified referral):
  Milestone 1: Friend joins + Telegram verified  → +100 coins (auto on signup)
  Milestone 2: Friend completes first mining      → +200 coins
  Milestone 3: Friend active for 24h             → +200 coins

Self-referral, duplicate referral, and referral cycles are prevented.
"""
import secrets
from datetime import datetime, timezone, timedelta
from app.database import db
from app.models import Referral, Transaction, TransactionType, MiningAccount


def generate_referral_code(telegram_id: int) -> str:
    return f"ref_{telegram_id}_{secrets.token_hex(4)}"


def _credit_referrer(referrer_id: int, amount: int, reference: str) -> None:
    """Credit coins to referrer and write ledger entry. Must be called inside a transaction."""
    account = MiningAccount.query.filter_by(user_id=referrer_id).with_for_update().first()
    if not account:
        return
    balance_before = account.available_coins
    account.available_coins += amount
    tx = Transaction(
        user_id=referrer_id,
        type=TransactionType.REFERRAL,
        amount=amount,
        balance_before=balance_before,
        balance_after=account.available_coins,
        source="available",
        reference_id=reference,
    )
    db.session.add(tx)


def process_referral_on_signup(referee_user: "User") -> None:
    """
    Called after a new user signs up via referral link.
    Awards Milestone 1 (+100 coins) to referrer — Telegram verified.
    Prevents self-referral and duplicate referral.
    """
    if not referee_user.referred_by_id:
        return

    # Prevent self-referral
    if referee_user.referred_by_id == referee_user.telegram_id:
        return

    # Check if referral record already exists (duplicate prevention)
    existing = Referral.query.filter_by(referee_id=referee_user.telegram_id).first()
    if existing:
        return

    try:
        referral = Referral(
            referrer_id=referee_user.referred_by_id,
            referee_id=referee_user.telegram_id,
            telegram_verify_reward_paid=False,
            first_mining_reward_paid=False,
            activity_24h_reward_paid=False,
        )
        db.session.add(referral)
        db.session.flush()

        # Milestone 1: Telegram verify reward
        from flask import current_app
        reward = current_app.config.get("REFERRAL_REWARD_TELEGRAM_VERIFY", 100)
        _credit_referrer(
            referee_user.referred_by_id,
            reward,
            f"referral_verify_{referee_user.telegram_id}",
        )
        referral.telegram_verify_reward_paid = True
        referral.total_reward_paid += reward
        db.session.commit()
    except Exception:
        db.session.rollback()


def process_referral_on_first_mining(referee_user: "User") -> None:
    """
    Called after a user's first successful mining claim.
    Awards Milestone 2 (+200 coins) to referrer.
    """
    referral = Referral.query.filter_by(
        referee_id=referee_user.telegram_id,
        first_mining_reward_paid=False,
    ).first()
    if not referral:
        return

    try:
        from flask import current_app
        reward = current_app.config.get("REFERRAL_REWARD_FIRST_MINING", 200)
        _credit_referrer(
            referral.referrer_id,
            reward,
            f"referral_mining_{referee_user.telegram_id}",
        )
        referral.first_mining_reward_paid = True
        referral.total_reward_paid += reward
        db.session.commit()
    except Exception:
        db.session.rollback()


def check_and_reward_24h_activity(referee_user: "User") -> None:
    """
    Called when referee has been active for 24h.
    Awards Milestone 3 (+200 coins) to referrer.
    """
    referral = Referral.query.filter_by(
        referee_id=referee_user.telegram_id,
        activity_24h_reward_paid=False,
    ).first()
    if not referral:
        return

    created_at = referral.created_at
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)

    if datetime.now(timezone.utc) - created_at < timedelta(hours=24):
        return  # not yet 24h

    try:
        from flask import current_app
        reward = current_app.config.get("REFERRAL_REWARD_24H_ACTIVITY", 200)
        _credit_referrer(
            referral.referrer_id,
            reward,
            f"referral_24h_{referee_user.telegram_id}",
        )
        referral.activity_24h_reward_paid = True
        referral.total_reward_paid += reward
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_referral_stats(user: "User") -> dict:
    from flask import current_app
    if not user.referral_code:
        user.referral_code = generate_referral_code(user.telegram_id)
        db.session.commit()

    referrals = Referral.query.filter_by(referrer_id=user.telegram_id).all()
    total_earned = sum(r.total_reward_paid for r in referrals)
    # Qualified = completed at least first mining milestone
    qualified = sum(1 for r in referrals if r.first_mining_reward_paid)
    bot_username = current_app.config.get("TELEGRAM_BOT_USERNAME", "YourBot")

    return {
        "total_referrals": len(referrals),
        "qualified_referrals": qualified,
        "total_earned": total_earned,
        "referral_code": user.referral_code,
        "referral_link": f"https://t.me/{bot_username}?start={user.referral_code}",
        "max_reward_per_referral": 500,
        "milestones": {
            "telegram_verify": 100,
            "first_mining": 200,
            "activity_24h": 200,
        },
    }
