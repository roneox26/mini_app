"""
Payment Service — Telegram Stars boost & coin purchase verification.

Boost prices (initial launch):
  Bronze: 79 Stars / 7 days / 12,000 coins/hr
  Silver: 159 Stars / 7 days / 30,000 coins/hr
  Gold:   299 Stars / 7 days / 60,000 coins/hr

Upgrade credit logic:
  When upgrading from an active boost, credit the unused time value
  as a proportional Stars discount (applied as bonus coins, not Stars refund).
  Only one active boost at a time — no stacking.

NEVER activate a boost before successful_payment webhook is verified.
"""
from datetime import datetime, timezone, timedelta
from flask import current_app
from app.database import db
from app.models import (
    UserBoost, BoostPlan, CoinPurchase, MiningAccount,
    Transaction, TransactionType
)


def get_boost_plans() -> list:
    plans = BoostPlan.query.filter_by(is_active=True).order_by(BoostPlan.mining_rate).all()
    return [p.to_dict() for p in plans]


def activate_boost(
    user: "User",
    plan_name: str,
    telegram_payment_charge_id: str,
    stars_paid: int,
) -> tuple[dict, int]:
    """
    Activate a paid mining boost after successful Telegram Stars payment.
    Handles upgrade from existing active boost with credit logic.
    """
    plan = BoostPlan.query.filter_by(name=plan_name, is_active=True).first()
    if not plan:
        return {"error": "Boost plan not found"}, 404

    if plan.price_stars == 0:
        return {"error": "This is a free plan"}, 400

    if stars_paid != plan.price_stars:
        return {"error": f"Stars amount mismatch. Expected {plan.price_stars}, got {stars_paid}"}, 400

    # Idempotency — prevent duplicate payment processing
    existing_payment = UserBoost.query.filter_by(
        telegram_payment_charge_id=telegram_payment_charge_id
    ).first()
    if existing_payment:
        return {"error": "Payment already processed"}, 409

    now = datetime.now(timezone.utc)

    try:
        account = (
            MiningAccount.query
            .filter_by(user_id=user.telegram_id)
            .with_for_update()
            .first()
        )
        if not account:
            return {"error": "Mining account not found"}, 404

        # Handle existing active boost (upgrade/extend)
        credit_coins = 0
        upgraded_from_plan_id = None
        existing_boost = _get_active_boost(user.telegram_id, now)

        if existing_boost:
            # Prevent downgrade — only allow upgrade or same-tier extend
            if existing_boost.plan and existing_boost.plan.mining_rate > plan.mining_rate:
                return {"error": "Cannot downgrade to a lower boost tier"}, 400

            # Calculate unused time credit as bonus coins
            credit_coins = _calculate_upgrade_credit(existing_boost, now)
            upgraded_from_plan_id = existing_boost.plan_id

            # Deactivate old boost
            existing_boost.is_active = False
            existing_boost.status = "upgraded"

            # If currently mining, stop session so rate updates cleanly
            if account.is_mining:
                account.is_mining = False
                account.last_mining_started_at = None

        expires_at = now + timedelta(days=plan.duration_days)

        boost = UserBoost(
            user_id=user.telegram_id,
            plan_id=plan.id,
            started_at=now,
            expires_at=expires_at,
            is_active=True,
            status="active",
            telegram_payment_charge_id=telegram_payment_charge_id,
            stars_paid=stars_paid,
            upgraded_from_plan_id=upgraded_from_plan_id,
            credit_coins_applied=credit_coins,
        )
        db.session.add(boost)
        db.session.flush()

        # Update mining account rate
        account.mining_rate = plan.mining_rate
        account.active_boost_id = boost.id

        # Apply upgrade credit as bonus coins
        if credit_coins > 0:
            balance_before = account.available_coins
            account.available_coins += credit_coins
            account.bonus_coins += credit_coins
            tx = Transaction(
                user_id=user.telegram_id,
                type=TransactionType.BONUS,
                amount=credit_coins,
                balance_before=balance_before,
                balance_after=account.available_coins,
                source="available",
                reference_id=f"upgrade_credit_{boost.id}",
                note=f"Upgrade credit from previous boost",
            )
            db.session.add(tx)

        # Ledger entry for boost purchase (negative = cost)
        tx_purchase = Transaction(
            user_id=user.telegram_id,
            type=TransactionType.BOOST_PURCHASE,
            amount=0,  # Stars payment, not coins — record for audit
            balance_before=account.available_coins,
            balance_after=account.available_coins,
            source="stars",
            reference_id=telegram_payment_charge_id,
            note=f"{plan.display_name} boost — {stars_paid} Stars",
        )
        db.session.add(tx_purchase)
        db.session.commit()

        return {
            "status": "activated",
            "plan": plan.to_dict(),
            "expires_at": expires_at.isoformat(),
            "new_mining_rate": plan.mining_rate,
            "upgrade_credit_coins": credit_coins,
            "upgraded_from": upgraded_from_plan_id,
        }, 200

    except Exception as e:
        db.session.rollback()
        return {"error": f"Boost activation failed: {str(e)}"}, 500


