"""
Cost Guard — Monthly budget protection per user (Day 12 Lab)

Tracks estimated LLM spending per user per month.
Falls back to in-memory storage when Redis is not available.

Budget rule: $10 / user / month (configurable via MONTHLY_BUDGET_USD).
Cost estimation: GPT-4o-mini pricing (~$0.00015/1K input, $0.0006/1K output).
"""
import time
import logging
from datetime import datetime

from fastapi import HTTPException

from app.config import settings

logger = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────
# Try Redis; fall back to in-memory dict
# ─────────────────────────────────────────────────────────
_redis_client = None

if settings.redis_url:
    try:
        import redis as redis_lib
        _redis_client = redis_lib.from_url(settings.redis_url, decode_responses=True)
        _redis_client.ping()
        logger.info("Cost guard: using Redis backend")
    except Exception as e:
        logger.warning(f"Cost guard: Redis unavailable ({e}), falling back to in-memory")
        _redis_client = None

# In-memory fallback: { "budget:<user>:<YYYY-MM>" -> float }
_mem_store: dict[str, float] = {}

# Pricing constants (GPT-4o-mini)
INPUT_COST_PER_1K = 0.00015   # $ per 1K input tokens
OUTPUT_COST_PER_1K = 0.0006   # $ per 1K output tokens

# TTL for Redis keys (35 days — ensures reset after month boundary)
KEY_TTL_SECONDS = 35 * 24 * 3600


def _month_key(user_id: str) -> str:
    month = datetime.now().strftime("%Y-%m")
    return f"budget:{user_id}:{month}"


def _get_spending(user_id: str) -> float:
    key = _month_key(user_id)
    if _redis_client:
        val = _redis_client.get(key)
        return float(val) if val else 0.0
    return _mem_store.get(key, 0.0)


def _add_spending(user_id: str, amount: float) -> float:
    key = _month_key(user_id)
    if _redis_client:
        new_val = _redis_client.incrbyfloat(key, amount)
        _redis_client.expire(key, KEY_TTL_SECONDS)
        return float(new_val)
    current = _mem_store.get(key, 0.0)
    _mem_store[key] = current + amount
    return _mem_store[key]


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    """Estimate LLM cost in USD given token counts."""
    return (input_tokens / 1000) * INPUT_COST_PER_1K + \
           (output_tokens / 1000) * OUTPUT_COST_PER_1K


def check_budget(user_id: str, estimated_cost: float = 0.001) -> None:
    """
    Check whether user still has budget remaining for this month.

    Args:
        user_id: Unique user identifier.
        estimated_cost: Estimated cost of this request (USD).

    Raises:
        HTTPException 402 if monthly budget is exceeded.
    """
    monthly_limit = getattr(settings, "monthly_budget_usd", 10.0)
    current = _get_spending(user_id)

    if current + estimated_cost > monthly_limit:
        raise HTTPException(
            status_code=402,
            detail=(
                f"Monthly budget exceeded. "
                f"Spent: ${current:.4f} / Limit: ${monthly_limit:.2f}. "
                f"Budget resets on the 1st of next month."
            ),
        )


def record_cost(user_id: str, input_tokens: int, output_tokens: int) -> float:
    """
    Record actual cost after a successful LLM call.

    Returns:
        New total spending for this user this month.
    """
    cost = estimate_cost(input_tokens, output_tokens)
    new_total = _add_spending(user_id, cost)
    logger.debug(f"Cost recorded: user={user_id} cost=${cost:.6f} total=${new_total:.4f}")
    return new_total


def get_spending(user_id: str) -> dict:
    """Return spending info for a user (for /metrics or dashboard)."""
    monthly_limit = getattr(settings, "monthly_budget_usd", 10.0)
    current = _get_spending(user_id)
    return {
        "user_id": user_id,
        "month": datetime.now().strftime("%Y-%m"),
        "spent_usd": round(current, 4),
        "limit_usd": monthly_limit,
        "remaining_usd": round(max(0.0, monthly_limit - current), 4),
        "pct_used": round(current / monthly_limit * 100, 1),
    }
