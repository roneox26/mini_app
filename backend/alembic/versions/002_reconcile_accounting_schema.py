"""Reconcile ORM accounting fields with the initial database schema."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # New ledger values are used by the current services.
    for value in (
        "AD_REWARD",
        "REFERRAL",
        "DAILY_REWARD",
        "BOOST_PURCHASE",
        "COIN_PURCHASE",
        "WITHDRAWAL",
        "WITHDRAWAL_FEE",
        "BONUS",
        "REVERSAL",
        "PENDING_RELEASE",
    ):
        op.execute(
            f"ALTER TYPE transactiontype ADD VALUE IF NOT EXISTS '{value}'"
        )

    op.add_column("mining_accounts", sa.Column("bonus_coins", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("mining_accounts", sa.Column("reserved_coins", sa.BigInteger(), nullable=False, server_default="0"))
    op.add_column("mining_accounts", sa.Column("ad_boost_expires_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("user_boosts", sa.Column("purchase_id", sa.String(length=256), nullable=True))
    op.add_column("user_boosts", sa.Column("status", sa.String(length=32), nullable=False, server_default="active"))
    op.add_column("user_boosts", sa.Column("upgraded_from_plan_id", sa.Integer(), nullable=True))
    op.add_column("user_boosts", sa.Column("credit_coins_applied", sa.BigInteger(), nullable=False, server_default="0"))
    op.create_foreign_key(
        "fk_user_boosts_upgraded_from_plan",
        "user_boosts",
        "boost_plans",
        ["upgraded_from_plan_id"],
        ["id"],
    )

    op.add_column("referrals", sa.Column("telegram_verify_reward_paid", sa.Boolean(), nullable=False, server_default=sa.true()))

    op.alter_column("transactions", "reference", new_column_name="reference_id")
    op.add_column("transactions", sa.Column("source", sa.String(length=64), nullable=True))
    op.add_column("transactions", sa.Column("metadata", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("transactions", "metadata")
    op.drop_column("transactions", "source")
    op.alter_column("transactions", "reference_id", new_column_name="reference")

    op.drop_column("referrals", "telegram_verify_reward_paid")

    op.drop_constraint("fk_user_boosts_upgraded_from_plan", "user_boosts", type_="foreignkey")
    op.drop_column("user_boosts", "credit_coins_applied")
    op.drop_column("user_boosts", "upgraded_from_plan_id")
    op.drop_column("user_boosts", "status")
    op.drop_column("user_boosts", "purchase_id")

    op.drop_column("mining_accounts", "ad_boost_expires_at")
    op.drop_column("mining_accounts", "reserved_coins")
    op.drop_column("mining_accounts", "bonus_coins")
