import base64

from public_access import SlidingWindowLimiter, verify_basic_authorization


def _basic(username: str, password: str) -> str:
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return f"Basic {token}"


def test_basic_authorization():
    assert verify_basic_authorization(_basic("trial", "secret"), "trial", "secret")
    assert not verify_basic_authorization(_basic("trial", "wrong"), "trial", "secret")
    assert not verify_basic_authorization("Bearer token", "trial", "secret")


def test_sliding_window_limiter():
    limiter = SlidingWindowLimiter(window_seconds=60)
    assert limiter.allow("visitor", 2, now=10)
    assert limiter.allow("visitor", 2, now=20)
    assert not limiter.allow("visitor", 2, now=30)
    assert limiter.allow("visitor", 2, now=71)
