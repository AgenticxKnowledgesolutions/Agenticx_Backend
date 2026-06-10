import logging
from datetime import datetime, timezone
from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

# Set up audit logger
logger = logging.getLogger("audit_logger")
logger.setLevel(logging.INFO)

# Ensure audit logs are printed to console (useful on Render)
if not logger.handlers:
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    formatter = logging.Formatter('%(message)s') # Just output raw formatted msg
    ch.setFormatter(formatter)
    logger.addHandler(ch)


def get_ip_address(request: Request) -> str:
    """
    Get client IP address, trusting X-Forwarded-For if present for reverse proxies (Render).
    """
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For can be a list: "client, proxy1, proxy2..."
        # The leftmost IP is the original client IP.
        client_ip = x_forwarded_for.split(",")[0].strip()
        if client_ip:
            return client_ip

    if request.client:
        return request.client.host

    return "127.0.0.1"


# Initialize the Limiter. By default, it will use in-memory storage (MemoryStorage).
# This is Redis-ready since we can swap in a storage_uri (e.g., redis://...) anytime.
limiter = Limiter(key_func=get_ip_address)


async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """
    Custom handler for rate limit violations.
    Logs the event to audit logger and returns a standard HTTP 429 response.
    """
    ip = get_ip_address(request)
    endpoint = request.url.path
    timestamp = datetime.now(timezone.utc).isoformat()

    event_type = "RATE_LIMITED"

    # Structured audit logging
    # Format: timestamp ip endpoint event_type
    logger.warning(f"{timestamp} {ip} {endpoint} {event_type}")

    return JSONResponse(
        status_code=429,
        content={"detail": "Too many submissions. Please try again later."}
    )
