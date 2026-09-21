# সিস্টেম স্থিতিশীলতা অপ্টিমাইজেশন গাইড
# System Stability Optimization Guide

## 📊 করা হয়েছে যা পরিবর্তন (Changes Made)

### 1. **রেট লিমিটিং অপ্টিমাইজেশন (Rate Limiting)**
```
পুরাতন: 200 per day; 50 per hour
নতুন:   10000 per day; 1000 per hour; 100 per minute
```
- প্রতিটি ব্যবহারকারী আরও বেশি অনুরোধ পাঠাতে পারে
- টোকেন-ভিত্তিক রেট লিমিটিং (IP এর পরিবর্তে)
- বাস্তব-বিশ্বের ট্রাফিক পরিচালনা করতে পারে

### 2. **ডাটাবেস পুল আপগ্রেড (Database Connection Pooling)**
```
পুরাতন: pool_size=10, max_overflow=20
নতুন:   pool_size=30, max_overflow=50
```
- সমসাময়িক সংযোগ 10 থেকে 30+ এ বৃদ্ধি
- বার্স্ট ট্রাফিকের জন্য 50 অতিরিক্ত সংযোগ
- স্বয়ংক্রিয় সংযোগ পুনর্ব্যবহার এবং পুনঃসেট

### 3. **গুনিকর্ন ওয়ার্কার বৃদ্ধি (Gunicorn Workers)**
```
পুরাতন: 4 workers
নতুন:   8 workers (স্বয়ংক্রিয় CPU-ভিত্তিক: 2*cores + 1)
```
- প্রতিটি ওয়ার্কার 1000 সংযোগ পরিচালনা করতে পারে
- স্বয়ংক্রিয় ওয়ার্কার রিসাইক্লিং (মেমরি লিক প্রতিরোধ)
- সচেতন শাটডাউন (graceful shutdown)

### 4. **রেডিস অপ্টিমাইজেশন (Redis)**
```
পুরাতন: 256MB max memory
নতুন:   512MB max memory + LRU eviction policy
```
- বেশি ক্যাশ স্টোরেজ
- স্মার্ট মেমরি ম্যানেজমেন্ট
- TCP কিপালাইভ সক্ষম

### 5. **PostgreSQL পারফরম্যান্স (Database Performance)**
```
নতুন কনফিগারেশন:
- max_connections: 200
- shared_buffers: 256MB
- effective_cache_size: 1GB
- work_mem: 4MB
```

### 6. **ত্রুটি হ্যান্ডলিং (Error Handling)**
- 429 (রেট লিমিট) ত্রুটি এখন বন্ধুত্বপূর্ণ বার্তা সহ
- 500 (সার্ভার) ত্রুটি সঠিকভাবে পরিচালিত
- ডাটাবেস সেশন পরিষ্কারভাবে বন্ধ হয়

---

## 🚀 ডিপ্লয়মেন্ট গাইড (Deployment Guide)

### প্রিরিকোইজিট (Prerequisites):
- Docker & Docker Compose
- PostgreSQL 16+
- Redis 7+
- Python 3.11+

### পদক্ষেপ 1: পরিবেশ সেটআপ করুন
```bash
# প্রোডাকশন এনভায়রনমেন্ট ফাইল কপি করুন
cp backend/.env.production.example .env

# আপনার সংবেদনশীল তথ্য সহ সম্পাদনা করুন
nano .env
```

### পদক্ষেপ 2: Docker-Compose চালান
```bash
# সবকিছু বিল্ড এবং শুরু করুন
docker-compose up -d

# লগ দেখুন
docker-compose logs -f backend

# স্বাস্থ্য পরীক্ষা করুন
curl http://localhost:5000/health
```

### পদক্ষেপ 3: সিস্টেম মনিটর করুন
```bash
# চলমান কন্টেইনার পরীক্ষা করুন
docker-compose ps

# কন্টেইনার লগ দেখুন
docker-compose logs backend    # ব্যাকএন্ড
docker-compose logs postgres   # ডাটাবেস
docker-compose logs redis      # ক্যাশ
docker-compose logs worker     # কাজের প্রক্রিয়া
```

---

## ⚙️ কনফিগারেশন টিউনিং

### উচ্চ ট্রাফিক (10,000+ ব্যবহারকারী)
```yaml
# docker-compose.yml মধ্যে
backend:
  environment:
    GUNICORN_WORKERS: 16  # বাড়ান
    
worker:
  environment:
    CELERY_WORKER_CONCURRENCY: 8  # বাড়ান
```

