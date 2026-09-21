from app.database import db
from datetime import datetime, timezone
import enum


# Seed default tasks & boost plans on first boot
def seed_default_tasks():
    """Seed default tasks if none exist."""
    if Task.query.count() == 0:
        tasks = [
            Task(
                name="join_channel",
                display_name="Join Telegram Channel",
                description="Join our official channel for updates",
                task_type=TaskType.JOIN_CHANNEL,
                reward_coins=25000,
                target_url="https://t.me/yourchannel",
                is_active=True,
                is_repeatable=False,
            ),
            Task(
                name="join_group",
                display_name="Join Telegram Group",
                description="Join our community group",
                task_type=TaskType.JOIN_GROUP,
                reward_coins=20000,
                target_url="https://t.me/yourgroup",
                is_active=True,
                is_repeatable=False,
            ),
            Task(
                name="visit_website",
                display_name="Visit Website",
                description="Visit our official website",
                task_type=TaskType.VISIT_WEBSITE,
                reward_coins=10000,
                target_url="https://yourwebsite.com",
                is_active=True,
                is_repeatable=False,
            ),
            Task(
                name="daily_login",
                display_name="Daily Login",
                description="Open the app every day",
                task_type=TaskType.DAILY_LOGIN,
                reward_coins=5000,
                is_active=True,
                is_repeatable=True,
            ),
            Task(
                name="invite_friend",
                display_name="Invite a Friend",
                description="Share your referral link",
                task_type=TaskType.INVITE_FRIEND,
                reward_coins=10000,
                is_active=True,
                is_repeatable=True,
            ),
        ]
        for t in tasks:
            db.session.add(t)
        db.session.commit()


def seed_boost_plans():
    """Seed default boost plans if none exist."""
    if BoostPlan.query.count() == 0:
        plans = [
            BoostPlan(
                name="normal",
                display_name="Normal",
                emoji="⛏️",
                mining_rate=1000,
                price_stars=0,
                duration_days=0,
                is_active=True,
            ),
            BoostPlan(
                name="bronze",
                display_name="Bronze",
                emoji="🥉",
                mining_rate=5000,
                price_stars=79,
                duration_days=7,
                is_active=True,
            ),
            BoostPlan(
                name="silver",
                display_name="Silver",
                emoji="🥈",
                mining_rate=10000,
                price_stars=159,
                duration_days=7,
                is_active=True,
            ),
            BoostPlan(
                name="gold",
                display_name="Gold",
                emoji="🥇",
                mining_rate=20000,
                price_stars=299,
                duration_days=7,
                is_active=True,
            ),
        ]
        for p in plans:
            db.session.add(p)
        db.session.commit()


class TransactionType(str, enum.Enum):
    MINING = "MINING"
    AD_REWARD = "AD_REWARD"
    REFERRAL = "REFERRAL"
    DAILY_REWARD = "DAILY_REWARD"
    TASK_REWARD = "TASK_REWARD"
    BOOST_PURCHASE = "BOOST_PURCHASE"
    COIN_PURCHASE = "COIN_PURCHASE"
    WITHDRAWAL = "WITHDRAWAL"
    WITHDRAWAL_FEE = "WITHDRAWAL_FEE"
    REFUND = "REFUND"
    ADMIN_ADJUSTMENT = "ADMIN_ADJUSTMENT"
    BONUS = "BONUS"
    REVERSAL = "REVERSAL"
    PENDING_RELEASE = "PENDING_RELEASE"
    # Legacy aliases kept for migration compatibility
    BOOST = "BOOST"
    PURCHASE = "PURCHASE"
    WITHDRAW = "WITHDRAW"
    TASK = "TASK"


class WithdrawalStatus(str, enum.Enum):
    PENDING = "PENDING"
    REVIEW = "REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PAID = "PAID"
    CANCELLED = "CANCELLED"


class ReferralMilestone(str, enum.Enum):
    TELEGRAM_VERIFY = "TELEGRAM_VERIFY"   # +100
    FIRST_MINING = "FIRST_MINING"         # +200
    ACTIVITY_24H = "ACTIVITY_24H"         # +200


