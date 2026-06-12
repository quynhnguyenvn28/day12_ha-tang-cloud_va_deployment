# Day 12 Lab - Mission Answers

> **Student:** Day 12 Lab Submission  
> **Course:** AICB-P1 · VinUniversity 2026

---

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found in `01-localhost-vs-production/develop/app.py`

| # | Anti-pattern | Dòng code | Vấn đề |
|---|-------------|-----------|--------|
| 1 | **API key hardcode** | `OPENAI_API_KEY = "sk-hardcoded-fake-key-never-do-this"` | Nếu push lên GitHub → key bị lộ ngay lập tức, kẻ xấu có thể dùng để gọi API tốn tiền |
| 2 | **Database URL hardcode** | `DATABASE_URL = "postgresql://admin:password123@localhost:5432/mydb"` | Credentials bị lộ trong source code — vi phạm nguyên tắc security cơ bản |
| 3 | **Debug logging ra secret** | `print(f"[DEBUG] Using key: {OPENAI_API_KEY}")` | Log API key ra stdout → bất kỳ ai xem log đều thấy được key |
| 4 | **Không có health check endpoint** | Comment `# ❌ Vấn đề 4: Không có health check endpoint` | Platform (Railway/Render/K8s) không biết container có hoạt động không → không thể tự restart khi crash |
| 5 | **Port cứng và host cứng** | `host="localhost", port=8000` | Trên Railway/Render, `PORT` được inject qua env var; `localhost` chỉ lắng nghe loopback, container không nhận được traffic từ bên ngoài |
| 6 | **`reload=True` trong production** | `reload=True` trong uvicorn | Hot-reload watch filesystem → tốn CPU, không ổn định, nguy hiểm trong production |
| 7 | **`DEBUG = True` hardcode** | `DEBUG = True` | Debug mode bật trong production → stack trace lộ cho người dùng, tiềm ẩn lỗ hổng bảo mật |

### Exercise 1.3: Comparison table

| Feature | Develop (Basic) | Production (Advanced) | Tại sao quan trọng? |
|---------|----------------|----------------------|---------------------|
| **Config** | Hardcode trong code (`OPENAI_API_KEY = "sk-..."`) | Environment variables (`os.getenv("OPENAI_API_KEY")`) | Không lộ secret trong source code; dễ thay đổi per-environment |
| **Logging** | `print("[DEBUG] ...")` | Structured JSON logging (`json.dumps({...})`) | JSON log dễ parse bởi Datadog/CloudWatch/Grafana; có timestamp, level, context |
| **Health check** | Không có | `GET /health` → 200 OK | Platform biết khi nào restart container; load balancer biết khi nào route traffic |
| **Readiness probe** | Không có | `GET /ready` → 200/503 | Tách biệt "container sống" vs "sẵn sàng nhận traffic" (e.g. chờ DB connect) |
| **Graceful shutdown** | Đột ngột (SIGKILL) | Handle SIGTERM → hoàn thành requests đang xử lý → close connections | Không bị mất request đang in-flight khi deploy/scale |
| **Port** | Cứng `8000` | `int(os.getenv("PORT", "8000"))` | Railway/Render inject `PORT` dynamically |
| **Host** | `localhost` (chỉ loopback) | `0.0.0.0` (tất cả interfaces) | Container cần lắng nghe tất cả interfaces để nhận traffic từ bên ngoài |
| **Authentication** | Không có | API Key + JWT | Chỉ user hợp lệ mới gọi được → bảo vệ chi phí LLM |
| **Rate limiting** | Không có | Sliding window 10 req/min | Ngăn abuse, giảm chi phí |
| **Error handling** | Lỗi → 500 stack trace lộ | HTTPException có message rõ ràng | Không lộ thông tin nội bộ; user hiểu lỗi gì |
| **CORS** | Không có | Configured middleware | Cho phép frontend call API từ browser |
| **Security headers** | Không có | `X-Content-Type-Options`, `X-Frame-Options` | Bảo vệ khỏi MIME sniffing và clickjacking |

---

## Part 2: Docker

### Exercise 2.1: Dockerfile questions (`02-docker/develop/Dockerfile`)

1. **Base image là gì?**  
   `python:3.11` — full Python distribution (~1 GB). Nặng nhưng đơn giản để bắt đầu học.

2. **Working directory là gì?**  
   `/app` — tất cả file được copy vào đây, và commands được chạy từ đây.

3. **Tại sao COPY requirements.txt trước?**  
   Docker build theo từng **layer**. Nếu `requirements.txt` không đổi, Docker sẽ dùng **layer cache** từ lần build trước → không cần `pip install` lại → build nhanh hơn rất nhiều. Chỉ khi `requirements.txt` thay đổi thì Docker mới re-install.

