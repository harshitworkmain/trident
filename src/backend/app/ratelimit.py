"""Per-client token buckets for public and auth endpoints.

In-process: each API replica limits independently. That is acceptable for abuse protection on
the public SOS form; move the buckets to Redis if strict global limits are ever needed.
"""

from __future__ import annotations

import threading
import time
from typing import Dict, Tuple

from fastapi import Request

from .errors import RateLimited


class TokenBucket:
    def __init__(self, per_minute: int, burst: int | None = None):
        self.rate = per_minute / 60.0
        self.capacity = float(burst or per_minute)
        self.state: Dict[str, Tuple[float, float]] = {}
        self.lock = threading.Lock()

    def take(self, key: str) -> float:
        """Consume one token; returns 0 if allowed, else seconds until a token is available."""
        now = time.monotonic()
        with self.lock:
            tokens, last = self.state.get(key, (self.capacity, now))
            tokens = min(self.capacity, tokens + (now - last) * self.rate)
            if tokens >= 1:
                self.state[key] = (tokens - 1, now)
                if len(self.state) > 50_000:                    # bound memory under a flood
                    self.state.clear()
                return 0.0
            self.state[key] = (tokens, now)
            return (1 - tokens) / self.rate


def client_key(request: Request) -> str:
    # behind a proxy, set it to overwrite X-Forwarded-For; uvicorn --proxy-headers then fills client.host
    return request.client.host if request.client else 'unknown'


def limit(bucket: TokenBucket, request: Request, scope: str) -> None:
    wait = bucket.take(f'{scope}:{client_key(request)}')
    if wait:
        raise RateLimited('Too many requests, try again shortly', {'retry_after_s': round(wait, 1)},
                          headers={'Retry-After': str(max(1, int(wait + 0.5)))})
