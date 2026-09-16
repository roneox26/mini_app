# ⛏️ Telegram Mining App

A full-stack Telegram Mini App with auto-mining, Monetag ads, Telegram Stars payments, and a referral system.

## 🏗️ Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | HTML + CSS + JavaScript (Glassmorphism UI) |
| Backend | Python + Flask |
| Database | PostgreSQL + SQLAlchemy |
| Cache | Redis |
| Workers | Celery |
| Bot | Telegram Bot API |
| Ads | Monetag |
| Payments | Telegram Stars (XTR) |
| Deployment | Docker + Nginx + Cloudflare |

## 📁 Project Structure

```
miniapp/
├── backend/          # Flask API
│   ├── app/
│   │   ├── __init__.py        # App factory
│   │   ├── config.py          # All settings
│   │   ├── database.py        # SQLAlchemy init
│   │   ├── models/            # DB models
│   │   ├── api/v1/            # All API routes
│   │   ├── services/          # Business logic
│   │   ├── security/          # Telegram auth + JWT
│   │   └── workers/           # Celery tasks
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/         # Telegram Mini App UI
│   ├── index.html
│   ├── css/style.css
│   └── js/app.js
├── bot/              # Telegram Bot
├── nginx/            # Reverse proxy
├── docker-compose.yml
└── .env.example
```

## 🚀 Quick Start (Development)

### 1. Clone & Configure

```bash
cp .env.example .env
# Edit .env with your Telegram Bot Token, DB credentials, etc.
```

### 2. Install Backend

```bash
cd backend
pip install -r requirements.txt
```

### 3. Start Services (Docker)

```bash
docker-compose up -d postgres redis
```

### 4. Run Database Migrations

```bash
cd backend
flask db init
flask db migrate -m "Initial schema"
flask db upgrade
```

### 5. Run Backend

```bash
cd backend
python app/main.py
# API running at http://localhost:5000
```

### 6. Serve Frontend

Open `frontend/index.html` in a browser, or use a local tunnel:
```bash
npx localtunnel --port 80 --subdomain your-mining-app
```

### 7. Set Telegram Webhook

```bash
python bot/bot.py set_webhook https://your-tunnel-url/webhook
```

## 📡 API Reference

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/auth/telegram` | POST | Authenticate with Telegram initData |
| `/api/v1/me` | GET | Get user profile + balance |
| `/api/v1/mining/start` | POST | Start mining session |
| `/api/v1/mining/status` | GET | Get current mining status |
| `/api/v1/mining/claim` | POST | Claim mined coins |
| `/api/v1/boosts` | GET | List boost plans |
| `/api/v1/boosts/{plan}/buy` | POST | Purchase boost with Stars |
| `/api/v1/ads/reward` | POST | Claim ad reward |
| `/api/v1/referrals/stats` | GET | Referral stats |
| `/api/v1/rewards/daily` | POST | Claim daily reward |
| `/api/v1/tasks` | GET | List tasks |
| `/api/v1/tasks/{id}/complete` | POST | Complete a task |
| `/api/v1/leaderboard` | GET | Top 100 miners |
| `/api/v1/coins/purchase` | POST | Purchase coins with Stars |
| `/api/v1/withdrawals` | POST | Request withdrawal |

## 💰 Coin Economy

| Plan | Rate | Price | Duration |
|------|------|-------|----------|
| 🆓 Normal | 10/hr | Free | Forever |
| 🥉 Bronze | 20/hr | 99 ⭐ | 7 days |
| 🥈 Silver | 50/hr | 199 ⭐ | 7 days |
| 🥇 Gold | 100/hr | 399 ⭐ | 7 days |

**Mining Formula:**
```
earned = elapsed_seconds × rate_per_hour / 3600
```
Max session: **8 hours**. Frontend never calculates balance — always server timestamps.

## 🔒 Security

- ✅ Telegram initData server-side HMAC-SHA256 validation
- ✅ JWT Bearer token auth
- ✅ Redis rate limiting + anti-spam
- ✅ Idempotent payment processing (duplicate charge ID detection)
- ✅ Admin RBAC decorators
- ✅ Database transactions (no double-spend)
- ✅ Environment variable secrets

## 🚢 Production Deployment

```bash
# Full stack
docker-compose up -d

# View logs
docker-compose logs -f backend

# Scale backend workers
docker-compose up -d --scale backend=3
```

Point your domain's DNS to the server, configure SSL in `nginx/nginx.conf`, and set Cloudflare as your CDN.

## ☁️ Deploy on Render

This repository includes `render.yaml` and a root `Dockerfile` for a Render Blueprint deployment. The Blueprint creates:

- one public web service that runs migrations, serves the Flask API, user Mini App at `/`, admin panel at `/admin`, and Telegram webhook at `/webhook`
- managed PostgreSQL and Redis-compatible Key Value services

1. Push the repository to GitHub and create a new **Blueprint** in Render from that repository.
2. During the first deploy, enter the values marked `sync: false`, especially `TELEGRAM_BOT_TOKEN`, `FIRST_ADMIN_TELEGRAM_ID`, and Monetag credentials.
3. After the web service is live, set the Telegram webhook to the same web service URL:

```bash
python bot/bot.py set_webhook https://YOUR-WEB-SERVICE.onrender.com/webhook
```

4. Set `FRONTEND_URL` to the web service URL if you use a custom Render URL or domain.

Render web services provide their own `PORT`; the included startup command binds to it automatically. Keep the Postgres and Redis services running because the API, rate limiter, and cache depend on them. Celery scheduled jobs are not started in this one-service profile.

## ⚠️ Notes

- **Crypto withdrawal is DISABLED** by default (Bangladesh Bank compliance)
- Monetag ad rewards require backend validation before coins are credited
- Telegram Stars payments are verified via webhook `successful_payment` events
