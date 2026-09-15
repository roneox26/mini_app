"""
Withdrawal Service — handles coin withdrawal requests.

Rules:
  - Minimum: 500,000 coins (≈ ৳500 reference value)
  - Fee: 5% (min configurable floor)
  - Only available_coins (mined) are withdrawal-eligible
  - purchased_coins are NOT withdrawal-eligible
  - Coins are reserved immediately on request (prevents double-withdrawal)
  - Crypto withdrawal DISABLED by default (CRYPTO_WITHDRAWAL_ENABLED = false)
"""
from datetime import datetime, timezone
from flask import current_app
from app.database import db
from app.models import Withdrawal, WithdrawalStatus, MiningAccount, Transaction, TransactionType

AVAILABLE_METHODS = ["bkash", "nagad", "rocket"]   # crypto: disabled by default


def request_withdrawal(
    user: "User",
    amount_coins: int,
    method: str,
    destination: str,
) -> tuple[dict, int]:
    """
    Create a withdrawal request.
    Reserves coins immediately to prevent double-withdrawal.
    """
    if not current_app.config.get("WITHDRAWALS_ENABLED", True):
        return {"error": "Withdrawals are currently disabled"}, 503

    if method not in AVAILABLE_METHODS:
        return {"error": f"Method not available. Use: {', '.join(AVAILABLE_METHODS)}"}, 400

    if not destination or len(destination.strip()) < 5:
        return {"error": "Valid destination (phone/wallet) is required"}, 400

    min_withdraw = current_app.config.get("MIN_WITHDRAWAL_COINS", 500000)
    if amount_coins < min_withdraw:
        return {"error": f"Minimum withdrawal is {min_withdraw:,} coins"}, 400

    # Row-level lock to prevent race conditions
    account = (
        MiningAccount.query
        .filter_by(user_id=user.telegram_id)
        .with_for_update()
        .first()
    )
    if not account:
        return {"error": "Mining account not found"}, 404

    # Only mined coins are withdrawal-eligible
    # available_coins = mined coins (not purchased, not bonus)
    if account.available_coins < amount_coins:
        return {"error": f"Insufficient available balance. You have {account.available_coins:,} coins."}, 400

    # Check for pending withdrawal (prevent duplicate requests)
    pending = Withdrawal.query.filter_by(
        user_id=user.telegram_id,
        status=WithdrawalStatus.PENDING,
    ).first()
    if pending:
        return {"error": "You already have a pending withdrawal request"}, 400

    fee_pct = current_app.config.get("WITHDRAWAL_FEE_PERCENT", 5)
    min_fee = current_app.config.get("MIN_WITHDRAWAL_FEE_COINS", 1000)
    fee_coins = max(int(amount_coins * fee_pct / 100), min_fee)
    net_coins = amount_coins - fee_coins

    # Reference value display (not guaranteed)
    ref_value_bdt = current_app.config.get("COIN_REFERENCE_VALUE_BDT", 0.001)
    net_ref_bdt = round(net_coins * ref_value_bdt, 2)

    try:
        balance_before = account.available_coins

        # Reserve coins immediately — deduct from available, track in reserved
        account.available_coins -= amount_coins
        account.reserved_coins = getattr(account, 'reserved_coins', 0) + amount_coins
        account.spent_coins += amount_coins

        withdrawal = Withdrawal(
            user_id=user.telegram_id,
            requested_coins=amount_coins,
            fee_coins=fee_coins,
            net_coins=net_coins,
            method=method,
            destination=destination.strip(),
            status=WithdrawalStatus.PENDING,
        )
        db.session.add(withdrawal)
        db.session.flush()

        # Ledger debit
        tx = Transaction(
            user_id=user.telegram_id,
            type=TransactionType.WITHDRAWAL,
            amount=-amount_coins,
            balance_before=balance_before,
            balance_after=account.available_coins,
            source="available",
            reference_id=f"withdrawal_{withdrawal.id}",
            note=f"Withdrawal via {method} — {amount_coins:,} coins",
        )
        db.session.add(tx)

        # Fee ledger entry
        tx_fee = Transaction(
            user_id=user.telegram_id,
            type=TransactionType.WITHDRAWAL_FEE,
            amount=-fee_coins,
            balance_before=account.available_coins,
            balance_after=account.available_coins,
            source="fee",
            reference_id=f"withdrawal_fee_{withdrawal.id}",
            note=f"Withdrawal fee {fee_pct}%",
        )
        db.session.add(tx_fee)
        db.session.commit()

        return {
            "status": "requested",
            "withdrawal_id": withdrawal.id,
            "requested_coins": amount_coins,
            "fee_coins": fee_coins,
            "fee_percent": fee_pct,
            "net_coins": net_coins,
            "method": method,
            "withdrawal_status": WithdrawalStatus.PENDING.value,
            "estimated_net_bdt": net_ref_bdt,
            "note": "Estimated value only. Not a guaranteed amount.",
        }, 200

    except Exception as e:
        db.session.rollback()
        return {"error": f"Withdrawal request failed: {str(e)}"}, 500


def get_withdrawal_history(user: "User") -> list:
    withdrawals = (
        Withdrawal.query
        .filter_by(user_id=user.telegram_id)
        .order_by(Withdrawal.created_at.desc())
        .limit(20)
        .all()
    )
    return [w.to_dict() for w in withdrawals]


def get_available_methods() -> list:
    if current_app.config.get("CRYPTO_WITHDRAWAL_ENABLED", False):
        return AVAILABLE_METHODS + ["crypto_ton"]
    return AVAILABLE_METHODS
