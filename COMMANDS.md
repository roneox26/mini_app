# QUICK REFERENCE - কমান্ড গাইড

## 🚀 শুরু করুন (Getting Started)
```bash
# সব সেবা চালান
docker-compose up -d

# লগ দেখুন (রিয়েল-টাইম)
docker-compose logs -f

# সার্ভার বন্ধ করুন
docker-compose down

# সম্পূর্ণ পুনরায় তৈরি (ডাটা হারানো)
docker-compose down -v && docker-compose up -d
```

---

## 📊 মনিটরিং কমান্ড

### সেবার স্ট্যাটাস
```bash
# সব সেবার অবস্থা
docker-compose ps

# কোন সেবা চালু আছে
docker-compose ps --services --filter "status=running"

# বন্ধ সেবা খুঁজুন
docker-compose ps --services --filter "status=exited"
```

### লগ দেখুন
```bash
# সব লগ (শেষ 100 লাইন)
docker-compose logs --tail=100

# নির্দিষ্ট সেবা
docker-compose logs -f backend     # ব্যাকএন্ড
docker-compose logs -f postgres    # ডাটাবেস
docker-compose logs -f redis       # রেডিস
docker-compose logs -f worker      # ওয়ার্কার
docker-compose logs -f nginx       # Nginx

# শুধুমাত্র ত্রুটি
docker-compose logs backend | grep -i error

# গত 1 ঘন্টার লগ
docker-compose logs --since 1h backend
```

### সংস্থান ব্যবহার
```bash
# রিয়েল-টাইম ব্যবহার
docker-compose stats

# একবার স্ন্যাপশট
docker-compose stats --no-stream

# নির্দিষ্ট সেবা
docker-compose stats backend

# বিস্তারিত তথ্য
docker stats --no-stream mining_backend
```

---

## 🗄️ ডাটাবেস কমান্ড

### সংযোগ পরিচালনা
```bash
# সংযোগের সংখ্যা
docker-compose exec postgres psql -U mininguser -d miningdb \
  -c "SELECT datname, count(*) FROM pg_stat_activity GROUP BY datname;"

# সব সংযোগ দেখুন
docker-compose exec postgres psql -U mininguser -d miningdb \
  -c "SELECT pid, usename, state, query FROM pg_stat_activity;"

# নিষ্ক্রিয় সংযোগ বন্ধ করুন
docker-compose exec postgres psql -U mininguser -d miningdb -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE state = 'idle' AND query_start < NOW() - INTERVAL '10 minutes';"

# সব সংযোগ বন্ধ করুন (জরুরি অবস্থায়)
docker-compose exec postgres psql -U mininguser -d miningdb -c \
  "SELECT pg_terminate_backend(pid) FROM pg_stat_activity 
   WHERE datname = 'miningdb' AND pid != pg_backend_pid();"
```

### ডাটা পরীক্ষা
```bash
# ব্যবহারকারীর সংখ্যা
docker-compose exec postgres psql -U mininguser -d miningdb -c "SELECT COUNT(*) FROM users;"

# সক্রিয় খনি সেশন
docker-compose exec postgres psql -U mininguser -d miningdb -c \
  "SELECT COUNT(*) FROM mining_sessions WHERE ended_at IS NULL;"

# লেনদেন সংখ্যা
docker-compose exec postgres psql -U mininguser -d miningdb -c "SELECT COUNT(*) FROM transactions;"

# সংস্করণ পরীক্ষা করুন
docker-compose exec postgres psql -U mininguser -d miningdb -c "SELECT version();"

# ডাটাবেস আকার
docker-compose exec postgres psql -U mininguser -d miningdb -c \
  "SELECT pg_size_pretty(pg_database_size('miningdb'));"
```

### ব্যাকআপ/পুনরুদ্ধার
```bash
# সম্পূর্ণ ডাটাবেস ব্যাকআপ
docker-compose exec postgres pg_dump -U mininguser miningdb > backup.sql

# নির্দিষ্ট টেবিল ব্যাকআপ
docker-compose exec postgres pg_dump -U mininguser -t users miningdb > users_backup.sql

# ব্যাকআপ পুনরুদ্ধার করুন
docker-compose exec -T postgres psql -U mininguser miningdb < backup.sql
```

---

## 🔴 রেডিস কমান্ড

### তথ্য দেখুন
```bash
# রেডিস তথ্য
docker-compose exec redis redis-cli INFO

# মেমরি ব্যবহার
docker-compose exec redis redis-cli INFO memory

# কী গণনা
docker-compose exec redis redis-cli DBSIZE

# সব কী তালিকাভুক্ত করুন
docker-compose exec redis redis-cli KEYS '*'

# নির্দিষ্ট কী মূল্য
docker-compose exec redis redis-cli GET keyname
```

