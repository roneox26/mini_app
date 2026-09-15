"""Initial schema — all tables

Revision ID: 001
Revises: 
Create Date: 2026-09-14

Creates all tables:
  - users
  - mining_accounts
  - mining_sessions
  - transactions
  - boost_plans
  - user_boosts
  - referrals
  - tasks
  - user_tasks
  - user_daily_rewards
  - ad_rewards
  - coin_purchases
  - withdrawals
  - app_settings
  - audit_logs
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── users ────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=64), nullable=True),
        sa.Column("first_name", sa.String(length=128), nullable=False),
        sa.Column("last_name", sa.String(length=128), nullable=True),
        sa.Column("photo_url", sa.String(length=512), nullable=True),
        sa.Column("language_code", sa.String(length=8), nullable=True),
        sa.Column("is_premium", sa.Boolean(), nullable=True),
        sa.Column("is_banned", sa.Boolean(), nullable=True),
        sa.Column("is_admin", sa.Boolean(), nullable=True),
        sa.Column("referral_code", sa.String(length=32), nullable=True),
        sa.Column("referred_by_id", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referred_by_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referral_code"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_referral_code", "users", ["referral_code"])
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    # ── boost_plans ──────────────────────────────────────────────────────────
    op.create_table(
        "boost_plans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=32), nullable=False),
        sa.Column("display_name", sa.String(length=64), nullable=False),
        sa.Column("emoji", sa.String(length=8), nullable=False),
        sa.Column("mining_rate", sa.Integer(), nullable=False),
        sa.Column("price_stars", sa.Integer(), nullable=False),
        sa.Column("duration_days", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── user_boosts ──────────────────────────────────────────────────────────
    op.create_table(
        "user_boosts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("plan_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("telegram_payment_charge_id", sa.String(length=256), nullable=True),
        sa.Column("stars_paid", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["plan_id"], ["boost_plans.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_payment_charge_id"),
    )
    op.create_index("ix_user_boosts_user_id", "user_boosts", ["user_id"])

    # ── mining_accounts ──────────────────────────────────────────────────────
    op.create_table(
        "mining_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("available_coins", sa.BigInteger(), nullable=False),
        sa.Column("pending_coins", sa.BigInteger(), nullable=False),
        sa.Column("mined_coins_total", sa.BigInteger(), nullable=False),
        sa.Column("purchased_coins", sa.BigInteger(), nullable=False),
        sa.Column("spent_coins", sa.BigInteger(), nullable=False),
        sa.Column("mining_rate", sa.Integer(), nullable=False),
        sa.Column("last_mining_started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_mining", sa.Boolean(), nullable=True),
        sa.Column("active_boost_id", sa.BigInteger(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["active_boost_id"], ["user_boosts.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_mining_accounts_user_id", "mining_accounts", ["user_id"])

    # ── mining_sessions ──────────────────────────────────────────────────────
    op.create_table(
        "mining_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("mining_account_id", sa.BigInteger(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("coins_earned", sa.BigInteger(), nullable=True),
        sa.Column("mining_rate_snapshot", sa.Integer(), nullable=False),
        sa.Column("is_claimed", sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(["mining_account_id"], ["mining_accounts.id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_mining_sessions_mining_account_id", "mining_sessions", ["mining_account_id"])

    # ── transactions ─────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE transactiontype AS ENUM ('MINING', 'AD_REWARD', 'REFERRAL', 'DAILY_REWARD', 'BOOST', 'PURCHASE', 'WITHDRAW', 'REFUND', 'ADMIN_ADJUSTMENT', 'TASK');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.create_table(
        "transactions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("type", postgresql.ENUM(
            "MINING", "AD_REWARD", "REFERRAL", "DAILY_REWARD",
            "BOOST", "PURCHASE", "WITHDRAW", "REFUND", "ADMIN_ADJUSTMENT", "TASK",
            name="transactiontype", create_type=False
        ), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_before", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("reference", sa.String(length=256), nullable=True),
        sa.Column("note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_transactions_user_id", "transactions", ["user_id"])
    op.create_index("ix_transactions_created_at", "transactions", ["created_at"])

    # ── referrals ────────────────────────────────────────────────────────────
    op.create_table(
        "referrals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("referrer_id", sa.BigInteger(), nullable=False),
        sa.Column("referee_id", sa.BigInteger(), nullable=False),
        sa.Column("first_mining_reward_paid", sa.Boolean(), nullable=True),
        sa.Column("activity_24h_reward_paid", sa.Boolean(), nullable=True),
        sa.Column("total_reward_paid", sa.BigInteger(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["referee_id"], ["users.telegram_id"], ),
        sa.ForeignKeyConstraint(["referrer_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("referee_id"),
    )
    op.create_index("ix_referrals_referrer_id", "referrals", ["referrer_id"])
    op.create_index("ix_referrals_referee_id", "referrals", ["referee_id"])

    # ── tasks ────────────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE tasktype AS ENUM ('JOIN_CHANNEL', 'JOIN_GROUP', 'FOLLOW', 'VISIT_WEBSITE', 'PLAY_GAME', 'DAILY_LOGIN', 'INVITE_FRIEND');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.create_table(
        "tasks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("display_name", sa.String(length=128), nullable=False),
        sa.Column("task_type", postgresql.ENUM(
            "JOIN_CHANNEL", "JOIN_GROUP", "FOLLOW",
            "VISIT_WEBSITE", "PLAY_GAME", "DAILY_LOGIN", "INVITE_FRIEND",
            name="tasktype", create_type=False
        ), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("reward_coins", sa.BigInteger(), nullable=False),
        sa.Column("target_url", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=True),
        sa.Column("is_repeatable", sa.Boolean(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )

    # ── user_tasks ───────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE usertaskstatus AS ENUM ('PENDING', 'VERIFYING', 'COMPLETED', 'REJECTED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.create_table(
        "user_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("status", postgresql.ENUM(
            "PENDING", "VERIFYING", "COMPLETED", "REJECTED",
            name="usertaskstatus", create_type=False
        ), nullable=False),
        sa.Column("reward_coins", sa.BigInteger(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_tasks_user_id", "user_tasks", ["user_id"])
    op.create_index("ix_user_tasks_task_id", "user_tasks", ["task_id"])

    # ── user_daily_rewards ───────────────────────────────────────────────────
    op.create_table(
        "user_daily_rewards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("current_streak", sa.Integer(), nullable=True),
        sa.Column("last_claimed_date", sa.Date(), nullable=True),
        sa.Column("total_days_claimed", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_daily_rewards_user_id", "user_daily_rewards", ["user_id"])

    # ── ad_rewards ───────────────────────────────────────────────────────────
    op.create_table(
        "ad_rewards",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("ad_event_id", sa.String(length=256), nullable=True),
        sa.Column("coins_awarded", sa.Integer(), nullable=False),
        sa.Column("ad_type", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ad_event_id"),
    )
    op.create_index("ix_ad_rewards_user_id", "ad_rewards", ["user_id"])
    op.create_index("ix_ad_rewards_created_at", "ad_rewards", ["created_at"])

    # ── coin_purchases ───────────────────────────────────────────────────────
    op.create_table(
        "coin_purchases",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("stars_paid", sa.Integer(), nullable=False),
        sa.Column("coins_received", sa.BigInteger(), nullable=False),
        sa.Column("telegram_payment_charge_id", sa.String(length=256), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_payment_charge_id"),
    )
    op.create_index("ix_coin_purchases_user_id", "coin_purchases", ["user_id"])

    # ── withdrawals ──────────────────────────────────────────────────────────
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE withdrawalstatus AS ENUM ('PENDING', 'REVIEW', 'APPROVED', 'REJECTED', 'PAID', 'CANCELLED');
        EXCEPTION WHEN duplicate_object THEN null;
        END $$
    """)

    op.create_table(
        "withdrawals",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("requested_coins", sa.BigInteger(), nullable=False),
        sa.Column("fee_coins", sa.BigInteger(), nullable=False),
        sa.Column("net_coins", sa.BigInteger(), nullable=False),
        sa.Column("method", sa.String(length=64), nullable=False),
        sa.Column("destination", sa.String(length=256), nullable=True),
        sa.Column("status", postgresql.ENUM(
            "PENDING", "REVIEW", "APPROVED", "REJECTED", "PAID", "CANCELLED",
            name="withdrawalstatus", create_type=False
        ), nullable=False),
        sa.Column("admin_note", sa.String(length=512), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.telegram_id"], ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_withdrawals_user_id", "withdrawals", ["user_id"])
    op.create_index("ix_withdrawals_status", "withdrawals", ["status"])
    op.create_index("ix_withdrawals_created_at", "withdrawals", ["created_at"])

    # ── app_settings ─────────────────────────────────────────────────────────
    op.create_table(
        "app_settings",
        sa.Column("key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("description", sa.String(length=512), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("key"),
    )

    # ── audit_logs ───────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("admin_id", sa.BigInteger(), nullable=False),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("target_user_id", sa.BigInteger(), nullable=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("app_settings")
    op.drop_table("withdrawals")
    op.drop_table("coin_purchases")
    op.drop_table("ad_rewards")
    op.drop_table("user_daily_rewards")
    op.drop_table("user_tasks")
    op.drop_table("tasks")
    op.drop_table("referrals")
    op.drop_table("transactions")
    op.drop_table("mining_sessions")
    op.drop_table("mining_accounts")
    op.drop_table("user_boosts")
    op.drop_table("boost_plans")
    op.drop_table("users")

    # Drop enums
    from sqlalchemy.dialects import postgresql
    for enum_name in ["transactiontype", "withdrawalstatus", "tasktype", "usertaskstatus"]:
        postgresql.ENUM(name=enum_name).drop(op.get_bind(), checkfirst=True)
