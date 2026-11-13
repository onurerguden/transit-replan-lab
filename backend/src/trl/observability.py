"""Trace execution and model metadata without emitting notice or prompt text."""

from collections.abc import Awaitable, Callable
from functools import wraps

import structlog
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from trl.settings import get_settings

_provider: TracerProvider | None = None


def configure_observability() -> None:
    global _provider
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.PrintLoggerFactory(),
    )
    endpoint = get_settings().otel_endpoint
    if endpoint and _provider is None:
        provider = TracerProvider(
            resource=Resource.create(
                {
                    "service.name": "transit-replan-lab",
                }
            )
        )
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces"),
            )
        )
        _provider = provider


def tracer() -> trace.Tracer:
    if _provider is not None:
        return _provider.get_tracer("trl")
    return trace.get_tracer("trl")


def observe_async[**P, T](
    name: str,
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    def decorate(node: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(node)
        async def call(*args: P.args, **kwargs: P.kwargs) -> T:
            with tracer().start_as_current_span(f"graph.{name}"):
                return await node(*args, **kwargs)

        return call

    return decorate


def observe[**P, T](name: str) -> Callable[[Callable[P, T]], Callable[P, T]]:
    def decorate(node: Callable[P, T]) -> Callable[P, T]:
        @wraps(node)
        def call(*args: P.args, **kwargs: P.kwargs) -> T:
            with tracer().start_as_current_span(f"graph.{name}"):
                return node(*args, **kwargs)

        return call

    return decorate
