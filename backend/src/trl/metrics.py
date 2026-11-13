"""Prometheus metrics for requests, runs, model calls and searches."""

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

REGISTRY = CollectorRegistry()
REQUESTS = Counter(
    "trl_http_requests_total", "HTTP requests", ["method", "route", "status"], registry=REGISTRY
)
LATENCY = Histogram(
    "trl_http_request_seconds",
    "HTTP request latency",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
    registry=REGISTRY,
)
RUNS_SETTLED = Counter(
    "trl_runs_settled_total", "Run revisions by outcome", ["status"], registry=REGISTRY
)
MODEL_CALLS = Histogram(
    "trl_model_call_seconds",
    "Model call duration",
    ["backend"],
    buckets=(0.05, 0.25, 1, 2.5, 5, 10, 30, 120),
    registry=REGISTRY,
)
SEARCH_WORK = Histogram(
    "trl_search_work_units",
    "Deterministic work units per route search",
    buckets=(1e3, 1e4, 1e5, 5e5, 1e6, 2e6),
    registry=REGISTRY,
)
SEARCH_INCOMPLETE = Counter(
    "trl_search_incomplete_total", "Searches that exhausted their budget", registry=REGISTRY
)
FENCED = Counter("trl_fenced_writes_total", "Writes refused for a revoked lease", registry=REGISTRY)
STREAMS = Gauge("trl_event_streams", "Open event streams", registry=REGISTRY)
RATE_LIMITED = Counter(
    "trl_rate_limited_total", "Requests refused by the rate limit", registry=REGISTRY
)


def render() -> bytes:
    return generate_latest(REGISTRY)
