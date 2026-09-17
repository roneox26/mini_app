"""Tasks endpoints — list, create, and complete tasks."""
from flask import request, jsonify, g
from datetime import datetime, timezone
from app.api.v1 import api_v1
from app.security.auth import require_auth, require_admin
from app.database import db
from app.models import Task, UserTask, UserTaskStatus, MiningAccount, Transaction, TransactionType, TaskType, seed_default_tasks


@api_v1.route("/tasks", methods=["GET", "POST"])
@require_auth
def tasks_endpoint():
    if request.method == "GET":
        if Task.query.count() == 0:
            seed_default_tasks()
        tasks = Task.query.filter_by(is_active=True).all()
        result = []
        for task in tasks:
            user_task = UserTask.query.filter_by(
                user_id=g.user_id,
                task_id=task.id
            ).first()
            t = task.to_dict()
            t["user_status"] = user_task.status.value if user_task else "NOT_STARTED"
            result.append(t)
        return jsonify({"tasks": result})

    # POST — admin only
    if not g.user.is_admin:
        return jsonify({"error": "Admin access required"}), 403

    data = request.get_json() or {}
    required = ["name", "display_name", "task_type", "reward_coins"]
    if not all(k in data for k in required):
        return jsonify({"error": "Missing required fields"}), 400

    if Task.query.filter_by(name=data["name"]).first():
        return jsonify({"error": "Task name already exists"}), 400

    try:
        task_type = TaskType[data["task_type"]]
    except KeyError:
        return jsonify({"error": f"Invalid task_type. Must be one of: {', '.join([t.name for t in TaskType])}"}), 400

    task = Task(
        name=data["name"],
        display_name=data["display_name"],
        task_type=task_type,
        description=data.get("description"),
        reward_coins=int(data["reward_coins"]),
        target_url=data.get("target_url"),
        is_active=data.get("is_active", True),
        is_repeatable=data.get("is_repeatable", False),
    )
    db.session.add(task)
    db.session.commit()
    return jsonify({"status": "created", "task": task.to_dict()}), 201


@api_v1.route("/tasks/<int:task_id>/complete", methods=["POST"])
@require_auth
def complete_task(task_id):
    task = Task.query.get(task_id)
    if not task or not task.is_active:
        return jsonify({"error": "Task not found"}), 404

    existing = UserTask.query.filter_by(
        user_id=g.user_id,
        task_id=task_id,
    ).first()

    if existing and existing.status == UserTaskStatus.COMPLETED and not task.is_repeatable:
        return jsonify({"error": "Task already completed"}), 400

    try:
        account = MiningAccount.query.filter_by(user_id=g.user_id).first()
        if not account:
            return jsonify({"error": "Mining account not found"}), 404

        # Create or update user task record
        if not existing:
            user_task = UserTask(
                user_id=g.user_id,
                task_id=task_id,
                status=UserTaskStatus.COMPLETED,
                reward_coins=task.reward_coins,
                completed_at=datetime.now(timezone.utc),
            )
            db.session.add(user_task)
        else:
            existing.status = UserTaskStatus.COMPLETED
            existing.completed_at = datetime.now(timezone.utc)
            existing.reward_coins = task.reward_coins

        # Credit reward
        balance_before = account.available_coins
        account.available_coins += task.reward_coins

        tx = Transaction(
            user_id=g.user_id,
            type=TransactionType.TASK,
            amount=task.reward_coins,
            balance_before=balance_before,
            balance_after=account.available_coins,
            reference_id=f"task_{task_id}",
            note=task.display_name,
        )
        db.session.add(tx)
        db.session.commit()

        return jsonify({
            "status": "completed",
            "task_id": task_id,
            "task_name": task.display_name,
            "coins_earned": task.reward_coins,
            "new_balance": account.available_coins,
        }), 200

    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@api_v1.route("/tasks/<int:task_id>", methods=["PUT", "DELETE"])
@require_auth
def task_detail(task_id):
    if not g.user.is_admin:
        return jsonify({"error": "Admin access required"}), 403

    task = Task.query.get(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404

    if request.method == "DELETE":
        db.session.delete(task)
        db.session.commit()
        return jsonify({"status": "deleted", "task_id": task_id}), 200

    # PUT
    data = request.get_json() or {}
    for field in ["display_name", "description", "target_url", "is_active", "is_repeatable"]:
        if field in data:
            setattr(task, field, data[field])
    if "reward_coins" in data:
        task.reward_coins = int(data["reward_coins"])
    db.session.commit()
    return jsonify({"status": "updated", "task": task.to_dict()}), 200
