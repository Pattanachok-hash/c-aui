"""DSC Portal — auth + permissions backend.

Hosts:
  /api/auth/*    — signup, /me, change-password
  /api/admin/*   — pending approvals, approve/reject, manage user access
"""
import logging
import re
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import Response

from config import settings
from routers import auth, admin

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="DSC Portal API", version="1.0.0")

_SAFE_CORS_ORIGIN_RE = re.compile(
    r"^(http://localhost:\d+|http://127\.0\.0\.1:\d+|https://([a-z0-9-]+\.)?c-aui\.com)$",
    re.IGNORECASE,
)


# CORS — allow all c-aui.com subdomains (regex match)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _is_allowed_cors_origin(origin: str) -> bool:
    if _SAFE_CORS_ORIGIN_RE.fullmatch(origin):
        return True
    try:
        return bool(re.fullmatch(settings.CORS_ALLOW_ORIGIN_REGEX, origin))
    except re.error:
        logging.warning("Invalid CORS_ALLOW_ORIGIN_REGEX: %s", settings.CORS_ALLOW_ORIGIN_REGEX)
        return False


@app.middleware("http")
async def explicit_cors_preflight(request, call_next):
    """Answer browser preflight directly so auth routes never reject OPTIONS."""
    origin = request.headers.get("origin", "")
    if request.method == "OPTIONS" and origin and _is_allowed_cors_origin(origin):
        requested_headers = request.headers.get("access-control-request-headers", "*")
        return Response(
            content="OK",
            status_code=200,
            headers={
                "Access-Control-Allow-Origin": origin,
                "Access-Control-Allow-Credentials": "true",
                "Access-Control-Allow-Methods": "DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT",
                "Access-Control-Allow-Headers": requested_headers,
                "Access-Control-Max-Age": "600",
                "Vary": "Origin",
            },
        )
    return await call_next(request)

app.include_router(auth.router,  prefix="/api/auth",  tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/")
def root():
    return {"service": "DSC Portal API", "status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