class TaskType(str, enum.Enum):
    JOIN_CHANNEL = "JOIN_CHANNEL"
    JOIN_GROUP = "JOIN_GROUP"
    FOLLOW = "FOLLOW"
    VISIT_WEBSITE = "VISIT_WEBSITE"
    PLAY_GAME = "PLAY_GAME"
    DAILY_LOGIN = "DAILY_LOGIN"
    INVITE_FRIEND = "INVITE_FRIEND"


class UserTaskStatus(str, enum.Enum):
    PENDING = "PENDING"
    VERIFYING = "VERIFYING"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class User(db.Model):
    """Core user model — Telegram identity."""
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)  # Telegram user ID
    telegram_id = db.Column(db.BigInteger, unique=True, nullable=False, index=True)
    username = db.Column(db.String(64), nullable=True)
    first_name = db.Column(db.String(128), nullable=False)
    last_name = db.Column(db.String(128), nullable=True)
    photo_url = db.Column(db.String(512), nullable=True)
    language_code = db.Column(db.String(8), nullable=True)
    is_premium = db.Column(db.Boolean, default=False)
    is_banned = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    referral_code = db.Column(db.String(32), unique=True, nullable=True, index=True)
    referred_by_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    last_seen_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    # Relationships
    mining_account = db.relationship("MiningAccount", back_populates="user", uselist=False, cascade="all, delete-orphan")
    transactions = db.relationship("Transaction", back_populates="user", cascade="all, delete-orphan")
    withdrawals = db.relationship("Withdrawal", back_populates="user", cascade="all, delete-orphan")
    ad_rewards = db.relationship("AdReward", back_populates="user", cascade="all, delete-orphan")
    referrals_made = db.relationship("Referral", foreign_keys="Referral.referrer_id", back_populates="referrer", cascade="all, delete-orphan")
    user_tasks = db.relationship("UserTask", back_populates="user", cascade="all, delete-orphan")
    user_daily_rewards = db.relationship("UserDailyReward", back_populates="user", cascade="all, delete-orphan")
    user_boosts = db.relationship("UserBoost", back_populates="user", cascade="all, delete-orphan")
    coin_purchases = db.relationship("CoinPurchase", back_populates="user", cascade="all, delete-orphan")

    def to_dict(self):
        return {
            "telegram_id": self.telegram_id,
            "username": self.username,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "photo_url": self.photo_url,
            "is_premium": self.is_premium,
            "referral_code": self.referral_code,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MiningAccount(db.Model):
    """Per-user mining balance ledger (source of truth)."""
    __tablename__ = "mining_accounts"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), unique=True, nullable=False, index=True)

    # Two-balance system
    available_coins = db.Column(db.BigInteger, default=0, nullable=False)   # withdrawal-eligible mined coins
    pending_coins = db.Column(db.BigInteger, default=0, nullable=False)     # awaiting validation

    # Coin category tracking (separate ledgers)
    mined_coins_total = db.Column(db.BigInteger, default=0, nullable=False)     # lifetime mined
    purchased_coins = db.Column(db.BigInteger, default=0, nullable=False)       # bought with Stars (NOT withdrawal-eligible)
    bonus_coins = db.Column(db.BigInteger, default=0, nullable=False)           # admin bonuses
    spent_coins = db.Column(db.BigInteger, default=0, nullable=False)           # total withdrawn/spent

    # Mining state
    mining_rate = db.Column(db.Integer, default=5000, nullable=False)      # coins/hour (Normal = 5000)
    last_mining_started_at = db.Column(db.DateTime(timezone=True), nullable=True)
    last_claimed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_mining = db.Column(db.Boolean, default=False)

    # 2x mining boost from ad
    ad_boost_expires_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # Active boost reference
    active_boost_id = db.Column(db.BigInteger, db.ForeignKey("user_boosts.id"), nullable=True)

    # Withdrawal-reserved coins (deducted from available but not yet paid)
    reserved_coins = db.Column(db.BigInteger, default=0, nullable=False)

    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationships
    user = db.relationship("User", back_populates="mining_account")
    mining_sessions = db.relationship("MiningSession", back_populates="mining_account", cascade="all, delete-orphan")

    @property
    def total_balance(self):
        return self.available_coins + self.pending_coins

    def get_effective_rate(self):
        """Return mining rate with 2x ad boost applied if active."""
        now = datetime.now(timezone.utc)
        if self.ad_boost_expires_at:
            exp = self.ad_boost_expires_at
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp > now:
                return self.mining_rate * 2
        return self.mining_rate

    def to_dict(self):
        return {
            "available_coins": self.available_coins,
            "pending_coins": self.pending_coins,
            "total_balance": self.total_balance,
            "mined_coins_total": self.mined_coins_total,
            "purchased_coins": self.purchased_coins,
            "bonus_coins": self.bonus_coins,
            "reserved_coins": self.reserved_coins,
            "mining_rate": self.mining_rate,
            "effective_rate": self.get_effective_rate(),
            "is_mining": self.is_mining,
            "ad_boost_expires_at": self.ad_boost_expires_at.isoformat() if self.ad_boost_expires_at else None,
            "last_mining_started_at": self.last_mining_started_at.isoformat() if self.last_mining_started_at else None,
            "last_claimed_at": self.last_claimed_at.isoformat() if self.last_claimed_at else None,
        }


