"""Portal user-management endpoints (portal developer only).

Only the portal developer email in settings.DEVELOPER_EMAIL can use these endpoints.
"""
import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Literal

from dependencies import require_developer
from config import settings
from services.supabase_client import supabase, db_execute
from services.email_service import send_approval_notification, send_rejection_notification

logger = logging.getLogger(__name__)
router = APIRouter()


# ── Schemas ──────────────────────────────────────────────────────────────────

AppName = Literal["warehouse", "transport", "shipco"]
RoleName = Literal["admin", "operator"]


class AppGrant(BaseModel):
    app: AppName
    role: RoleName


class ApproveRequest(BaseModel):
    apps: list[AppGrant]  # list of (app, role) pairs to grant


class RejectRequest(BaseModel):
    note: str | None = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/pending-approvals")
def list_pending(developer: dict = Depends(require_developer)):
    """List signup requests that are still pending."""
    res = db_execute(
        supabase.table("pending_approvals")
        .select("id, email, user_id, status, requested_at, decided_at, decided_by, note")
        .eq("status", "pending")
        .order("requested_at", desc=True)
    )
    return res.data or []


@router.get("/users")
def list_users(developer: dict = Depends(require_developer)):
    """List users managed by the portal + their per-app access.

    Source of truth for access is user_app_access. pending_approvals only
    contains users who signed up through this portal, so migrated/legacy users
    must be included from user_app_access too.
    """
    approved = db_execute(
        supabase.table("pending_approvals")
        .select("email, user_id, status, decided_at")
        .eq("status", "approved")
        .order("decided_at", desc=True)
    ).data or []

    access = db_execute(
        supabase.table("user_app_access")
        .select("user_id, app, role")
    ).data or []

    by_user: dict[str, list[dict]] = {}
    for a in access:
        by_user.setdefault(a["user_id"], []).append({"app": a["app"], "role": a["role"]})

    approved_by_user = {r["user_id"]: r for r in approved if r.get("user_id")}
    user_ids = set(by_user.keys()) | set(approved_by_user.keys())

    users = []
    for user_id in user_ids:
        approved_row = approved_by_user.get(user_id) or {}
        email = approved_row.get("email")

        if not email:
            try:
                auth_res = supabase.auth.admin.get_user_by_id(user_id)
                auth_user = getattr(auth_res, "user", auth_res)
                email = getattr(auth_user, "email", None)
                if not email and isinstance(auth_user, dict):
                    email = auth_user.get("email")
            except Exception:
                logger.exception("get_user_by_id failed for %s", user_id)

        users.append({
            "user_id": user_id,
            "email": email or user_id,
            "apps": by_user.get(user_id, []),
            "decided_at": approved_row.get("decided_at"),
        })

    return sorted(
        users,
        key=lambda u: (u.get("decided_at") or "", (u.get("email") or "").lower()),
        reverse=True,
    )


@router.post("/approve-user/{pending_id}")
async def approve_user(pending_id: str, body: ApproveRequest, developer: dict = Depends(require_developer)):
    """Unban user, grant requested apps + roles, email user, mark approved."""
    if not body.apps:
        raise HTTPException(400, "ต้องระบุอย่างน้อย 1 app + role")

    # 1) Load pending row
    row = db_execute(
        supabase.table("pending_approvals")
        .select("*")
        .eq("id", pending_id)
        .maybe_single()
    ).data
    if not row:
        raise HTTPException(404, "ไม่พบ pending approval นี้")
    if row["status"] != "pending":
        raise HTTPException(400, f"คำขอนี้ถูกตัดสินแล้ว (status={row['status']})")

    user_id = row["user_id"]
    email = row["email"]

    # 2) Unban the auth user
    try:
        supabase.auth.admin.update_user_by_id(user_id, {"ban_duration": "none"})
    except Exception:
        logger.exception("Failed to unban user")
        raise HTTPException(500, "Unban ผู้ใช้ไม่สำเร็จ")

    # 3) Grant per-app access (idempotent upsert)
    try:
        rows = [
            {"user_id": user_id, "app": g.app, "role": g.role, "granted_by": developer.get("sub")}
            for g in body.apps
        ]
        db_execute(
            supabase.table("user_app_access").upsert(rows, on_conflict="user_id,app"),
            idempotent=False,
        )
    except Exception:
        logger.exception("Failed to grant user_app_access")
        raise HTTPException(500, "บันทึกสิทธิ์ไม่สำเร็จ")

    # 4) Mark pending row approved
    try:
        from datetime import datetime, timezone
        db_execute(
            supabase.table("pending_approvals").update({
                "status": "approved",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "decided_by": developer.get("sub"),
            }).eq("id", pending_id),
        )
    except Exception:
        logger.exception("Failed to mark approved")

    # 5) Notify user — best effort
    try:
        send_approval_notification(email, [{"app": g.app, "role": g.role} for g in body.apps])
    except Exception:
        logger.exception("send_approval_notification failed")

    return {"ok": True, "user_id": user_id, "email": email}


