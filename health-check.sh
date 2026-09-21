#!/bin/bash
# System Health Check & Monitoring Script
# সিস্টেম স্বাস্থ্য পরীক্ষা স্ক্রিপ্ট

set -e

echo "╔════════════════════════════════════════════════════════════════╗"
echo "║         MINING APP - SYSTEM HEALTH CHECK                       ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to check status
check_status() {
    local service=$1
    local command=$2
    
    echo -n "Checking $service... "
    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ OK${NC}"
        return 0
    else
        echo -e "${RED}✗ FAILED${NC}"
        return 1
    fi
}

# 1. Docker Services
echo -e "${YELLOW}1. DOCKER SERVICES${NC}"
echo "─────────────────────────────────────────────────────────────────"

docker-compose ps
echo ""

# 2. Backend API
echo -e "${YELLOW}2. BACKEND API${NC}"
echo "─────────────────────────────────────────────────────────────────"
check_status "Backend Health" "curl -sf http://localhost:5000/health > /dev/null"

# 3. Database
echo -e "${YELLOW}3. DATABASE${NC}"
echo "─────────────────────────────────────────────────────────────────"
check_status "PostgreSQL" "docker-compose exec -T postgres pg_isready -U mininguser -d miningdb"

echo -n "User count: "
docker-compose exec -T postgres psql -U mininguser -d miningdb -c \
    "SELECT count(*) FROM users;" -t | tail -1

echo -n "Database connections: "
docker-compose exec -T postgres psql -U mininguser -d miningdb -c \
    "SELECT count(*) FROM pg_stat_activity;" -t | tail -1

# 4. Redis
echo -e "${YELLOW}4. REDIS${NC}"
echo "─────────────────────────────────────────────────────────────────"
check_status "Redis" "docker-compose exec -T redis redis-cli PING"

echo -n "Redis memory usage: "
docker-compose exec -T redis redis-cli INFO memory | grep used_memory_human | cut -d: -f2

echo -n "Redis keys: "
docker-compose exec -T redis redis-cli DBSIZE | tail -1

# 5. Workers
echo -e "${YELLOW}5. CELERY WORKERS${NC}"
echo "─────────────────────────────────────────────────────────────────"

docker-compose logs worker --tail=5 | grep -i "ready\|accepted\|error" || echo "No recent messages"

# 6. Nginx
echo -e "${YELLOW}6. NGINX REVERSE PROXY${NC}"
echo "─────────────────────────────────────────────────────────────────"
check_status "Nginx" "curl -sf http://localhost:80/health > /dev/null"

# 7. Resource Usage
echo -e "${YELLOW}7. RESOURCE USAGE${NC}"
echo "─────────────────────────────────────────────────────────────────"
echo "Container Resource Usage:"
docker-compose stats --no-stream 2>/dev/null || echo "Stats not available"

# 8. Recent Errors
echo -e "${YELLOW}8. RECENT ERRORS (Last 10)${NC}"
echo "─────────────────────────────────────────────────────────────────"
docker-compose logs backend --tail=20 | grep -i "error\|exception" | tail -10 || echo "No errors found"

# 9. API Response Time
echo -e "${YELLOW}9. API PERFORMANCE${NC}"
echo "─────────────────────────────────────────────────────────────────"
echo "Testing API response time (5 samples):"
for i in {1..5}; do
    response_time=$(curl -w "%{time_total}" -o /dev/null -s http://localhost:5000/health)
    echo "  Request $i: ${response_time}s"
done

# Summary
echo ""
echo "╔════════════════════════════════════════════════════════════════╗"
echo "║                     HEALTH CHECK COMPLETE                      ║"
echo "╚════════════════════════════════════════════════════════════════╝"
echo ""
echo "Next steps:"
echo "1. If any service failed, check logs: docker-compose logs <service>"
echo "2. Restart services if needed: docker-compose restart"
echo "3. Check resource limits in docker-compose.yml"
echo "4. Monitor real-time: docker-compose logs -f backend"