class MiningSession(db.Model):
    """Records each individual mining session."""
    __tablename__ = "mining_sessions"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    mining_account_id = db.Column(db.BigInteger, db.ForeignKey("mining_accounts.id"), nullable=False, index=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False)
    claimed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    coins_earned = db.Column(db.BigInteger, default=0)
    mining_rate_snapshot = db.Column(db.Integer, nullable=False)   # rate at session start
    is_claimed = db.Column(db.Boolean, default=False)

    mining_account = db.relationship("MiningAccount", back_populates="mining_sessions")

    def to_dict(self):
        return {
            "id": self.id,
            "started_at": self.started_at.isoformat(),
            "claimed_at": self.claimed_at.isoformat() if self.claimed_at else None,
            "coins_earned": self.coins_earned,
            "mining_rate_snapshot": self.mining_rate_snapshot,
            "is_claimed": self.is_claimed,
        }


class Transaction(db.Model):
    """Immutable financial ledger — every coin movement recorded here."""
    __tablename__ = "transactions"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, index=True)
    type = db.Column(db.Enum(TransactionType), nullable=False)
    amount = db.Column(db.BigInteger, nullable=False)           # positive = credit, negative = debit
    balance_before = db.Column(db.BigInteger, nullable=False)
    balance_after = db.Column(db.BigInteger, nullable=False)
    source = db.Column(db.String(64), nullable=True)            # which balance: available/pending
    reference_id = db.Column(db.String(256), nullable=True)     # session_id, ad_event_id, etc.
    metadata_ = db.Column("metadata", db.Text, nullable=True)   # JSON string for extra data
    note = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User", back_populates="transactions")

    def to_dict(self):
        return {
            "id": self.id,
            "type": self.type.value,
            "amount": self.amount,
            "balance_before": self.balance_before,
            "balance_after": self.balance_after,
            "source": self.source,
            "reference_id": self.reference_id,
            "note": self.note,
            "created_at": self.created_at.isoformat(),
        }


class BoostPlan(db.Model):
    """Available mining boost plans."""
    __tablename__ = "boost_plans"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(32), unique=True, nullable=False)
    display_name = db.Column(db.String(64), nullable=False)
    emoji = db.Column(db.String(8), nullable=False)
    mining_rate = db.Column(db.Integer, nullable=False)              # coins/hour
    price_stars = db.Column(db.Integer, default=0, nullable=False)   # Telegram Stars (XTR)
    duration_days = db.Column(db.Integer, default=0, nullable=False) # 0 = forever (free)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user_boosts = db.relationship("UserBoost", foreign_keys="UserBoost.plan_id", back_populates="plan")

    def to_dict(self):
        session_earnings = self.mining_rate * 8  # 8-hour session max
        # Estimated monthly: ~30 sessions/month (active user, 1 session/day)
        monthly_estimate = session_earnings * 30
        return {
            "id": self.id,
            "name": self.name,
            "display_name": self.display_name,
            "emoji": self.emoji,
            "mining_rate": self.mining_rate,
            "price_stars": self.price_stars,
            "duration_days": self.duration_days,
            "session_earnings": session_earnings,
            "monthly_estimate": monthly_estimate,
        }


