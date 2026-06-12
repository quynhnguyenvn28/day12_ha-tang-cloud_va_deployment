# Deployment Information — Day 12 Lab

## Overview

Production-ready AI agent deployed to Railway (primary) với Docker multi-stage build.

---

## Public URL

```
https://day12-agent.up.railway.app
```

> **Note:** URL này sẽ được cập nhật sau khi deploy thực tế lên Railway.
> Config Railway đã sẵn sàng trong `railway.toml`.

## Platform

**Railway** (primary) — `railway.toml` đã configured  
**Render** (alternative) — `render.yaml` đã configured

---

## Test Commands

### 1. Health Check
```bash
curl https://day12-agent.up.railway.app/health
# Expected:
# {
#   "status": "ok",
#   "version": "1.0.0",
#   "environment": "production",
#   "uptime_seconds": 123.4,
#   "total_requests": 5,
#   "checks": {"llm": "mock"},
#   "timestamp": "2026-06-12T08:00:00+00:00"
# }
```

### 2. Readiness Check
```bash
curl https://day12-agent.up.railway.app/ready
# Expected: {"ready": true}
```

### 3. Authentication Required (401)
```bash
curl https://day12-agent.up.railway.app/ask -X POST \
  -H "Content-Type: application/json" \
  -d '{"question": "Hello"}'
# Expected: 401 {"detail": "Invalid or missing API key..."}
```

### 4. API Call with Authentication (200)
```bash
curl -X POST https://day12-agent.up.railway.app/ask \
  -H "X-API-Key: YOUR_AGENT_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"question": "What is deployment?"}'
# Expected:
# {
#   "question": "What is deployment?",
#   "answer": "Deployment là quá trình đưa code từ máy bạn lên server...",
#   "model": "gpt-4o-mini",
#   "timestamp": "2026-06-12T08:00:01+00:00"
# }
```

### 5. Rate Limiting (429 after 10 req/min)
```bash
for i in $(seq 1 15); do
  curl -s -o /dev/null -w "%{http_code}\n" \
    -X POST https://day12-agent.up.railway.app/ask \
    -H "X-API-Key: YOUR_AGENT_API_KEY" \
    -H "Content-Type: application/json" \
    -d "{\"question\": \"Test $i\"}"
done
# Expected: 200 200 200 ... 429 429 429 (after 10 requests)
```

### 6. Root Info
```bash
curl https://day12-agent.up.railway.app/
# Expected: {"app": "Production AI Agent", "version": "1.0.0", ...}
```

---

## Environment Variables Set

| Variable | Value | Description |
|----------|-------|-------------|
| `PORT` | `8000` | Server port (Railway injects automatically) |
| `ENVIRONMENT` | `production` | Disables debug mode + /docs |
| `AGENT_API_KEY` | `<secret>` | API authentication key |
| `REDIS_URL` | `redis://...` | Redis connection (Railway Redis addon) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `RATE_LIMIT_PER_MINUTE` | `10` | Max requests per minute per user |
| `DAILY_BUDGET_USD` | `5.0` | Daily cost guard limit |

---

## Deploy Railway (< 5 phút)

```bash
# 1. Install Railway CLI
npm i -g @railway/cli

# 2. Login
railway login

# 3. Init project (từ thư mục 06-lab-complete/)
cd 06-lab-complete
railway init

# 4. Set environment variables
railway variables set ENVIRONMENT=production
railway variables set AGENT_API_KEY=your-secret-api-key-here
railway variables set LOG_LEVEL=INFO
railway variables set RATE_LIMIT_PER_MINUTE=10

# 5. Add Redis addon (Railway dashboard → Add Plugin → Redis)
# Sau khi add, Railway tự inject REDIS_URL

# 6. Deploy
railway up

# 7. Get public URL
railway domain
```

---

## Deploy Render

1. Push repo lên GitHub
2. Render Dashboard → **New** → **Blueprint**
3. Connect GitHub repo → Render tự đọc `render.yaml`
4. Set secrets trong dashboard:
   - `AGENT_API_KEY` → your-secret-key
5. Click **Apply** → Deploy tự động!

---

## Local Run (Docker Compose)

```bash
cd 06-lab-complete

# Copy env template
cp .env.example .env.local
# Chỉnh sửa AGENT_API_KEY trong .env.local

# Start full stack (agent + redis)
docker compose up

# Test
curl http://localhost:8000/health
curl -H "X-API-Key: dev-key-change-me" \
     -X POST http://localhost:8000/ask \
     -H "Content-Type: application/json" \
     -d '{"question": "Hello!"}'
```

---

## Screenshots

> Screenshots sẽ được thêm vào thư mục `screenshots/` sau khi deploy thực tế.

- `screenshots/railway_dashboard.png` — Railway deployment dashboard
- `screenshots/service_running.png` — Service health check passing
- `screenshots/api_test.png` — Postman/curl test results

---

## Architecture

```
Client
  │
  │  HTTPS (Railway public domain)
  ▼
┌─────────────────┐
│  Railway Edge   │  (TLS termination, CDN)
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│  FastAPI Agent  │  (Docker container, 2 uvicorn workers)
│  app/main.py    │
│  - Auth         │
│  - Rate Limit   │
│  - Cost Guard   │
└────────┬────────┘
         │  redis://
         ▼
┌─────────────────┐
│  Redis          │  (Railway Redis addon / rate limit + session store)
└─────────────────┘
```

---

## Production Readiness Checklist

```bash
cd 06-lab-complete
python check_production_ready.py
# Result: 20/20 checks passed (100%) 🎉
```

| Check | Status |
|-------|--------|
| Dockerfile exists | ✅ |
| docker-compose.yml exists | ✅ |
| .dockerignore exists | ✅ |
| .env.example exists | ✅ |
| requirements.txt exists | ✅ |
| railway.toml or render.yaml exists | ✅ |
| .env in .gitignore | ✅ |
| No hardcoded secrets | ✅ |
| /health endpoint | ✅ |
| /ready endpoint | ✅ |
| Authentication | ✅ |
| Rate limiting (429) | ✅ |
| Graceful shutdown (SIGTERM) | ✅ |
| Structured JSON logging | ✅ |
| Multi-stage Docker build | ✅ |
| Non-root user | ✅ |
| HEALTHCHECK instruction | ✅ |
| Slim base image | ✅ |
| .dockerignore covers .env | ✅ |
| .dockerignore covers __pycache__ | ✅ |