@router.post("/reject-user/{pending_id}")
async def reject_user(pending_id: str, body: RejectRequest, developer: dict = Depends(require_developer)):
    """Delete auth user, mark pending row rejected, email user."""
    row = db_execute(
        supabase.table("pending_approvals")
        .select("*")
        .eq("id", pending_id)
        .maybe_single()
    ).data
    if not row:
        raise HTTPException(404, "ไม่พบ pending approval นี้")
    if row["status"] != "pending":
        raise HTTPException(400, f"คำขอนี้ถูกตัดสินแล้ว (status={row['status']})")

    user_id = row["user_id"]
    email = row["email"]

    # 1) Delete auth user (cascades to user_app_access via FK ON DELETE CASCADE)
    try:
        supabase.auth.admin.delete_user(user_id)
    except Exception:
        logger.exception("delete_user failed (continuing)")

    # 2) Mark rejected
    try:
        from datetime import datetime, timezone
        db_execute(
            supabase.table("pending_approvals").update({
                "status": "rejected",
                "decided_at": datetime.now(timezone.utc).isoformat(),
                "decided_by": developer.get("sub"),
                "note": body.note,
            }).eq("id", pending_id),
        )
    except Exception:
        logger.exception("Failed to mark rejected")

    # 3) Notify user — best effort
    try:
        send_rejection_notification(email, body.note)
    except Exception:
        logger.exception("send_rejection_notification failed")

    return {"ok": True, "email": email}


class UpdateAccessRequest(BaseModel):
    apps: list[AppGrant]  # full replacement of user's app access


class DeleteUserRequest(BaseModel):
    email: str | None = None


def _auth_email(auth_res) -> str | None:
    auth_user = getattr(auth_res, "user", auth_res)
    email = getattr(auth_user, "email", None)
    if not email and isinstance(auth_user, dict):
        email = auth_user.get("email")
    return email.lower() if email else None


def _is_auth_not_found_error(e: Exception) -> bool:
    msg = str(e).lower()
    return (
        "not found" in msg
        or "404" in msg
        or "does not exist" in msg
        or "user not found" in msg
    )


@router.patch("/users/{user_id}/access")
def update_user_access(user_id: str, body: UpdateAccessRequest, developer: dict = Depends(require_developer)):
    """Replace a user's per-app access set (admin tweaks roles / grants new apps)."""
    # 1) Delete existing access rows
    db_execute(
        supabase.table("user_app_access").delete().eq("user_id", user_id),
    )

    # 2) Insert new set (if any)
    if body.apps:
        rows = [
            {"user_id": user_id, "app": g.app, "role": g.role, "granted_by": developer.get("sub")}
            for g in body.apps
        ]
        db_execute(
            supabase.table("user_app_access").insert(rows),
            idempotent=False,
        )

    return {"ok": True, "user_id": user_id, "apps": [g.model_dump() for g in body.apps]}


@router.delete("/users/{user_id}")
def delete_user(user_id: str, body: DeleteUserRequest | None = None, developer: dict = Depends(require_developer)):
    """Delete an auth user and portal records so the email can sign up again.

    Idempotent enough for legacy/stale rows: if Auth user is already gone, we
    still clean portal DB rows by user_id and by the provided email fallback.
    """
    fallback_email = (body.email or "").strip().lower() if body and body.email else None
    auth_email = None

    try:
        auth_email = _auth_email(supabase.auth.admin.get_user_by_id(user_id))
    except Exception as e:
        if _is_auth_not_found_error(e):
            logger.info("Auth user already missing before delete: %s", user_id)
        else:
            logger.exception("get_user_by_id failed before delete for %s", user_id)

    if auth_email == settings.DEVELOPER_EMAIL.lower() or fallback_email == settings.DEVELOPER_EMAIL.lower():
        raise HTTPException(400, "Cannot delete the portal developer account")

    email = auth_email or fallback_email
    auth_deleted = False
    auth_already_missing = False

    try:
        supabase.auth.admin.delete_user(user_id)
        auth_deleted = True
    except Exception as e:
        if _is_auth_not_found_error(e):
            auth_already_missing = True
            logger.info("Auth user already missing during delete: %s", user_id)
        else:
            logger.exception("delete_user failed for %s", user_id)
            raise HTTPException(500, "ลบผู้ใช้ไม่สำเร็จ")

    cleanup_errors: list[str] = []
    cleanup_results: dict[str, bool] = {}
    cleanup_queries: list[tuple[str, object]] = [
        ("user_app_access_by_user_id", supabase.table("user_app_access").delete().eq("user_id", user_id)),
        ("password_reset_tokens_by_user_id", supabase.table("password_reset_tokens").delete().eq("user_id", user_id)),
        ("pending_approvals_by_user_id", supabase.table("pending_approvals").delete().eq("user_id", user_id)),
    ]
    if email:
        cleanup_queries.extend([
            ("password_reset_tokens_by_email", supabase.table("password_reset_tokens").delete().eq("email", email)),
            ("pending_approvals_by_email", supabase.table("pending_approvals").delete().eq("email", email)),
        ])

    for name, query in cleanup_queries:
        try:
            db_execute(query)
            cleanup_results[name] = True
        except Exception:
            logger.exception("cleanup %s failed for %s", name, user_id)
            cleanup_errors.append(name)
            cleanup_results[name] = False

    if cleanup_errors:
        raise HTTPException(500, f"ลบผู้ใช้แล้ว แต่ cleanup ไม่ครบ: {', '.join(cleanup_errors)}")

    return {
        "ok": True,
        "user_id": user_id,
        "email": email,
        "auth_deleted": auth_deleted,
        "auth_already_missing": auth_already_missing,
        "cleanup": cleanup_results,
    }