class UserBoost(db.Model):
    """Active or historical boosts per user."""
    __tablename__ = "user_boosts"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, index=True)
    plan_id = db.Column(db.Integer, db.ForeignKey("boost_plans.id"), nullable=False)
    purchase_id = db.Column(db.String(256), nullable=True)                  # internal purchase reference
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    expires_at = db.Column(db.DateTime(timezone=True), nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    status = db.Column(db.String(32), default="active", nullable=False)     # active, expired, cancelled
    telegram_payment_charge_id = db.Column(db.String(256), nullable=True, unique=True)
    stars_paid = db.Column(db.Integer, nullable=True)
    upgraded_from_plan_id = db.Column(db.Integer, db.ForeignKey("boost_plans.id"), nullable=True)  # for upgrades
    credit_coins_applied = db.Column(db.BigInteger, default=0)              # credit from previous boost on upgrade

    user = db.relationship("User", back_populates="user_boosts")
    plan = db.relationship("BoostPlan", foreign_keys=[plan_id], back_populates="user_boosts")

    def to_dict(self):
        return {
            "id": self.id,
            "plan": self.plan.to_dict() if self.plan else None,
            "started_at": self.started_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "is_active": self.is_active,
            "status": self.status,
            "stars_paid": self.stars_paid,
        }


class Referral(db.Model):
    """Tracks referral relationships and reward milestones."""
    __tablename__ = "referrals"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    referrer_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, index=True)
    referee_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, unique=True, index=True)
    telegram_verify_reward_paid = db.Column(db.Boolean, default=True)   # +100 coins (auto on join)
    first_mining_reward_paid = db.Column(db.Boolean, default=False)     # +200 coins
    activity_24h_reward_paid = db.Column(db.Boolean, default=False)     # +200 coins
    total_reward_paid = db.Column(db.BigInteger, default=0)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    referrer = db.relationship("User", foreign_keys=[referrer_id], back_populates="referrals_made")

    def to_dict(self):
        return {
            "id": self.id,
            "referrer_id": self.referrer_id,
            "referee_id": self.referee_id,
            "first_mining_reward_paid": self.first_mining_reward_paid,
            "activity_24h_reward_paid": self.activity_24h_reward_paid,
            "total_reward_paid": self.total_reward_paid,
            "created_at": self.created_at.isoformat(),
        }


class Task(db.Model):
    """Configurable tasks users can complete for coin rewards."""
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String(64), unique=True, nullable=False)     # unique slug e.g. join_channel
    display_name = db.Column(db.String(128), nullable=False)         # human-readable title
    task_type = db.Column(db.Enum(TaskType), nullable=False)
    description = db.Column(db.String(512), nullable=True)
    reward_coins = db.Column(db.BigInteger, nullable=False)
    target_url = db.Column(db.String(512), nullable=True)            # channel/group/website link
    is_active = db.Column(db.Boolean, default=True)
    is_repeatable = db.Column(db.Boolean, default=False)             # daily login etc.
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user_tasks = db.relationship("UserTask", back_populates="task")

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "task_type": self.task_type.value,
            "display_name": self.display_name,
            "description": self.description,
            "reward_coins": self.reward_coins,
            "target_url": self.target_url,
            "is_active": self.is_active,
            "is_repeatable": self.is_repeatable,
        }


