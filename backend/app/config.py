import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Base configuration."""

    # Flask
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = False
    TESTING = False

    # SQLAlchemy
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL", "postgresql://mininguser:miningpassword@localhost:5432/miningdb")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 300,
        "pool_size": 30,           # Increased from 10 for concurrent connections
        "max_overflow": 50,        # Increased from 20 for burst traffic
        "pool_timeout": 30,        # Wait up to 30s for available connection
        "pool_echo": False,
        "connect_args": {
            "connect_timeout": 5,
            "keepalives": 1,
            "keepalives_idle": 30,
            "keepalives_interval": 10,
            "keepalives_count": 5,
        },
    }

    # Redis
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

    # JWT
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "jwt-secret-change-in-production")
    JWT_EXPIRY_HOURS = int(os.getenv("JWT_EXPIRY_HOURS", "24"))

    # Telegram
    TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_BOT_USERNAME = os.getenv("TELEGRAM_BOT_USERNAME", "")

    # Monetag
    MONETAG_PUBLISHER_ID = os.getenv("MONETAG_PUBLISHER_ID", "")
    MONETAG_ZONE_ID_REWARDED = os.getenv("MONETAG_ZONE_ID_REWARDED", "")
    MONETAG_ZONE_ID_POPUP = os.getenv("MONETAG_ZONE_ID_POPUP", "")
    MONETAG_SECRET_KEY = os.getenv("MONETAG_SECRET_KEY", "")
    MONETAG_SDK_URL = os.getenv("MONETAG_SDK_URL", "")

    # Admin
    ADMIN_SECRET_KEY = os.getenv("ADMIN_SECRET_KEY", "admin-secret-change-in-production")
    FIRST_ADMIN_TELEGRAM_ID = int(os.getenv("FIRST_ADMIN_TELEGRAM_ID", "0"))

    # CORS
    FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:3000")
    ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")

    # Mining Economy — initial launch values (all configurable via admin panel)
    DEFAULT_MINING_RATE = int(os.getenv("DEFAULT_MINING_RATE", "1000"))     # coins/hour (Normal plan)
    MINING_SESSION_HOURS = int(os.getenv("MINING_SESSION_HOURS", "8"))      # max session hours

    # Ad Rewards
    AD_REWARD_COINS = int(os.getenv("AD_REWARD_COINS", "250"))             # coins per completed ad
    AD_COOLDOWN_MINUTES = int(os.getenv("AD_COOLDOWN_MINUTES", "5"))       # cooldown between ads
    AD_DAILY_LIMIT = int(os.getenv("AD_DAILY_LIMIT", "5"))                 # max rewarded ads/user/day (max 1,250/day)
    AD_2X_DURATION_MINUTES = int(os.getenv("AD_2X_DURATION_MINUTES", "30")) # 2x mining boost from ad

    # Referral Rewards — milestone-based, total = 500 coins
    # Milestone 1: Telegram verify (auto on join) = 100
    # Milestone 2: First mining session claim     = 200
    # Milestone 3: 24h activity                  = 200
    REFERRAL_REWARD_TELEGRAM_VERIFY = int(os.getenv("REFERRAL_REWARD_TELEGRAM_VERIFY", "100"))
    REFERRAL_REWARD_FIRST_MINING = int(os.getenv("REFERRAL_REWARD_FIRST_MINING", "200"))
    REFERRAL_REWARD_24H_ACTIVITY = int(os.getenv("REFERRAL_REWARD_24H_ACTIVITY", "200"))

    # Withdrawal
    MIN_WITHDRAWAL_COINS = int(os.getenv("MIN_WITHDRAWAL_COINS", "500000"))  # 500,000 coins ≈ ৳500
    WITHDRAWAL_FEE_PERCENT = float(os.getenv("WITHDRAWAL_FEE_PERCENT", "5"))
    MIN_WITHDRAWAL_FEE_COINS = int(os.getenv("MIN_WITHDRAWAL_FEE_COINS", "1000"))

    # Coin reference value (for display only — NOT a guaranteed rate)
    # 1,000 coins ≈ ৳1 (reference only, admin-configurable)
    COIN_REFERENCE_VALUE_BDT = float(os.getenv("COIN_REFERENCE_VALUE_BDT", "0.001"))  # BDT per coin

    # Daily Reward schedule (day -> coins) — 7-day streak
    # Total 7-day reward: 220,000 coins
    DAILY_REWARDS = {1: 5000, 2: 10000, 3: 15000, 4: 20000, 5: 30000, 6: 40000, 7: 100000}

    # Boost Plans — initial launch prices
    BOOST_PLANS = {
        "normal": {"rate": 1000,  "price_stars": 0,   "duration_days": 0},
        "bronze": {"rate": 5000,  "price_stars": 79,  "duration_days": 7},
        "silver": {"rate": 10000, "price_stars": 159, "duration_days": 7},
        "gold":   {"rate": 20000, "price_stars": 299, "duration_days": 7},
    }

    # Coin Purchase Packages
    COIN_PACKAGES = [
        {"stars": 100,  "coins": 100000},
        {"stars": 500,  "coins": 600000},
        {"stars": 1000, "coins": 1300000},
    ]

    # Feature Flags
    MINING_ENABLED = os.getenv("MINING_ENABLED", "true").lower() == "true"
    ADS_ENABLED = os.getenv("ADS_ENABLED", "true").lower() == "true"
    REFERRALS_ENABLED = os.getenv("REFERRALS_ENABLED", "true").lower() == "true"
    WITHDRAWALS_ENABLED = os.getenv("WITHDRAWALS_ENABLED", "true").lower() == "true"
    CRYPTO_WITHDRAWAL_ENABLED = os.getenv("CRYPTO_WITHDRAWAL_ENABLED", "false").lower() == "true"
    COIN_PURCHASE_ENABLED = os.getenv("COIN_PURCHASE_ENABLED", "true").lower() == "true"

    # Rate Limiting — More generous to handle high traffic
    # Per-user rate limits (identified by token or IP)
    RATELIMIT_DEFAULT = "10000 per day;1000 per hour;100 per minute"  # Changed from 200/50
    RATELIMIT_STORAGE_URI = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    
    # Cache configuration
    CACHE_TYPE = "redis"
    CACHE_REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/1")
    CACHE_DEFAULT_TIMEOUT = 300  # 5 minutes default
    
    # Session configuration for better resource management
    PERMANENT_SESSION_LIFETIME = 86400  # 24 hours
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS


class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class ProductionConfig(Config):
    DEBUG = False
    SQLALCHEMY_ECHO = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"


config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}


def get_config():
    env = os.getenv("FLASK_ENV", "development")
    return config_map.get(env, config_map["default"])
