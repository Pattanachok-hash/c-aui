"""DSC Portal — auth + permissions backend.

Hosts:
  /api/auth/*    — signup, /me, change-password
  /api/admin/*   — pending approvals, approve/reject, manage user access
"""
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from config import settings
from routers import auth, admin

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="DSC Portal API", version="1.0.0")

# CORS — allow all c-aui.com subdomains (regex match)
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=settings.CORS_ALLOW_ORIGIN_REGEX,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router,  prefix="/api/auth",  tags=["auth"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


@app.get("/")
def root():
    return {"service": "DSC Portal API", "status": "ok"}


@app.get("/healthz")
def healthz():
    return {"status": "ok"}