class UserTask(db.Model):
    """User's task completion record."""
    __tablename__ = "user_tasks"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, index=True)
    task_id = db.Column(db.Integer, db.ForeignKey("tasks.id"), nullable=False, index=True)
    status = db.Column(db.Enum(UserTaskStatus), default=UserTaskStatus.PENDING, nullable=False)
    reward_coins = db.Column(db.BigInteger, nullable=True)
    completed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", back_populates="user_tasks")
    task = db.relationship("Task", back_populates="user_tasks")

    def to_dict(self):
        return {
            "id": self.id,
            "task": self.task.to_dict() if self.task else None,
            "status": self.status.value,
            "reward_coins": self.reward_coins,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }


class UserDailyReward(db.Model):
    """Tracks daily login streak and reward claims."""
    __tablename__ = "user_daily_rewards"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), unique=True, nullable=False, index=True)
    current_streak = db.Column(db.Integer, default=0)
    last_claimed_date = db.Column(db.Date, nullable=True)
    total_days_claimed = db.Column(db.Integer, default=0)

    user = db.relationship("User", back_populates="user_daily_rewards")

    def to_dict(self):
        return {
            "current_streak": self.current_streak,
            "last_claimed_date": self.last_claimed_date.isoformat() if self.last_claimed_date else None,
            "total_days_claimed": self.total_days_claimed,
        }


class AdReward(db.Model):
    """Records each ad reward event for dedup and analytics."""
    __tablename__ = "ad_rewards"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, index=True)
    ad_event_id = db.Column(db.String(256), nullable=True, unique=True)   # Monetag event ID
    coins_awarded = db.Column(db.Integer, nullable=False)
    ad_type = db.Column(db.String(64), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)

    user = db.relationship("User", back_populates="ad_rewards")

    def to_dict(self):
        return {
            "id": self.id,
            "coins_awarded": self.coins_awarded,
            "ad_type": self.ad_type,
            "created_at": self.created_at.isoformat(),
        }


class CoinPurchase(db.Model):
    """Records coin purchases made with Telegram Stars."""
    __tablename__ = "coin_purchases"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, index=True)
    stars_paid = db.Column(db.Integer, nullable=False)
    coins_received = db.Column(db.BigInteger, nullable=False)
    telegram_payment_charge_id = db.Column(db.String(256), unique=True, nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = db.relationship("User", back_populates="coin_purchases")

    def to_dict(self):
        return {
            "id": self.id,
            "stars_paid": self.stars_paid,
            "coins_received": self.coins_received,
            "created_at": self.created_at.isoformat(),
        }


class Withdrawal(db.Model):
    """Withdrawal requests from users."""
    __tablename__ = "withdrawals"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    user_id = db.Column(db.BigInteger, db.ForeignKey("users.telegram_id"), nullable=False, index=True)
    requested_coins = db.Column(db.BigInteger, nullable=False)
    fee_coins = db.Column(db.BigInteger, nullable=False)
    net_coins = db.Column(db.BigInteger, nullable=False)
    method = db.Column(db.String(64), nullable=False)
    destination = db.Column(db.String(256), nullable=True)       # wallet address, phone, etc.
    status = db.Column(db.Enum(WithdrawalStatus), default=WithdrawalStatus.PENDING, nullable=False, index=True)
    admin_note = db.Column(db.String(512), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
    processed_at = db.Column(db.DateTime(timezone=True), nullable=True)

    user = db.relationship("User", back_populates="withdrawals")

    def to_dict(self):
        return {
            "id": self.id,
            "requested_coins": self.requested_coins,
            "fee_coins": self.fee_coins,
            "net_coins": self.net_coins,
            "method": self.method,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "processed_at": self.processed_at.isoformat() if self.processed_at else None,
        }


class AppSetting(db.Model):
    """Dynamic app settings editable from admin panel."""
    __tablename__ = "app_settings"

    key = db.Column(db.String(128), primary_key=True)
    value = db.Column(db.Text, nullable=False)
    description = db.Column(db.String(512), nullable=True)
    updated_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        return {"key": self.key, "value": self.value}


class AuditLog(db.Model):
    """Admin action audit trail."""
    __tablename__ = "audit_logs"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    admin_id = db.Column(db.BigInteger, nullable=False)
    action = db.Column(db.String(128), nullable=False)
    target_user_id = db.Column(db.BigInteger, nullable=True)
    detail = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
