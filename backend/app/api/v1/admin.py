"""
Admin API Routes
All endpoints require X-Admin-Key header matching ADMIN_SECRET_KEY config.
"""
from functools import wraps
from flask import Blueprint, request, jsonify, current_app, g
from datetime import datetime, timezone, timedelta
from sqlalchemy import func, desc

from app.database import db
from app.models import (
    User, MiningAccount, Transaction, Withdrawal, WithdrawalStatus,
    Task, UserTask, Referral, AuditLog, AppSetting, CoinPurchase, UserBoost, BoostPlan
)
from app.services.economy import normal_mining_rate

admin_bp = Blueprint("admin", __name__, url_prefix="/api/v1/admin")


# ── Auth decorator ────────────────────────────────────────────────────────────
def require_admin(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        key = request.headers.get("X-Admin-Key", "")
        admin_tg_id = request.headers.get("X-Admin-Telegram-Id", "")
        if key != current_app.config.get("ADMIN_SECRET_KEY"):
            return jsonify({"error": "Unauthorized"}), 401
        try:
            g.admin_id = int(admin_tg_id)
        except (ValueError, TypeError):
            g.admin_id = 0
        return f(*args, **kwargs)
    return decorated


def log_action(action: str, target_user_id=None, detail=None):
    """Write an audit log entry."""
    try:
        log = AuditLog(
            admin_id=g.admin_id,
            action=action,
            target_user_id=target_user_id,
            detail=detail,
        )
        db.session.add(log)
        db.session.commit()
    except Exception:
        db.session.rollback()


# ── Dashboard Stats ───────────────────────────────────────────────────────────
@admin_bp.route("/stats", methods=["GET"])
@require_admin
def get_stats():
    total_users = User.query.count()
    active_miners = MiningAccount.query.filter_by(is_mining=True).count()
    total_coins = db.session.query(
        func.coalesce(func.sum(MiningAccount.mined_coins_total), 0)
    ).scalar()
    pending_withdrawals = Withdrawal.query.filter_by(status=WithdrawalStatus.PENDING).count()
    total_stars = db.session.query(
        func.coalesce(func.sum(UserBoost.stars_paid), 0)
    ).filter(UserBoost.stars_paid.isnot(None)).scalar()
    total_referrals = Referral.query.count()

    # Top 10 miners for dashboard
    top_accounts = (
        MiningAccount.query
        .join(User, MiningAccount.user_id == User.telegram_id)
        .filter(User.is_banned == False)
        .order_by(desc(MiningAccount.mined_coins_total))
        .limit(10)
        .all()
    )
    top_miners = []
    for acc in top_accounts:
        u = acc.user
        top_miners.append({
            "first_name": u.first_name,
            "username": u.username,
            "mined_coins_total": acc.mined_coins_total,
            "mining_rate": acc.mining_rate,
            "is_mining": acc.is_mining,
        })

    return jsonify({
        "total_users": total_users,
        "active_miners": active_miners,
        "total_coins_distributed": int(total_coins),
        "pending_withdrawals": pending_withdrawals,
        "total_stars_collected": int(total_stars),
        "total_referrals": total_referrals,
        "top_miners": top_miners,
    })


# ── Users ─────────────────────────────────────────────────────────────────────
@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))
    search = request.args.get("q", "")

    query = db.session.query(User, MiningAccount).outerjoin(
        MiningAccount, User.telegram_id == MiningAccount.user_id
    )
    if search:
        query = query.filter(
            (User.username.ilike(f"%{search}%")) |
            (User.first_name.ilike(f"%{search}%")) |
            (User.telegram_id == int(search) if search.isdigit() else False)
        )

    rows = query.order_by(desc(User.created_at)).limit(limit).offset(offset).all()

    users = []
    for u, acc in rows:
        d = u.to_dict()
        d["is_banned"] = u.is_banned
        d["is_admin"] = u.is_admin
        d["available_coins"] = acc.available_coins if acc else 0
        d["mined_coins_total"] = acc.mined_coins_total if acc else 0
        d["mining_rate"] = acc.mining_rate if acc else normal_mining_rate()
        d["is_mining"] = acc.is_mining if acc else False
        users.append(d)

    return jsonify({"users": users, "total": len(users)})


