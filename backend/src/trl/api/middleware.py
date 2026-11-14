"""Request metrics, a per-client rate limit and security headers."""

import time
from collections import defaultdict
from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request, Response

from trl import metrics
from trl.api.problems import problem

HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cross-Origin-Opener-Policy": "same-origin",
}


class TokenBucket:
    """Refill `rate` tokens per second up to `burst`, per client."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic) -> None:
        self.rate = per_minute / 60
        self.burst = max(1, per_minute // 4)
        self.clock = clock
        self.state: dict[str, tuple[float, float]] = defaultdict(
            lambda: (float(self.burst), clock())
        )

    def take(self, client: str) -> float | None:
        """Return None when allowed, or the seconds to wait."""
        now = self.clock()
        tokens, stamp = self.state[client]
        tokens = min(self.burst, tokens + (now - stamp) * self.rate)
        if tokens >= 1:
            self.state[client] = (tokens - 1, now)
            return None
        self.state[client] = (tokens, now)
        return (1 - tokens) / self.rate


def install(app: FastAPI, per_minute: int) -> None:
    bucket = TokenBucket(per_minute) if per_minute > 0 else None

    @app.middleware("http")
    async def wrap(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.perf_counter()
        if bucket and request.method == "POST":
            client = request.client.host if request.client else "unknown"
            wait = bucket.take(client)
            if wait is not None:
                metrics.RATE_LIMITED.inc()
                response = problem(request, 429, "Too many requests", "Slow down and retry.")
                response.headers["Retry-After"] = str(max(1, round(wait)))
                return response
        response = await call_next(request)
        route = getattr(request.scope.get("route"), "path", "unmatched")
        metrics.REQUESTS.labels(request.method, route, str(response.status_code)).inc()
        if route != "/v1/runs/{run_id}/events":
            metrics.LATENCY.labels(request.method, route).observe(time.perf_counter() - started)
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        return response