### মাঝারি ট্রাফিক (1,000-5,000 ব্যবহারকারী)
```yaml
backend:
  environment:
    GUNICORN_WORKERS: 8

worker:
  environment:
    CELERY_WORKER_CONCURRENCY: 4
```

### কম ট্রাফিক (100-1,000 ব্যবহারকারী)
```yaml
backend:
  environment:
    GUNICORN_WORKERS: 4

worker:
  environment:
    CELERY_WORKER_CONCURRENCY: 2
```

---

## 📈 পারফরম্যান্স মেট্রিক্স

### প্রত্যাশিত থ্রুপুট (Throughput):
- **একক সার্ভার**: 1000-2000 অনুরোধ/সেকেন্ড
- **8 ওয়ার্কার সহ**: 8000-16000 অনুরোধ/সেকেন্ড
- **সম্পূর্ণ স্ট্যাক**: 10,000+ ব্যবহারকারী একসাথে

### DB সংযোগ ব্যবহার:
- স্বাভাবিক: 15-20 সংযোগ
- পিক লোড: 40-50 সংযোগ
- সর্বোচ্চ: 80 সংযোগ (নিরাপদ সীমার মধ্যে)

---

## 🔍 সমস্যা সমাধান (Troubleshooting)

### সমস্যা: এখনও "Too Many Requests" ত্রুটি
**সমাধান:**
```bash
# রেট লিমিট বাড়ান
# .env এ:
RATE_LIMIT_DEFAULT=50000 per day;5000 per hour;500 per minute

# Docker-compose পুনরায় চালান
docker-compose restart backend
```

### সমস্যা: ডাটাবেস সংযোগ পূর্ণ
**সমাধান:**
```bash
# মনিটর সংযোগ:
docker-compose exec postgres psql -U mininguser -d miningdb -c \
  "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# সমস্ত নিষ্ক্রিয় সংযোগ বন্ধ করুন:
docker-compose exec postgres psql -U mininguser -d miningdb -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'idle' AND query_start < NOW() - INTERVAL '10 minutes';"
```

### সমস্যা: মেমরি লিক
**সমাধান:**
```bash
# ওয়ার্কার রিসাইক্লিং পরীক্ষা করুন
# gunicorn_config.py:
max_requests = 1000  # প্রতি N অনুরোধে পুনরায় শুরু করুন

# লগে দেখতে পাবেন:
# [Gunicorn] Worker restarted
```

---

## 📊 মনিটরিং সেটআপ

### সিস্টেম লগ দেখুন:
```bash
# সমস্ত লগ রিয়েল-টাইমে
docker-compose logs -f

# শুধুমাত্র ত্রুটি
docker-compose logs backend | grep ERROR

# নির্দিষ্ট সেবা
docker-compose logs -f --tail=50 backend
```

### রিডিস স্ট্যাটাস:
```bash
docker-compose exec redis redis-cli INFO stats
docker-compose exec redis redis-cli DBSIZE
```

### ডাটাবেস স্ট্যাটাস:
```bash
docker-compose exec postgres psql -U mininguser -d miningdb \
  -c "SELECT version();"
  
docker-compose exec postgres psql -U mininguser -d miningdb \
  -c "SELECT count(*) FROM users;"
```

---

## ✅ যা যাচাই করবেন (Checklist)

- [ ] `.env` ফাইল সঠিকভাবে কনফিগার করা হয়েছে
- [ ] `docker-compose up -d` সফলভাবে চালু হয়েছে
- [ ] সব সেবা চলছে: `docker-compose ps`
- [ ] হেলথ চেক পাস: `curl http://localhost:5000/health`
- [ ] ডাটাবেস মাইগ্রেশন সম্পূর্ণ হয়েছে
- [ ] রেডিস সংযুক্ত: `redis-cli PING`
- [ ] ওয়ার্কার কাজ করছে: `docker-compose logs worker`

---

## 📞 সাপোর্ট

যদি সমস্যা থাকে:
1. লগ চেক করুন: `docker-compose logs backend`
2. কন্টেইনার স্বাস্থ্য পরীক্ষা করুন: `docker-compose ps`
3. সার্ভার রিবুট করুন: `docker-compose restart`
4. সম্পূর্ণ পুনরায় তৈরি করুন: `docker-compose down && docker-compose up -d`