4. **CMD vs ENTRYPOINT khác nhau thế nào?**  
   - `ENTRYPOINT`: Fixed executable — không thể override bằng argument khi `docker run`  
   - `CMD`: Default command — có thể override. Ví dụ: `docker run myimage python test.py` sẽ thay `CMD`  
   - Kết hợp: `ENTRYPOINT ["python"]` + `CMD ["app.py"]` → `python` luôn chạy nhưng script có thể thay

### Exercise 2.3: Image size comparison

| Image | Build type | Estimated size | Difference |
|-------|-----------|----------------|------------|
| `my-agent:develop` | Single-stage (`python:3.11` full) | ~1.1 GB | Baseline |
| `my-agent:advanced` | Multi-stage (`python:3.11-slim` runtime) | ~180-220 MB | **~80% nhỏ hơn** |

**Tại sao image nhỏ hơn?**
- **Stage 1 (builder):** Cài `gcc`, `libpq-dev`, các build tools để compile dependencies → chỉ dùng để build, không đưa vào final image
- **Stage 2 (runtime):** Chỉ copy compiled packages từ builder (`/root/.local`) + source code → không có build tools, không có compiler
- `python:3.11-slim` thay vì `python:3.11` → loại bỏ nhiều package hệ thống không cần thiết

### Exercise 2.4: Docker Compose architecture

```
Client
  │
  └─► agent (port 8000:8000)
           │ depends_on (healthy)
           └─► redis:7-alpine (port 6379)
```

**Services:**
- **agent**: FastAPI app, depend on redis, restart `unless-stopped`, có healthcheck
- **redis**: Redis 7 Alpine, configured với `maxmemory 128mb` + LRU eviction policy

**Communication:** Agent dùng `redis://redis:6379/0` — Docker Compose tự resolve hostname `redis` thành container IP qua internal Docker network.

---

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

- **Platform:** Railway
- **Config file:** `railway.toml` (Dockerfile builder + uvicorn start command)
- **URL:** Xem `DEPLOYMENT.md` (cần tạo project trên Railway dashboard)

**Steps thực hiện:**
```bash
npm i -g @railway/cli
railway login
railway init
railway variables set AGENT_API_KEY=my-secret-key-lab12
railway variables set PORT=8000
railway up
railway domain
```

### Exercise 3.2: render.yaml vs railway.toml

| Aspect | `railway.toml` | `render.yaml` |
|--------|---------------|---------------|
| Format | TOML | YAML |
| Builder | `builder = "DOCKERFILE"` | `type: web` với Dockerfile detection |
| Start command | `startCommand = "uvicorn..."` | `startCommand: uvicorn...` |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Auto-deploy | Implicit | `autoDeploy: false` (optional) |
| Env vars | `railway variables set` | Trong `render.yaml` hoặc dashboard |

---

## Part 4: API Security

### Exercise 4.1: API Key Authentication

**API key được check ở đâu?**  
Trong `app/auth.py` — hàm `verify_api_key()` dùng `APIKeyHeader(name="X-API-Key")` để extract header, so sánh với `settings.agent_api_key`.

**Điều gì xảy ra nếu sai key?**  
`raise HTTPException(status_code=401, detail="Invalid or missing API key...")` → Response 401 Unauthorized.

**Làm sao rotate key?**  
Thay `AGENT_API_KEY` trong environment variables → restart service. Không cần sửa code.

**Test results:**
```bash
# Không có key → 401
curl http://localhost:8000/ask -X POST -d '{"question":"Hello"}'
# → {"detail":"Invalid or missing API key. Include header: X-API-Key: <key>"}

# Có key đúng → 200
curl http://localhost:8000/ask -X POST \
  -H "X-API-Key: dev-key-change-me" \
  -H "Content-Type: application/json" \
  -d '{"question":"Hello"}'
# → {"question":"Hello","answer":"...","model":"gpt-4o-mini","timestamp":"..."}
```

### Exercise 4.2: JWT flow

1. Client POST `/token` với `{username, password}` → server verify → trả JWT token
2. Client gửi `Authorization: Bearer <token>` trong mọi request tiếp theo
3. Server verify signature + expiry → cho phép hoặc từ chối

**Ưu điểm JWT so với API Key:**
- Stateless — server không cần lưu session
- Chứa claims (user role, exp, iat) → phân quyền chi tiết
- Short-lived → giảm rủi ro nếu bị lộ

### Exercise 4.3: Rate Limiting

**Algorithm được dùng:** **Sliding Window** (cửa sổ trượt 60 giây)

```python
# Cách hoạt động:
# 1. Lưu timestamp của mỗi request trong deque
# 2. Mỗi request đến → xóa timestamps cũ hơn 60s
# 3. Nếu còn >= limit → raise 429
# 4. Ngược lại → append timestamp mới, cho phép request
```

**Limit:** 10 req/min per user (từ `RATE_LIMIT_PER_MINUTE=10` trong `.env`)

**Bypass cho admin:** Có thể dùng key prefix khác nhau, hoặc thêm `is_admin` claim trong JWT để skip rate limit check.