@admin_bp.route("/users/<int:user_id>/ban", methods=["POST"])
@require_admin
def ban_user(user_id):
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.is_banned = True
    db.session.commit()
    log_action("ban_user", target_user_id=user_id)
    return jsonify({"status": "banned", "user_id": user_id})


@admin_bp.route("/users/<int:user_id>/unban", methods=["POST"])
@require_admin
def unban_user(user_id):
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    user.is_banned = False
    db.session.commit()
    log_action("unban_user", target_user_id=user_id)
    return jsonify({"status": "unbanned", "user_id": user_id})

@admin_bp.route("/users/<int:user_id>/boost", methods=["POST"])
@require_admin
def activate_user_boost(user_id):
    """Grant one active boost to a user as an admin action."""
    user = User.query.filter_by(telegram_id=user_id).first()
    if not user:
        return jsonify({"error": "User not found"}), 404

    data = request.get_json(silent=True) or {}
    plan_name = str(data.get("plan_name", "")).strip().lower()
    plan = BoostPlan.query.filter_by(name=plan_name, is_active=True).first()
    if not plan:
        return jsonify({"error": "Active boost plan not found"}), 404

    account = MiningAccount.query.filter_by(user_id=user_id).with_for_update().first()
    if not account:
        account = MiningAccount(user_id=user_id, mining_rate=plan.mining_rate, is_mining=False)
        db.session.add(account)
        db.session.flush()

    now = datetime.now(timezone.utc)
    active_boosts = UserBoost.query.filter_by(user_id=user_id, is_active=True).all()
    for existing in active_boosts:
        existing.is_active = False
        existing.status = "admin_replaced"

    if account.is_mining:
        account.is_mining = False
        account.last_mining_started_at = None

    boost = UserBoost(
        user_id=user_id,
        plan_id=plan.id,
        purchase_id=f"admin_{g.admin_id}_{now.timestamp()}",
        started_at=now,
        expires_at=now + timedelta(days=plan.duration_days) if plan.duration_days else None,
        is_active=True,
        status="active",
        stars_paid=0,
    )
    db.session.add(boost)
    db.session.flush()
    account.mining_rate = plan.mining_rate
    account.active_boost_id = boost.id
    db.session.add(Transaction(
        user_id=user_id,
        type="BOOST_PURCHASE",
        amount=0,
        balance_before=account.available_coins,
        balance_after=account.available_coins,
        source="admin",
        reference_id=f"admin_boost_{boost.id}",
        note=f"Admin activated {plan.display_name} plan",
    ))
    db.session.commit()
    log_action("activate_user_boost", target_user_id=user_id, detail=f"plan={plan.name}")
    return jsonify({"status": "activated", "user_id": user_id, "plan": plan.to_dict(), "expires_at": boost.expires_at.isoformat() if boost.expires_at else None})


@admin_bp.route("/users/<int:user_id>/adjust", methods=["POST"])
@require_admin
def adjust_balance(user_id):
    """Manually adjust a user's coin balance."""
    data = request.get_json(silent=True) or {}
    amount = data.get("amount")  # can be negative
    note = data.get("note", "Admin adjustment")

    if amount is None:
        return jsonify({"error": "amount is required"}), 400

    account = MiningAccount.query.filter_by(user_id=user_id).first()
    if not account:
        return jsonify({"error": "Mining account not found"}), 404

    try:
        balance_before = account.available_coins
        account.available_coins = max(0, account.available_coins + int(amount))

        tx = Transaction(
            user_id=user_id,
            type="ADMIN_ADJUSTMENT",
            amount=int(amount),
            balance_before=balance_before,
            balance_after=account.available_coins,
            note=note,
        )
        db.session.add(tx)
        db.session.commit()
        log_action("adjust_balance", target_user_id=user_id, detail=f"amount={amount}, note={note}")
        return jsonify({"status": "adjusted", "new_balance": account.available_coins})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ── Withdrawals ───────────────────────────────────────────────────────────────
