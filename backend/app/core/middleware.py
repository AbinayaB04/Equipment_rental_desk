"""Request correlation and structured request logging middleware."""

import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.api.access")

REQUEST_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_\-]{1,64}$")


def get_or_generate_request_id(raw_header: str | None) -> str:
    """Validate incoming request ID or generate a new UUID4.

    Accepts bounded strings (1-64 chars, alphanumeric, underscore, hyphen).
    Rejects missing, empty, or invalid values and substitutes a clean UUID4.
    """
    if raw_header:
        cleaned = raw_header.strip()
        if REQUEST_ID_PATTERN.match(cleaned):
            return cleaned
    return str(uuid.uuid4())


class RequestIdAndLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware attaching request IDs and logging structured request metrics."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = get_or_generate_request_id(request.headers.get("X-Request-ID"))
        request.state.request_id = request_id

        start_time = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"

        logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "client_ip": client_ip,
            },
        )

        try:
            response = await call_next(request)
        except Exception:
            elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "request_failed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "elapsed_ms": elapsed_ms,
                },
            )
            raise

        elapsed_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id
        logger.info(
            "request_completed",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "status_code": response.status_code,
                "elapsed_ms": elapsed_ms,
            },
        )
        return response
