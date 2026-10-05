import time

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from core.logging_config import get_logger

log = get_logger("ai_hr.web.DispatcherServlet")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs method, path, status, and duration for every HTTP request similar to Spring MVC."""

    async def dispatch(self, request: Request, call_next):
        start = time.perf_counter()
        path = request.url.path
        method = request.method
        client = request.client.host if request.client else "-"

        # Filter out spammy health check keep-alives unless at DEBUG level
        is_keepalive = path in ("/", "/health")
        if not is_keepalive:
            log.info("Incoming HTTP request: %s \"%s\" from client=%s", method, path, client)

        try:
            response = await call_next(request)
        except Exception as ex:
            duration_ms = (time.perf_counter() - start) * 1000
            log.error(
                "Request processing failed: %s \"%s\" from %s in %.2f ms | error=%s",
                method,
                path,
                client,
                duration_ms,
                ex,
                exc_info=True,
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        status = response.status_code
        if is_keepalive:
            log.debug("Keep-alive ping %s -> %s in %.2f ms", path, status, duration_ms)
        else:
            log.info(
                "Completed %s \"%s\" -> status=%s in %.2f ms",
                method,
                path,
                status,
                duration_ms,
            )
        return response