@admin_bp.route("/withdrawals", methods=["GET"])
@require_admin
def list_withdrawals():
    status_filter = request.args.get("status")
    limit = min(int(request.args.get("limit", 100)), 500)

    query = db.session.query(Withdrawal, User).join(User, Withdrawal.user_id == User.telegram_id)
    if status_filter:
        try:
            query = query.filter(Withdrawal.status == WithdrawalStatus(status_filter))
        except ValueError:
            pass

    rows = query.order_by(desc(Withdrawal.created_at)).limit(limit).all()

    withdrawals = []
    for w, u in rows:
        d = w.to_dict()
        d["user_name"] = f"{u.first_name} {u.last_name or ''}".strip()
        d["user_id"] = w.user_id
        withdrawals.append(d)

    return jsonify({"withdrawals": withdrawals})


@admin_bp.route("/withdrawals/<int:withdrawal_id>", methods=["PATCH"])
@require_admin
def update_withdrawal(withdrawal_id):
    data = request.get_json(silent=True) or {}
    new_status = data.get("status")
    admin_note = data.get("admin_note")

    if not new_status:
        return jsonify({"error": "status is required"}), 400

    try:
        status_enum = WithdrawalStatus(new_status)
    except ValueError:
        return jsonify({"error": f"Invalid status: {new_status}"}), 400

    w = Withdrawal.query.get(withdrawal_id)
    if not w:
        return jsonify({"error": "Withdrawal not found"}), 404

    w.status = status_enum
    if admin_note:
        w.admin_note = admin_note
    if new_status in ("PAID", "APPROVED", "REJECTED"):
        w.processed_at = datetime.now(timezone.utc)

    # Refund coins if rejected
    if new_status == "REJECTED":
        account = MiningAccount.query.filter_by(user_id=w.user_id).first()
        if account:
            balance_before = account.available_coins
            account.available_coins += w.requested_coins
            tx = Transaction(
                user_id=w.user_id,
                type="REFUND",
                amount=w.requested_coins,
                balance_before=balance_before,
                balance_after=account.available_coins,
                reference_id=f"refund_withdrawal_{withdrawal_id}",
                note="Withdrawal rejected — coins refunded",
            )
            db.session.add(tx)

    db.session.commit()
    log_action(f"withdrawal_{new_status.lower()}", target_user_id=w.user_id, detail=f"id={withdrawal_id}")
    return jsonify({"status": "updated", "new_status": new_status})


# ── Transactions ──────────────────────────────────────────────────────────────
@admin_bp.route("/transactions", methods=["GET"])
@require_admin
def list_transactions():
    limit = min(int(request.args.get("limit", 100)), 500)
    user_id = request.args.get("user_id")

    query = Transaction.query
    if user_id:
        query = query.filter_by(user_id=int(user_id))

    txs = query.order_by(desc(Transaction.created_at)).limit(limit).all()
    return jsonify({"transactions": [t.to_dict() for t in txs]})


# ── Tasks ─────────────────────────────────────────────────────────────────────
@admin_bp.route("/tasks", methods=["GET"])
@require_admin
def list_tasks():
    tasks = Task.query.order_by(Task.id).all()
    return jsonify({"tasks": [t.to_dict() for t in tasks]})


@admin_bp.route("/tasks", methods=["POST"])
@require_admin
def create_task():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    display_name = data.get("display_name", "").strip()
    task_type = data.get("task_type", "")
    reward_coins = data.get("reward_coins", 0)
    description = data.get("description", "")
    target_url = data.get("target_url", "")
    is_repeatable = bool(data.get("is_repeatable", False))

    if not name or not display_name or not task_type or not reward_coins:
        return jsonify({"error": "name, display_name, task_type, reward_coins are required"}), 400

    from app.models import TaskType
    try:
        task_type_enum = TaskType(task_type)
    except ValueError:
        return jsonify({"error": f"Invalid task_type: {task_type}"}), 400

    if Task.query.filter_by(name=name).first():
        return jsonify({"error": "Task name already exists"}), 400

    task = Task(
        name=name,
        display_name=display_name,
        task_type=task_type_enum,
        reward_coins=int(reward_coins),
        description=description,
        target_url=target_url or None,
        is_repeatable=is_repeatable,
        is_active=True,
    )
    db.session.add(task)
    db.session.commit()
    log_action("create_task", detail=f"name={name}, reward={reward_coins}")
    return jsonify({"status": "created", "task": task.to_dict()}), 201


