"""
Mining Service — Server-side auto mining logic.

Rule: Frontend NEVER calculates balance.
All calculations use server UTC timestamps.

Formula: earned = elapsed_seconds * effective_rate_per_hour / 3600
Max session: 8 hours = 28,800 seconds

Rates (coins/hour):
  Normal: 1,000  → 8,000 per session
  Bronze: 5,000  → 40,000 per session
  Silver: 10,000 → 80,000 per session
  Gold:   20,000 → 160,000 per session
"""
from datetime import datetime, timezone
from app.database import db
from app.models import (
    MiningAccount, MiningSession, Transaction, TransactionType, User
)
from app.services.referral import process_referral_on_first_mining
from app.services.economy import mining_session_seconds, normal_mining_rate


def get_or_create_mining_account(user: "User") -> MiningAccount:
    account = user.mining_account
    if not account:
        account = MiningAccount(
            user_id=user.telegram_id,
            available_coins=0,
            pending_coins=0,
            mining_rate=normal_mining_rate(),
            is_mining=False,
        )
        db.session.add(account)
        db.session.flush()
    return account


def _calc_earned(elapsed_seconds: float, rate: int) -> int:
    """Calculate coins earned, capped at the configured session duration."""
    effective = min(elapsed_seconds, mining_session_seconds())
    return int(effective * rate / 3600)


def start_mining(user: "User") -> tuple[dict, int]:
    """Start a new mining session."""
    account = get_or_create_mining_account(user)

    if account.is_mining:
        return {"error": "Mining session already active"}, 400

    now = datetime.now(timezone.utc)
    account.is_mining = True
    account.last_mining_started_at = now

    session = MiningSession(
        mining_account_id=account.id,
        started_at=now,
        mining_rate_snapshot=account.get_effective_rate(),
        is_claimed=False,
    )
    db.session.add(session)
    db.session.commit()

    session_hours = mining_session_seconds() // 3600
    return {
        "status": "started",
        "started_at": now.isoformat(),
        "mining_rate": account.mining_rate,
        "effective_rate": account.get_effective_rate(),
        "session_hours": session_hours,
        "max_session_earnings": account.get_effective_rate() * session_hours,
    }, 200


def get_mining_status(user: "User") -> tuple[dict, int]:
    """
    Calculate current mining status from server timestamps.
    Frontend receives calculated values — never computes locally.
    """
    account = get_or_create_mining_account(user)
    now = datetime.now(timezone.utc)

    result = {
        "is_mining": account.is_mining,
        "mining_rate": account.mining_rate,
        "effective_rate": account.get_effective_rate(),
        "balance": account.to_dict(),
        "earned_this_session": 0,
        "session_elapsed_seconds": 0,
        "session_remaining_seconds": mining_session_seconds(),
        "can_claim": False,
        "session_full": False,
    }

    if account.is_mining and account.last_mining_started_at:
        started_at = account.last_mining_started_at
        if started_at.tzinfo is None:
            started_at = started_at.replace(tzinfo=timezone.utc)

        elapsed = (now - started_at).total_seconds()
        session = (
            MiningSession.query
            .filter_by(mining_account_id=account.id, is_claimed=False)
            .order_by(MiningSession.started_at.desc())
            .first()
        )
        rate = session.mining_rate_snapshot if session else account.get_effective_rate()
        session_seconds = mining_session_seconds()
        effective_elapsed = min(elapsed, session_seconds)
        earned = _calc_earned(elapsed, rate)
        remaining = max(0, session_seconds - elapsed)
        session_full = elapsed >= session_seconds

        result.update({
            "earned_this_session": earned,
            "session_elapsed_seconds": int(effective_elapsed),
            "session_remaining_seconds": int(remaining),
            "effective_rate": rate,
            "can_claim": earned > 0,
            "session_full": session_full,
            "started_at": started_at.isoformat(),
        })

    return result, 200


def claim_mining(user: "User") -> tuple[dict, int]:
    """
    Claim accumulated mining coins.
    Uses DB row-level lock to prevent double-claims.
    Mining → pending_coins → available_coins (direct for mining, no hold needed).
    """
    # Lock the row to prevent concurrent claims
    account = (
        MiningAccount.query
        .filter_by(user_id=user.telegram_id)
        .with_for_update()
        .first()
    )

    if not account or not account.is_mining:
        return {"error": "No active mining session"}, 400

    now = datetime.now(timezone.utc)
    started_at = account.last_mining_started_at
    if started_at.tzinfo is None:
        started_at = started_at.replace(tzinfo=timezone.utc)

    elapsed = (now - started_at).total_seconds()
    active_session = (
        MiningSession.query
        .filter_by(mining_account_id=account.id, is_claimed=False)
        .order_by(MiningSession.started_at.desc())
        .first()
    )
    rate = active_session.mining_rate_snapshot if active_session else account.get_effective_rate()
    earned = _calc_earned(elapsed, rate)

    if earned <= 0:
        return {"error": "No coins to claim yet"}, 400

    try:
        balance_before = account.available_coins

        # Mining coins go directly to available (mined coins are withdrawal-eligible)
        account.available_coins += earned
        account.mined_coins_total += earned
        account.is_mining = False
        account.last_claimed_at = now

        # Mark active session as claimed
        if active_session:
            active_session.is_claimed = True
            active_session.claimed_at = now
            active_session.coins_earned = earned

        tx = Transaction(
            user_id=user.telegram_id,
            type=TransactionType.MINING,
            amount=earned,
            balance_before=balance_before,
            balance_after=account.available_coins,
            source="available",
            reference_id=f"session_{active_session.id if active_session else 'unknown'}",
        )
        db.session.add(tx)
        db.session.commit()

        # Process referral milestones (non-blocking)
        try:
            process_referral_on_first_mining(user)
        except Exception:
            pass

        return {
            "status": "claimed",
            "coins_earned": earned,
            "new_balance": account.available_coins,
            "claimed_at": now.isoformat(),
        }, 200

    except Exception as e:
        db.session.rollback()
        return {"error": f"Claim failed: {str(e)}"}, 500