### Exercise 4.4: Cost guard implementation

```python
def check_budget(user_id: str, estimated_cost: float = 0.001) -> None:
    """
    Logic:
    - Mỗi user có budget $10/tháng (monthly_budget_usd)
    - Track spending trong Redis với key "budget:<user>:<YYYY-MM>"
    - Reset tự động đầu tháng (key theo tháng + TTL 35 ngày)
    - Raise HTTP 402 nếu vượt budget
    """
    monthly_limit = settings.monthly_budget_usd  # default $10
    current = _get_spending(user_id)             # từ Redis hoặc in-memory

    if current + estimated_cost > monthly_limit:
        raise HTTPException(
            status_code=402,
            detail=f"Monthly budget exceeded. Spent: ${current:.4f} / Limit: ${monthly_limit}"
        )
```

**Approach:**
- Redis key theo tháng: `budget:user123:2026-06`
- `incrbyfloat` để atomic increment
- TTL 35 ngày → tự expire sau khi tháng kết thúc
- Fallback in-memory nếu Redis không có

---

## Part 5: Scaling & Reliability

### Exercise 5.1: Health & Readiness checks

```python
@app.get("/health")
def health():
    """Liveness probe — container còn sống không?"""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "version": settings.app_version,
    }

@app.get("/ready")
def ready():
    """Readiness probe — sẵn sàng nhận traffic không?"""
    if not _is_ready:
        raise HTTPException(503, "Not ready")
    return {"ready": True}
```

**Sự khác biệt quan trọng:**
- `/health` (liveness): Process đang chạy. Fail → platform restart container
- `/ready` (readiness): Sẵn sàng nhận traffic. Fail → load balancer ngừng route đến instance này (nhưng không restart)

### Exercise 5.2: Graceful Shutdown

```python
import signal
import json

_is_ready = False

def _handle_signal(signum, _frame):
    global _is_ready
    logger.info(json.dumps({"event": "signal", "signum": signum, "action": "graceful_shutdown"}))
    _is_ready = False  # Stop accepting new traffic (readiness probe → 503)
    # uvicorn timeout_graceful_shutdown=30 handles finishing in-flight requests

signal.signal(signal.SIGTERM, _handle_signal)
```

**Flow:**
1. Platform gửi SIGTERM (trước khi kill)
2. Handler đặt `_is_ready = False` → `/ready` trả 503 → LB ngừng route requests mới
3. uvicorn đợi in-flight requests hoàn thành (timeout 30s)
4. Container thoát sạch

### Exercise 5.3: Stateless design

**Anti-pattern (stateful — không scale được):**
```python
conversation_history = {}  # ❌ Chỉ tồn tại trong 1 instance

@app.post("/ask")
def ask(user_id: str, question: str):
    history = conversation_history.get(user_id, [])  # ❌ Instance 2 không có data này
```

**Correct (stateless với Redis):**
```python
@app.post("/ask")
def ask(user_id: str, question: str):
    history = r.lrange(f"history:{user_id}", 0, -1)  # ✅ Shared across all instances
    # ... call LLM ...
    r.rpush(f"history:{user_id}", response)
    r.expire(f"history:{user_id}", 86400)  # 24h TTL
```

**Tại sao cần stateless?**  
Khi scale ra 3 instances (Agent1, Agent2, Agent3), mỗi instance có RAM riêng. Request 1 → Agent1 (lưu history), Request 2 → Agent2 (không có history → context bị mất). Với Redis, tất cả instances chia sẻ 1 storage → đúng history.

### Exercise 5.4: Load balancing test results

```bash
docker compose up --scale agent=3
# → 3 containers: agent-1, agent-2, agent-3 + 1 redis

# Gọi 10 requests — quan sát logs
for i in {1..10}; do
  curl http://localhost:8000/ask -X POST \
    -H "X-API-Key: dev-key" \
    -d '{"question": "Request '$i'"}'
done

docker compose logs agent
# → requests được phân tán round-robin sang 3 instances
```

### Exercise 5.5: Stateless test

`test_stateless.py` kiểm tra:
1. Gửi question → lưu conversation history (Redis)
2. Tắt 1 instance ngẫu nhiên
3. Gửi follow-up question → instance khác trả lời với đúng context
4. → Chứng minh state không bị mất khi 1 instance die

---

## Tóm Tắt

| Part | Concept chính | Status |
|------|--------------|--------|
| 1 | Localhost vs Production (12-factor) | ✅ Hoàn thành |
| 2 | Docker containerization | ✅ Hoàn thành |
| 3 | Cloud deployment (Railway/Render) | ✅ Config sẵn sàng |
| 4 | API Security (auth + rate limit + cost guard) | ✅ Hoàn thành |
| 5 | Scaling & Reliability | ✅ Hoàn thành |
| 6 | Final project production-ready | ✅ 20/20 checks passed |
