"""公网试用入口的基础鉴权、限流和安全响应头。"""

from __future__ import annotations

import base64
import os
import secrets
import threading
import time
from collections import defaultdict, deque

from fastapi import Request
from fastapi.responses import JSONResponse


def _enabled(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


class SlidingWindowLimiter:
    def __init__(self, window_seconds: int = 60):
        self.window_seconds = window_seconds
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def allow(self, key: str, limit: int, now: float | None = None) -> bool:
        current = time.monotonic() if now is None else now
        cutoff = current - self.window_seconds
        with self._lock:
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) >= limit:
                return False
            events.append(current)
            return True


_limiter = SlidingWindowLimiter()
_UNMETERED_PATHS = {"/api/health", "/api/local-model/status"}


def verify_basic_authorization(header: str, username: str, password: str) -> bool:
    if not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:].strip(), validate=True).decode("utf-8")
        supplied_user, supplied_password = decoded.split(":", 1)
    except (ValueError, UnicodeDecodeError):
        return False
    return secrets.compare_digest(supplied_user, username) and secrets.compare_digest(
        supplied_password, password
    )


def _client_key(request: Request) -> str:
    # Cloudflare 会写入真实访客 IP；未经过 Cloudflare 时再退回代理头和连接地址。
    forwarded = request.headers.get("cf-connecting-ip") or request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",", 1)[0].strip()
    return request.client.host if request.client else "unknown"


def _is_direct_loopback(request: Request) -> bool:
    """本机直连免登录；Cloudflare 请求即使落到回环地址也带有 cf-ray。"""
    client_host = request.client.host if request.client else ""
    request_host = (request.url.hostname or "").lower()
    return (
        not request.headers.get("cf-ray")
        and client_host in {"127.0.0.1", "::1"}
        and request_host in {"127.0.0.1", "localhost", "::1"}
    )


async def public_demo_guard(request: Request, call_next):
    if not _enabled(os.getenv("PUBLIC_DEMO_ENABLED", "false")):
        return await call_next(request)

    path = request.url.path
    if path not in _UNMETERED_PATHS and not _is_direct_loopback(request):
        username = os.getenv("PUBLIC_DEMO_USERNAME", "")
        password = os.getenv("PUBLIC_DEMO_PASSWORD", "")
        if not username or not password:
            return JSONResponse(
                {"detail": "公网试用鉴权尚未配置"},
                status_code=503,
                headers={"Cache-Control": "no-store"},
            )
        if not verify_basic_authorization(request.headers.get("authorization", ""), username, password):
            return JSONResponse(
                {"detail": "请输入试用账号和口令"},
                status_code=401,
                headers={
                    "WWW-Authenticate": 'Basic realm="Intelligent Operations Trial", charset="UTF-8"',
                    "Cache-Control": "no-store",
                },
            )

        try:
            limit = max(5, min(int(os.getenv("PUBLIC_DEMO_RATE_LIMIT", "30")), 300))
        except ValueError:
            limit = 30
        if path.startswith("/api/") and not _limiter.allow(_client_key(request), limit):
            return JSONResponse(
                {"detail": "请求过于频繁，请一分钟后再试"},
                status_code=429,
                headers={"Retry-After": "60", "Cache-Control": "no-store"},
            )

    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "same-origin")
    response.headers.setdefault("X-Frame-Options", "DENY")
    return response
