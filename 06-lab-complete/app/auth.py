"""
Authentication module — API Key + JWT (Day 12 Lab)

Supports:
- API Key authentication via X-API-Key header
- JWT token generation and verification
"""
import time
import hmac
import hashlib
import base64
import json

from fastapi import HTTPException, Security
from fastapi.security.api_key import APIKeyHeader

from app.config import settings

# ─────────────────────────────────────────────────────────
# API Key Auth
# ─────────────────────────────────────────────────────────
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def verify_api_key(api_key: str = Security(api_key_header)) -> str:
    """
    Verify X-API-Key header against configured secret.
    Returns the api_key (used as user identifier) if valid.
    Raises 401 if missing or wrong.
    """
    if not api_key or api_key != settings.agent_api_key:
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key. Include header: X-API-Key: <key>",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key


# ─────────────────────────────────────────────────────────
# Simple JWT (no external library dependency beyond PyJWT)
# ─────────────────────────────────────────────────────────
def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _b64_decode(data: str) -> bytes:
    padding = 4 - len(data) % 4
    return base64.urlsafe_b64decode(data + "=" * padding)


def create_jwt_token(username: str, expires_in: int = 3600) -> str:
    """Create a simple HS256 JWT token."""
    header = _b64_encode(json.dumps({"alg": "HS256", "typ": "JWT"}).encode())
    payload = _b64_encode(json.dumps({
        "sub": username,
        "exp": int(time.time()) + expires_in,
        "iat": int(time.time()),
    }).encode())
    signing_input = f"{header}.{payload}".encode()
    signature = _b64_encode(
        hmac.new(settings.jwt_secret.encode(), signing_input, hashlib.sha256).digest()
    )
    return f"{header}.{payload}.{signature}"


def verify_jwt_token(token: str) -> dict:
    """Verify JWT and return payload. Raises 401 if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid structure")
        header_b64, payload_b64, signature_b64 = parts
        signing_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = _b64_encode(
            hmac.new(settings.jwt_secret.encode(), signing_input, hashlib.sha256).digest()
        )
        if not hmac.compare_digest(expected_sig, signature_b64):
            raise ValueError("Signature mismatch")
        payload = json.loads(_b64_decode(payload_b64))
        if payload.get("exp", 0) < int(time.time()):
            raise ValueError("Token expired")
        return payload
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")