### রক্ষণাবেক্ষণ
```bash
# রেডিস সাফ করুন (সব ডাটা হারিয়ে যাবে)
docker-compose exec redis redis-cli FLUSHDB

# সম্পূর্ণ ফ্লাশ (সব DB)
docker-compose exec redis redis-cli FLUSHALL

# স্মার্ট মেমরি ফ্রি করুন (LRU)
docker-compose exec redis redis-cli CONFIG SET maxmemory-policy allkeys-lru

# সংরক্ষণ করুন
docker-compose exec redis redis-cli SAVE
```

---

## 🔧 সেবা পুনরায় চালু করুন

### একটি সেবা পুনরায় চালু করুন
```bash
# ব্যাকএন্ড
docker-compose restart backend

# ওয়ার্কার
docker-compose restart worker

# সব সেবা
docker-compose restart
```

### ক্রাশ হওয়া সেবা ঠিক করুন
```bash
# সেবা পুনর্নির্মাণ করুন
docker-compose up -d --force-recreate backend

# রিবিল্ড ইমেজ
docker-compose build --no-cache backend
docker-compose up -d backend
```

---

## 🧹 পরিষ্কার করুন ও বজায় রাখুন

### ডিস্ক স্থান মুক্ত করুন
```bash
# অব্যবহৃত কন্টেইনার সরান
docker container prune -f

# অব্যবহৃত ইমেজ সরান
docker image prune -a -f

# অব্যবহৃত ভলিউম সরান
docker volume prune -f

# সব কিছু পরিষ্কার করুন (সতর্ক!)
docker system prune -a -f
```

### লগ রোটেশন
```bash
# Docker লগ আকার সীমিত করুন
docker-compose logs --tail=1000 backend > /dev/null

# পুরানো লগ মুছুন
docker system prune --filter "until=72h" -f
```

---

## 🆘 জরুরি সমস্যা সমাধান

### সিস্টেম ঝুলে গেছে
```bash
# সেবা পুনরায় চালু করুন
docker-compose restart

# সম্পূর্ণ রিসেট
docker-compose down && docker-compose up -d

# লগ দেখুন
docker-compose logs -f --tail=100
```

### উচ্চ CPU ব্যবহার
```bash
# সবচেয়ে বেশি CPU ব্যবহার করছে কি
docker stats --no-stream

# ওয়ার্কার প্রসেস পরীক্ষা করুন
docker-compose logs worker | tail -50

# কাজের সংখ্যা দেখুন
docker-compose exec redis redis-cli LLEN celery

# সব কাজ সাফ করুন (সতর্ক!)
docker-compose exec redis redis-cli FLUSHDB
```

### মেমরি পূর্ণ
```bash
# মেমরি ব্যবহার
docker stats --no-stream

# বড় প্রক্রিয়া খুঁজুন
docker ps --no-trunc -a

# ওয়ার্কার রিসাইক্লিং জোর করুন
docker-compose restart worker

# ডাটাবেস মেমরি ফ্রি করুন
docker-compose exec postgres psql -U mininguser -d miningdb \
  -c "VACUUM FULL; REINDEX DATABASE miningdb;"
```

### ডাটাবেস পূর্ণ
```bash
# ডাটাবেস আকার
docker-compose exec postgres psql -U mininguser -d miningdb \
  -c "SELECT pg_size_pretty(pg_database_size('miningdb'));"

# বড় টেবিল খুঁজুন
docker-compose exec postgres psql -U mininguser -d miningdb -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) 
   FROM pg_tables ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC LIMIT 10;"

# স্বয়ংক্রিয় পরিষ্কার করুন
docker-compose exec postgres psql -U mininguser -d miningdb -c "VACUUM FULL;"
```

---

## 📈 পারফরম্যান্স টেস্টিং

### ব্যাকএন্ড লোড টেস্ট
```bash
# হেলথ চেক গতি
time curl http://localhost:5000/health

# সমান্তরাল অনুরোধ (10 একসাথে)
for i in {1..10}; do curl http://localhost:5000/health & done; wait

# API স্ট্রেস টেস্ট (ApacheBench প্রয়োজন)
ab -n 1000 -c 50 http://localhost:5000/health
```

---

## 📝 নিয়মিত রক্ষণাবেক্ষণ সূচী

### দৈনিক
- লগ পরীক্ষা করুন
- সেবা স্ট্যাটাস যাচাই করুন
- সংস্থান ব্যবহার চেক করুন

### সাপ্তাহিক
- ডাটাবেস ব্যাকআপ
- ডাটাবেস ভ্যাকুয়াম
- পুরানো লগ পরিষ্কার করুন

### মাসিক
- ডিস্ক স্থান অপ্টিমাইজ করুন
- সিকিউরিটি প্যাচ আপডেট করুন
- পূর্ণ সিস্টেম ব্যাকআপ
