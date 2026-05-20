"""Auth endpoints: signup, current-user info, change-password, password reset.

Login itself happens client-side via Supabase SDK — no backend call needed.
"""
import logging
import re
import secrets
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from email_validator import EmailNotValidError, validate_email

from dependencies import get_current_user
from services.supabase_client import supabase, db_execute
from services.email_service import send_signup_notification, send_password_reset
from config import settings

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

class SignupRequest(BaseModel):
    email: str
    password: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


# ── Helpers ──────────────────────────────────────────────────────────────────

def _validate_password(pw: str) -> str | None:
    """Return error message if password fails policy (Level B). None if OK."""
    if len(pw) < 8:
        return "Password ต้องมีอย่างน้อย 8 ตัวอักษร"
    if not re.search(r"\d", pw):
        return "Password ต้องมีตัวเลขอย่างน้อย 1 ตัว"
    return None


def _normalize_email(raw: str) -> str:
    email = (raw or "").strip().lower()
    if email.endswith("@wh.local"):
        if re.fullmatch(r"[a-z0-9._%+-]+@wh\.local", email):
            return email
        raise HTTPException(400, "กรุณากรอก email ให้ถูกต้อง")

    try:
        return validate_email(email, check_deliverability=False).normalized.lower()
    except EmailNotValidError:
        raise HTTPException(400, "กรุณากรอก email ให้ถูกต้อง")


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.post("/signup")
async def signup(body: SignupRequest):
    """Create a banned auth user + pending_approvals row, then email developer."""
    email = _normalize_email(body.email)

    pw_err = _validate_password(body.password)
    if pw_err:
        raise HTTPException(400, pw_err)

    # 1) Check email isn't already in pending_approvals (any status)
    existing = db_execute(
        supabase.table("pending_approvals")
        .select("status")
        .eq("email", email)
        .limit(1)
    )
    if existing.data:
        status = existing.data[0]["status"]
        if status == "pending":
            raise HTTPException(409, "Email นี้รอ admin อนุมัติอยู่แล้ว")
        if status == "approved":
            raise HTTPException(409, "Email นี้ได้รับอนุมัติแล้ว — กรุณา login")
        # status == 'rejected' → allow re-signup (will overwrite below)

    # 2) Bootstrap: the configured DEVELOPER_EMAIL auto-approves (no ban, no review queue).
    #    Anyone else gets a 1-year ban until the portal developer approves.
    is_developer_bootstrap = email == settings.DEVELOPER_EMAIL.lower()

    try:
        create_params = {
            "email": email,
            "password": body.password,
            "email_confirm": True,         # skip Supabase's email verification step
        }
        if not is_developer_bootstrap:
            create_params["ban_duration"] = "8760h"  # 1 year — cleared on approval
        created = supabase.auth.admin.create_user(create_params)
        user_id = created.user.id
    except Exception as e:
        msg = str(e)
        if "already" in msg.lower() or "exists" in msg.lower():
            raise HTTPException(409, "Email นี้ถูกใช้แล้ว")
        logger.exception("create_user failed")
        raise HTTPException(500, f"สร้างผู้ใช้ไม่สำเร็จ: {msg}")

    # If portal developer email — auto-approve + grant app-admin access to all apps.
    if is_developer_bootstrap:
        try:
            from datetime import datetime, timezone
            db_execute(
                supabase.table("pending_approvals").upsert(
                    {
                        "email": email,
                        "user_id": user_id,
                        "status": "approved",
                        "decided_at": datetime.now(timezone.utc).isoformat(),
                        "note": "Auto-approved (portal developer bootstrap)",
                    },
                    on_conflict="email",
                ),
                idempotent=False,
            )
            db_execute(
                supabase.table("user_app_access").upsert(
                    [
                        {"user_id": user_id, "app": "warehouse", "role": "admin"},
                        {"user_id": user_id, "app": "transport", "role": "admin"},
                        {"user_id": user_id, "app": "shipco",    "role": "admin"},
                    ],
                    on_conflict="user_id,app",
                ),
                idempotent=False,
            )
        except Exception:
            logger.exception("Portal developer bootstrap upserts failed (continuing)")
        return {"ok": True, "message": "Developer บัญชีถูกสร้างและเปิดใช้งานแล้ว"}

    # 3) Insert / upsert pending_approvals
    try:
        db_execute(
            supabase.table("pending_approvals").upsert(
                {
                    "email": email,
                    "user_id": user_id,
                    "status": "pending",
                    "decided_at": None,
                    "decided_by": None,
                    "note": None,
                },
                on_conflict="email",
            ),
            idempotent=False,
        )
    except Exception:
        # If the pending insert fails we should clean up the auth user we just made
        try:
            supabase.auth.admin.delete_user(user_id)
        except Exception:
            logger.exception("Cleanup delete_user failed")
        logger.exception("Insert pending_approvals failed")
        raise HTTPException(500, "บันทึก pending_approvals ไม่สำเร็จ")

    # 4) Notify portal developer via email — best effort (don't fail signup if email fails)
    try:
        send_signup_notification(email)
    except Exception:
        logger.exception("send_signup_notification failed")

    return {
        "ok": True,
        "message": "สมัครเรียบร้อย — รอ admin อนุมัติทาง email",
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    """Return the current user's email + their per-app access list."""
    user_id = user.get("sub")
    email = user.get("email")

    access = db_execute(
        supabase.table("user_app_access")
        .select("app, role, granted_at")
        .eq("user_id", user_id)
    ).data or []

    return {
        "user_id": user_id,
        "email": email,
        "is_developer_portal": (email or "").lower() == __import__("config").settings.DEVELOPER_EMAIL.lower(),
        "portal_role": "developer" if (email or "").lower() == __import__("config").settings.DEVELOPER_EMAIL.lower() else "user",
        "apps": access,
    }


@router.post("/change-password")
async def change_password(body: ChangePasswordRequest, user: dict = Depends(get_current_user)):
    """Verify current password then update via Supabase admin API."""
    pw_err = _validate_password(body.new_password)
    if pw_err:
        raise HTTPException(400, pw_err)

    email = user.get("email")
    user_id = user.get("sub")
    if not email or not user_id:
        raise HTTPException(401, "Invalid session")

    # 1) Verify current password by trying to sign in
    try:
        verify = supabase.auth.sign_in_with_password({
            "email": email,
            "password": body.current_password,
        })
        if not verify.session:
            raise HTTPException(400, "Password ปัจจุบันไม่ถูกต้อง")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(400, "Password ปัจจุบันไม่ถูกต้อง")

    # 2) Update password via admin API (preserves user's session token elsewhere)
    try:
        supabase.auth.admin.update_user_by_id(user_id, {"password": body.new_password})
    except Exception:
        logger.exception("update_user_by_id failed")
        raise HTTPException(500, "เปลี่ยน Password ไม่สำเร็จ")

    return {"ok": True, "message": "เปลี่ยน Password สำเร็จ"}


# ── Forgot / Reset password (custom, branded via Resend) ────────────────────

@router.post("/forgot-password")
async def forgot_password(body: ForgotPasswordRequest):
    """Issue a one-time reset token + email it.

    Always returns success — never reveals whether the email is registered
    (prevents user enumeration).
    """
    email = _normalize_email(body.email)

    # Look up the user by email via the admin API.
    user_id: str | None = None
    try:
        # supabase-py exposes admin.list_users — we filter client-side because
        # the per-email lookup isn't a direct endpoint.
        page = supabase.auth.admin.list_users()
        users = getattr(page, "users", None) or page  # supabase-py shape varies
        for u in users:
            u_email = (getattr(u, "email", None) or "").lower()
            if u_email == email:
                user_id = getattr(u, "id", None)
                break
    except Exception:
        logger.exception("list_users failed during forgot-password")
        # Fall through — we still return success to avoid leaking failure mode

    if user_id:
        # Issue a 256-bit random token, valid for 1 hour
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        try:
            db_execute(
                supabase.table("password_reset_tokens").insert({
                    "token":      token,
                    "user_id":    user_id,
                    "email":      email,
                    "expires_at": expires_at.isoformat(),
                }),
                idempotent=False,
            )
        except Exception:
            logger.exception("Failed to insert password_reset_tokens")
            # Still return success — don't reveal infra issues either
        else:
            try:
                send_password_reset(email, token)
            except Exception:
                logger.exception("send_password_reset failed")

    return {"ok": True, "message": "ถ้า email นี้ลงทะเบียนไว้ ระบบได้ส่งลิงก์รีเซ็ตให้แล้ว"}


@router.post("/reset-password")
async def reset_password(body: ResetPasswordRequest):
    """Validate token then update the user's password via admin API."""
    pw_err = _validate_password(body.new_password)
    if pw_err:
        raise HTTPException(400, pw_err)

    # 1) Load token row
    row = db_execute(
        supabase.table("password_reset_tokens")
        .select("*")
        .eq("token", body.token)
        .maybe_single()
    ).data
    if not row:
        raise HTTPException(400, "ลิงก์ไม่ถูกต้อง")
    if row.get("used_at"):
        raise HTTPException(400, "ลิงก์นี้ถูกใช้ไปแล้ว")

    expires_at = datetime.fromisoformat(row["expires_at"].replace("Z", "+00:00"))
    if expires_at < datetime.now(timezone.utc):
        raise HTTPException(400, "ลิงก์หมดอายุ — กรุณาขอใหม่")

    user_id = row["user_id"]

    # 2) Update password
    try:
        supabase.auth.admin.update_user_by_id(user_id, {"password": body.new_password})
    except Exception:
        logger.exception("update_user_by_id failed in reset-password")
        raise HTTPException(500, "บันทึก Password ไม่สำเร็จ")

    # 3) Mark token used (best effort)
    try:
        db_execute(
            supabase.table("password_reset_tokens")
            .update({"used_at": datetime.now(timezone.utc).isoformat()})
            .eq("token", body.token),
        )
    except Exception:
        logger.exception("Failed to mark token used")

    return {"ok": True, "message": "เปลี่ยน Password สำเร็จ"}
