"""RFC 9457 problem details for every error the API returns."""

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry import trace
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from trl.storage import Conflict, NotFound

logger = structlog.get_logger(__name__)
MEDIA_TYPE = "application/problem+json"


class FieldError(BaseModel):
    field: str
    message: str


class Problem(BaseModel):
    type: str = "about:blank"
    title: str
    status: int
    detail: str
    instance: str | None = None
    trace_id: str | None = None
    errors: list[FieldError] | None = None


def problem(
    request: Request,
    status: int,
    title: str,
    detail: str,
    errors: list[FieldError] | None = None,
) -> JSONResponse:
    context = trace.get_current_span().get_span_context()
    body = Problem(
        title=title,
        status=status,
        detail=detail,
        instance=request.url.path,
        trace_id=f"{context.trace_id:032x}" if context.is_valid else None,
        errors=errors,
    )
    return JSONResponse(
        body.model_dump(exclude_none=True), status_code=status, media_type=MEDIA_TYPE
    )


def install(app: FastAPI) -> None:
    @app.exception_handler(NotFound)
    async def missing(request: Request, exc: NotFound) -> JSONResponse:
        return problem(request, 404, "Run not found", str(exc))

    @app.exception_handler(Conflict)
    async def conflict(request: Request, exc: Conflict) -> JSONResponse:
        return problem(request, 409, "Command conflict", str(exc))

    @app.exception_handler(RequestValidationError)
    async def invalid(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Report where and why, never the submitted value.
        errors = [
            FieldError(field=".".join(str(part) for part in item["loc"]), message=item["msg"])
            for item in exc.errors()
        ]
        return problem(
            request, 422, "Invalid request", "The request does not match the schema.", errors
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        titles = {404: "Not found", 405: "Method not allowed"}
        return problem(
            request, exc.status_code, titles.get(exc.status_code, "Request failed"), str(exc.detail)
        )

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception) -> JSONResponse:
        logger.error("unhandled_error", path=request.url.path, error=type(exc).__name__)
        return problem(
            request, 500, "Internal error", "The service could not complete the request."
        )