def _get_active_boost(user_id: int, now: datetime) -> "UserBoost | None":
    """Return the user's currently active boost, if any."""
    return (
        UserBoost.query
        .filter_by(user_id=user_id, is_active=True)
        .filter(UserBoost.expires_at > now)
        .first()
    )


def _calculate_upgrade_credit(boost: "UserBoost", now: datetime) -> int:
    """
    Calculate bonus coins credit for unused boost time.
    Credit = (remaining_days / total_days) * session_earnings_per_day
    This is a goodwill credit, not a Stars refund.
    """
    if not boost.expires_at or not boost.plan:
        return 0

    expires_at = boost.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)

    remaining_seconds = (expires_at - now).total_seconds()
    if remaining_seconds <= 0:
        return 0

    total_seconds = boost.plan.duration_days * 86400
    if total_seconds <= 0:
        return 0

    # Credit = remaining fraction × one session's earnings at old rate
    fraction = remaining_seconds / total_seconds
    one_session_earnings = boost.plan.mining_rate * 8  # 8-hour session
    credit = int(fraction * one_session_earnings * 0.5)  # 50% of proportional session value
    return max(0, credit)


def process_coin_purchase(
    user: "User",
    stars_paid: int,
    telegram_payment_charge_id: str,
) -> tuple[dict, int]:
    """
    Credit purchased coins after a Telegram Stars coin purchase.
    IMPORTANT: purchased_coins are tracked separately and are NOT withdrawal-eligible.
    """
    packages = current_app.config.get("COIN_PACKAGES", [])
    package = next((p for p in packages if p["stars"] == stars_paid), None)

    if not package:
        return {"error": "Invalid purchase amount"}, 400

    # Idempotency check
    existing = CoinPurchase.query.filter_by(
        telegram_payment_charge_id=telegram_payment_charge_id
    ).first()
    if existing:
        return {"error": "Payment already processed"}, 409

    account = (
        MiningAccount.query
        .filter_by(user_id=user.telegram_id)
        .with_for_update()
        .first()
    )
    if not account:
        return {"error": "Mining account not found"}, 404

    try:
        coins = package["coins"]
        balance_before = account.available_coins

        # Track separately — purchased coins are NOT withdrawal-eligible
        account.purchased_coins += coins
        # Do NOT add to available_coins — purchased coins have separate spending rules
        # They are spendable within the app but not withdrawable

        purchase = CoinPurchase(
            user_id=user.telegram_id,
            stars_paid=stars_paid,
            coins_received=coins,
            telegram_payment_charge_id=telegram_payment_charge_id,
        )
        db.session.add(purchase)

        tx = Transaction(
            user_id=user.telegram_id,
            type=TransactionType.COIN_PURCHASE,
            amount=coins,
            balance_before=balance_before,
            balance_after=account.available_coins,
            source="purchased",
            reference_id=telegram_payment_charge_id,
            note=f"Coin purchase: {coins:,} coins for {stars_paid} Stars",
        )
        db.session.add(tx)
        db.session.commit()

        return {
            "status": "credited",
            "stars_paid": stars_paid,
            "coins_received": coins,
            "note": "Purchased coins are not withdrawal-eligible",
        }, 200

    except Exception as e:
        db.session.rollback()
        return {"error": f"Purchase failed: {str(e)}"}, 500