@admin_bp.route("/tasks/<int:task_id>", methods=["PATCH"])
@require_admin
def update_task(task_id):
    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        task.is_active = bool(data["is_active"])
    if "reward_coins" in data:
        task.reward_coins = int(data["reward_coins"])
    if "display_name" in data:
        task.display_name = data["display_name"]
    if "target_url" in data:
        task.target_url = data["target_url"]

    db.session.commit()
    log_action("update_task", detail=f"task_id={task_id}, changes={data}")
    return jsonify({"status": "updated", "task": task.to_dict()})


# ── Boost Plans ──────────────────────────────────────────────────────────────
@admin_bp.route("/boosts", methods=["GET"])
@require_admin
def list_boost_plans():
    plans = BoostPlan.query.order_by(BoostPlan.mining_rate).all()
    return jsonify({"plans": [plan.to_dict() | {"is_active": plan.is_active} for plan in plans]})


@admin_bp.route("/boosts/<int:plan_id>", methods=["PATCH"])
@require_admin
def update_boost_plan(plan_id):
    plan = BoostPlan.query.get(plan_id)
    if not plan:
        return jsonify({"error": "Boost plan not found"}), 404

    data = request.get_json(silent=True) or {}
    if "is_active" in data:
        plan.is_active = bool(data["is_active"])
    if "mining_rate" in data:
        plan.mining_rate = max(0, int(data["mining_rate"]))
    if "price_stars" in data:
        plan.price_stars = max(0, int(data["price_stars"]))
    if "duration_days" in data:
        plan.duration_days = max(0, int(data["duration_days"]))

    db.session.commit()
    log_action("update_boost_plan", detail=f"plan_id={plan_id}, changes={data}")
    return jsonify({"status": "updated", "plan": plan.to_dict() | {"is_active": plan.is_active}})


# ── Settings ──────────────────────────────────────────────────────────────────
@admin_bp.route("/settings", methods=["GET"])
@require_admin
def get_settings():
    settings = AppSetting.query.all()
    return jsonify({"settings": {s.key: s.value for s in settings}})


@admin_bp.route("/settings", methods=["POST"])
@require_admin
def update_settings():
    data = request.get_json(silent=True) or {}
    settings_dict = data.get("settings", {})

    for key, value in settings_dict.items():
        existing = AppSetting.query.get(key)
        if existing:
            existing.value = str(value)
        else:
            db.session.add(AppSetting(key=key, value=str(value)))

    db.session.commit()
    log_action("update_settings", detail=str(list(settings_dict.keys())))
    return jsonify({"status": "saved", "count": len(settings_dict)})


# ── Broadcast ─────────────────────────────────────────────────────────────────
@admin_bp.route("/broadcast", methods=["POST"])
@require_admin
def broadcast():
    """Send a message to all users via Telegram Bot API."""
    import requests as req
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()

    if not message:
        return jsonify({"error": "Message is required"}), 400

    bot_token = current_app.config.get("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        return jsonify({"error": "Bot token not configured"}), 500

    users = User.query.filter_by(is_banned=False).all()
    sent = 0
    failed = 0

    for user in users:
        try:
            res = req.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": user.telegram_id, "text": message, "parse_mode": "HTML"},
                timeout=5,
            )
            if res.ok:
                sent += 1
            else:
                failed += 1
        except Exception:
            failed += 1

    log_action("broadcast", detail=f"sent={sent}, failed={failed}, msg={message[:100]}")
    return jsonify({"status": "done", "sent": sent, "failed": failed})
