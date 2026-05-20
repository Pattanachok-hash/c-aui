# DSC Portal (`c-aui.com`) — Project Context

## HANDOVER UPDATE — 2026-05-19

This section is the latest working-state handover. Read it before the older context below.

### Current direction

Chosen architecture remains split:
- `c-aui.com` = static frontend on GitHub Pages
- `api.c-aui.com` = FastAPI backend on Railway

Do not merge frontend/backend into one Railway service unless the user explicitly changes this decision.

### Local runtime notes

The user's machine has a real Python install that already has the backend deps:

```powershell
C:\Users\Pattanachok\AppData\Local\Programs\Python\Python314\python.exe
```

Use this Python. Do not create `.venv` / `venv` unless the user explicitly asks. Earlier attempts to create venvs wasted time and were removed.

Local run commands:

```powershell
# Backend
cd C:\Users\Pattanachok\DHL\c-aui\backend
& 'C:\Users\Pattanachok\AppData\Local\Programs\Python\Python314\python.exe' -m uvicorn main:app --host 127.0.0.1 --port 8000

# Frontend
cd C:\Users\Pattanachok\DHL\c-aui
& 'C:\Users\Pattanachok\AppData\Local\Programs\Python\Python314\python.exe' -m http.server 5500 --bind 127.0.0.1
```

Open with `http://localhost:5500/...`, not `127.0.0.1`, because local CORS allows `localhost`.

### Work completed in this session

Portal developer UI:
- Rebuilt `admin/approvals.html` to include two tabs:
  - `Pending Approvals`
  - `Approved Users`
- `Approved Users` now loads `GET /api/admin/users`.
- Added `Edit Access` modal for existing users.
- Edit modal supports full replacement of app access:
  - `warehouse`
  - `transport`
  - `shipco`
  - app role: `operator` or `admin`
- Save calls `PATCH /api/admin/users/{user_id}/access`.
- Added approved-user search box.
  - Searches email, user_id, app key, app label, and role.
  - Design was adjusted after user feedback: glass toolbar, search icon, clear button.
- Added `Delete` button for approved users.
  - Uses confirm prompt.
  - Sends `DELETE /api/admin/users/{user_id}` with body `{ email }`.

Backend portal developer:
- Changed `GET /api/admin/users`.
  - It now uses `user_app_access` as the main source of truth.
  - It also merges approved users from `pending_approvals`.
  - This fixed the issue where only 2 users appeared even though legacy users existed.
  - For legacy users, it fetches email from Supabase Auth via `get_user_by_id`.
- Added `DELETE /api/admin/users/{user_id}`.
  - Deletes Supabase Auth user.
  - Cleans portal records so the email can sign up again.
  - Cleans by `user_id` and by email where possible:
    - `user_app_access`
    - `pending_approvals`
    - `password_reset_tokens`
  - Blocks deleting `DEVELOPER_EMAIL`.
  - Made more idempotent:
    - if Auth user is already missing, it still cleans stale DB rows.
    - frontend now sends email fallback in DELETE body.

Signup/email validation:
- Existing warehouse users include internal emails like `name@wh.local`.
- `EmailStr` rejected `.local`, so backend email validation was changed.
- `backend/routers/auth.py` now:
  - accepts `@wh.local` only when matching a strict internal pattern:
    - `^[a-z0-9._%+-]+@wh\.local$`
  - still validates normal public emails through `email-validator`.
- `signup.html` and `forgot-password.html` now use `isValidPortalEmail()`.
- `js/utils.js` now includes `isValidPortalEmail()`.
- `js/api.js` now formats FastAPI validation errors instead of showing `[object Object]`.

Deployment housekeeping:
- Fixed duplicate `</head>` in `index.html`.
- Added `.claude/` to `.gitignore`.
- Hardened `.dockerignore`:
  - `.claude/`
  - `backend/.env`
  - `.venv/`
  - `venv/`
- Aligned default CORS in `backend/config.py` with `.env` / `.env.example`:

```python
r"^(http://localhost:\d+|https?://(.*\.)?c-aui\.com)$"
```

### Verification done

Recent checks performed:
- `backend/routers/admin.py` compiled successfully after admin changes.
- `backend/routers/auth.py` compiled successfully after email validation changes.
- `backend/config.py` compiled successfully after CORS default change.
- Frontend pages returned HTTP 200 locally:
  - `http://localhost:5500/admin/approvals.html`
  - `http://localhost:5500/signup.html`
  - `http://localhost:5500/forgot-password.html`
  - `http://localhost:5500/index.html`
- Backend health returned HTTP 200:
  - `http://localhost:8000/healthz`
- Test signup with `test@wh.local` and password `password1` returned success and created pending signup.

### Important behavior notes

- Browser cache caused one confusing signup case where success UI did not appear immediately even though signup succeeded. Hard refresh fixed it.
- During local tests, use `localhost`, not `127.0.0.1`, because CORS local regex is `localhost`.
- `api.c-aui.com` is backend only. It is not meant to render user-facing pages.
- `warehouse-scanner` differs from this portal architecture:
  - `warehouse.c-aui.com` serves frontend and `/api` from one Railway app.
  - `c-aui` remains split (`c-aui.com` + `api.c-aui.com`).

### Current git/worktree state

Many project files are still untracked because this portal was newly built locally. At last check:
- tracked modified: `index.html`
- untracked project files include:
  - `.dockerignore`
  - `.gitignore`
  - `AGENTS.md`
  - `CLAUDE.md`
  - `Dockerfile`
  - `admin/`
  - `backend/`
  - `css/`
  - `js/`
  - auth pages such as `login.html`, `signup.html`, etc.
- `.claude/` no longer appears in `git status` after ignore update.
- `backend/.env` exists locally and must never be committed.

Before commit, inspect staged files carefully.

### Recommended next steps

1. Do one full local smoke test:
   - signup with `@wh.local`
   - approve user
   - login as that user
   - confirm visible app cards match access
   - edit access promote/demote
   - delete user
   - confirm same email can sign up again
   - forgot/reset password
2. Review diff and confirm no secrets.
3. Stage only intended project files.
4. Commit.
5. Push to GitHub.
6. Deploy backend to Railway.
7. Set Railway env vars.
8. Configure DNS `api.c-aui.com`.
9. Confirm production frontend on GitHub Pages calls `https://api.c-aui.com`.

### Still not done

- Production deploy not done.
- DNS `api.c-aui.com` not configured.
- Cross-subdomain SSO not done.
- Transport and shipco/booking apps are not integrated with portal login yet.
- Warehouse integration still needs review; especially ensure users without `app='warehouse'` are rejected rather than silently treated as operator.
- Portal developer action audit log is not implemented yet.
- Delete confirmation is still browser `confirm`; future production hardening could use a modal requiring email confirmation.

### User preferences / caution

- User is sensitive to unnecessary setup. Do not create environments or install packages unless explicitly approved.
- Before editing anything, ask/confirm approval if the request is not already an explicit instruction to edit.
- Keep changes narrow. The user prefers making the current portal real before expanding scope to SSO or per-app admin/operator enforcement.

## 🎯 Project Status (เห็นก่อนทำอะไร)

**Phase:** in active development — backend + frontend สร้างเสร็จ, **ยังไม่ deploy production**

| Component | Status |
|-----------|--------|
| Supabase tables (`user_app_access`, `pending_approvals`, `password_reset_tokens`) | ✅ Created in production DB |
| Backend code (`backend/`) | ✅ ทำเสร็จ, ทดสอบ local แล้ว |
| Frontend pages | ✅ ทำเสร็จ — login, signup, change-pw, forgot-pw, reset-pw, admin/approvals, index |
| Local dev environment | ✅ ทำงานครบ (signup → approve → login → reset password ผ่านหมด) |
| Git repo | ✅ มี local commits — **ยังไม่ push GitHub** |
| Railway backend deploy | ❌ ยังไม่ทำ |
| DNS `api.c-aui.com` | ❌ ยังไม่ตั้ง |
| Cross-subdomain SSO | ❌ **ยังไม่ทำ** — แต่ละ subdomain ยัง login แยก |
| Warehouse/Transport apps integrate กับ portal | ❌ ยังไม่ทำ — apps ปัจจุบันยัง login ตัวเอง |

## 🌍 ระบบใหญ่ (ไม่ใช่แค่ portal นี้)

มี 4 repos ที่เกี่ยวข้อง อยู่ใน `C:\Users\Pattanachok\DHL\`:
- **`c-aui/`** — portal นี้ (this repo)
- **`warehouse-scanner/`** — สแกนสินค้า, deploy ที่ `warehouse.c-aui.com` (Railway)
- **`transport-dashboard/`** — ติดตามขนส่ง, deploy ที่ `transport.c-aui.com` (Railway)
- **`shipping-something/`** — booking & SI, deploy ที่ `shipco.c-aui.com` (ยังไม่มี auth)

**ทุก app ใช้ Supabase project เดียวกันชื่อ "Warehouse Scanner"** (URL = `aprmihzsessyptzqgdvs.supabase.co`)

แต่ละ repo มี `CLAUDE.md` ของตัวเอง อ่าน sister repo's CLAUDE.md ถ้างานข้าม project

## Overview
Portal กลางสำหรับ login + จัดการสิทธิ์เข้าใช้ apps:
- สมัครใหม่ (รอ portal developer อนุมัติทาง email)
- Login → (ในอนาคต) SSO ไปทุก app ที่ได้รับสิทธิ์
- เปลี่ยน password / ลืม password
- Portal developer: list/approve/reject pending signups + จัดการ per-app permissions

## Architecture
```
c-aui.com           → Frontend static (GitHub Pages — planned)
api.c-aui.com       → Backend FastAPI (Railway — planned)
warehouse.c-aui.com → warehouse-scanner (existing, Railway)
transport.c-aui.com → transport-dashboard (existing, Railway)
shipco.c-aui.com    → shipping app (existing, no auth yet)
```

**Auth model (Option B — pragmatic):** Supabase project เดิม (warehouse) เป็น auth store
- เก็บ users ที่ `auth.users` (เดิม)
- เก็บ permissions ที่ `user_app_access` table (ใหม่)
- ⚠ Tech debt: เมื่อสเกล upgrade Pro แล้วย้ายไป dedicated auth project (~6-8 ชม. งาน)

## Tech Stack
- **Backend:** FastAPI 0.110, supabase-py, pyjwt, resend, pydantic-settings
- **Frontend:** Vanilla HTML/CSS/JS (no framework) — design = DHL red + glassmorphism + Plus Jakarta Sans
- **Auth:** Supabase Auth (**ES256 JWT** — must verify via `/auth/v1/user`, NOT decode locally with HS256 secret)
- **Email:** Resend จาก `noreply@c-aui.com` (verified domain)
- **Hosting:** Railway (backend) + GitHub Pages (frontend)

## Folder Structure
```
c-aui/
├── CLAUDE.md                  ← this file
├── CNAME                      (GitHub Pages domain → c-aui.com)
├── Dockerfile                 (Railway backend image — COPY backend/)
├── railway.toml
├── .dockerignore              (exclude frontend from backend image)
├── .gitignore                 (excludes backend/.env)
├── index.html                 ← auth-aware portal (filters cards by user_app_access)
├── login.html
├── signup.html
├── change-password.html
├── forgot-password.html
├── reset-password.html
├── admin/
│   └── approvals.html         ← admin list pending + approve/reject + assign apps
├── css/
│   └── portal.css             ← shared design system
├── js/
│   ├── auth.js                ← Supabase SDK wrapper (login/logout/getCurrentSession)
│   ├── api.js                 ← Backend fetch wrapper (auto-refresh on 401)
│   └── utils.js               ← toast, alert, topbar, escapeHtml, formatDateTime
└── backend/
    ├── main.py                ← FastAPI app + CORS
    ├── config.py              ← env settings (pydantic-settings)
    ├── dependencies.py        ← get_current_user / require_developer
    ├── requirements.txt
    ├── .env                   ← REAL credentials (gitignored)
    ├── .env.example
    ├── routers/
    │   ├── auth.py            ← /signup, /me, /change-password, /forgot-password, /reset-password
    │   └── admin.py           ← /pending-approvals, /approve-user, /reject-user, /users, /access
    └── services/
        ├── supabase_client.py ← service-role client + db_execute() retry
        └── email_service.py   ← Resend templates (signup notify, approval, reset, reject)
```

## Database Tables (in shared Supabase project)

### `user_app_access` — per-app permissions
- **Source of truth** สำหรับสิทธิ์ user เข้าใช้ apps
- PK: (user_id, app) — user เดียวมี role ต่างกันต่อ app ได้
- `app`: 'warehouse' / 'transport' / 'shipco'
- `role`: 'admin' / 'operator'

### `pending_approvals` — signup queue
- เก็บ user ที่สมัครรอ admin อนุมัติ
- `email` UNIQUE → ป้องกัน double-signup
- `status`: 'pending' / 'approved' / 'rejected'

### `password_reset_tokens` — custom reset flow
- เราไม่ใช้ Supabase's built-in (อยาก control email template + brand)
- `token` = 256-bit `secrets.token_urlsafe(32)`
- Expires 1 hour, single-use (mark `used_at`)

### Legacy: `user_roles` (ในตอน warehouse-scanner สร้าง)
- เดิม warehouse-scanner ใช้ ตอนนี้ถูก migrate ไป user_app_access แล้ว
- ยังไม่ลบ (จะลบหลัง stable)
- ดู `warehouse-scanner/supabase/migrations/007_*.sql`

## Auth Flow (Critical Knowledge)

### Login
1. Frontend (`login.html`) → `sb.auth.signInWithPassword(email, password)` ผ่าน Supabase SDK
2. Supabase return JWT (ES256 signed)
3. SDK เก็บใน localStorage (key = `sb-aprmihzsessyptzqgdvs-auth-token`)
4. Redirect ไป `/index.html`

### Backend authorization
- Backend `dependencies.py:get_current_user` — รับ Bearer JWT
- Verify ผ่าน `GET /auth/v1/user` ของ Supabase (ไม่ decode เอง!)
  ```
  GET https://<project>.supabase.co/auth/v1/user
  Authorization: Bearer <jwt>
  apikey: <anon_key>
  ```
- ถ้า 200 → ได้ user object → return claims dict

### Developer gate (`require_developer`)
- Portal developer = email matches `settings.DEVELOPER_EMAIL` or Supabase Auth `app_metadata.portal_role = 'developer'`
- ไม่ใช้ user_app_access สำหรับ portal developer เพราะ app role ต้องไม่ปนกับ portal-level role

### Signup
1. Frontend → POST `/api/auth/signup` พร้อม email + password
2. Backend ตรวจ pending_approvals
3. ถ้า email = `DEVELOPER_EMAIL` → **auto-approve** + grant app-admin access ทุก app
4. ถ้าไม่ใช่ → สร้าง user + ban 1 ปี + insert pending_approvals + email portal developer
5. Portal developer คลิก link ใน email → ไป `/admin/approvals.html?email=xxx`
6. Portal developer เลือก apps + roles → กดอนุมัติ
7. Backend `/admin/approve-user/{id}`: unban + upsert user_app_access + email user

### Forgot password (custom — ไม่ใช่ Supabase built-in)
1. User → POST `/api/auth/forgot-password` พร้อม email
2. Backend gen token (`secrets.token_urlsafe(32)`) → save `password_reset_tokens`
3. ส่ง email พร้อม link `https://c-aui.com/reset-password.html?token=xxx`
4. User คลิก → reset-password.html รับ `?token=xxx`
5. กรอก password ใหม่ → POST `/api/auth/reset-password`
6. Backend validate token + update password via admin API

## API Endpoints (`api.c-aui.com/api/*`)

### Public
- POST `/auth/signup` — สมัครใหม่ (ban + email portal developer, auto-approve developer email)
- POST `/auth/forgot-password` — gen token + email reset link (never reveals if email exists)
- POST `/auth/reset-password` — validate token + update password

### Authenticated (JWT bearer)
- GET `/auth/me` — user info + `apps` list (from user_app_access)
- POST `/auth/change-password` — verify current + update (Supabase admin API)

### Portal developer only (`email == DEVELOPER_EMAIL`)
- GET `/admin/pending-approvals` — list pending signups
- POST `/admin/approve-user/{id}` — unban + grant `apps` array + email user
- POST `/admin/reject-user/{id}` — delete auth user + email user
- GET `/admin/users` — list approved users + their `apps`
- PATCH `/admin/users/{id}/access` — replace user's access set
- PATCH `/admin/users/{id}/portal-role` — promote/demote portal developer access

## Environment Variables

### Backend (`backend/.env`)
ดูตัวอย่างใน `backend/.env.example`. Values อยู่ใน Supabase Dashboard → Project Settings → API:
- `SUPABASE_URL` — `https://aprmihzsessyptzqgdvs.supabase.co`
- `SUPABASE_ANON_KEY` — anon public key
- `SUPABASE_SERVICE_ROLE_KEY` — service_role secret (BYPASSES RLS!)
- `SUPABASE_JWT_SECRET` — Legacy JWT Secret (ใช้สำรอง แม้ตอนนี้ verify ผ่าน /auth/v1/user)
- `RESEND_API_KEY` — เริ่มจาก `re_...` (existing key from warehouse-scanner Onboarding)
- `EMAIL_FROM` = `noreply@c-aui.com`
- `DEVELOPER_EMAIL` = `pattanachok_msn@hotmail.com` (portal developer)
- `PORTAL_FRONTEND_URL` = `https://c-aui.com` หรือ `http://localhost:5500` (dev)
- `CORS_ALLOW_ORIGIN_REGEX` = `^(http://localhost:\d+|https?://(.*\.)?c-aui\.com)$`

### Frontend
- Supabase URL/anon key เขียน hardcode ใน `js/auth.js` (ปลอดภัยเพราะ anon key + RLS)

## Local Development

```bash
# Terminal 1 — Backend (port 8000)
cd /c/Users/Pattanachok/DHL/c-aui/backend
# Make sure .env is filled in (.env.example has the template)
uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend static (port 5500)
cd /c/Users/Pattanachok/DHL/c-aui
python -m http.server 5500

# Open in browser:
#   http://localhost:5500/login.html
#   http://localhost:5500/signup.html
#   http://localhost:5500/admin/approvals.html (login as portal developer first)
```

`js/api.js` auto-detects localhost and points to `http://localhost:8000`. Override via `?api=http://other:port` query string.

## How to add a new app to the portal

1. Add app name to `CHECK` constraint of `user_app_access.app` (currently 'warehouse', 'transport', 'shipco')
2. Add card to `index.html` with `data-app="newname"`
3. Add to `admin/approvals.html` modal — `data-app="newname"` row + role select
4. Add to `backend/routers/admin.py` `AppName = Literal["warehouse", "transport", "shipco"]`

## Known Decisions / Tech Debt

- **Auth in warehouse project (not dedicated)**: pragmatic choice — saves $25/mo Pro plan. Migrate when ready.
- **Frontend on GitHub Pages**: free CDN. ถ้าจะ SSR ภายหลังต้องเปลี่ยน.
- **No backend for login**: login = client-side via Supabase SDK. Backend แค่ตรวจ JWT.
- **Forgot password custom**: เพื่อ branded email matching signup notification.
- **Root portal developer**: `DEVELOPER_EMAIL` is the owner account and cannot be deleted/demoted. Other portal developers are stored in Supabase Auth `app_metadata.portal_role`.
- **Cross-subdomain SSO ยังไม่ทำ**: ปัจจุบันแต่ละ subdomain มี localStorage แยก → user ต้อง login ต่อ subdomain
  - **Plan A:** cookie storage adapter บน `.c-aui.com` parent domain (ทำให้ SDK เก็บ session ที่ใช้ได้ข้าม subdomain)
  - **Plan B:** URL fragment relay (portal redirect ไปพร้อม `#access_token=...`)

## Common Pitfalls (อ่านก่อนทำ)

1. **Don't decode JWT locally** — Supabase ใช้ ES256 (asymmetric). Always verify via `/auth/v1/user`.
2. **`supabase-py` service role bypasses RLS** — ระวังตอนเขียน RLS policies คิดว่าใช้กับ backend (มันไม่ใช้)
3. **Email sends ห้าม fail request** — wrap try/except, log warning, return success ต่อ user
4. **CORS regex includes localhost** — backend allow localhost dev ด้วย, อย่าลืม
5. **Token expiry**: Supabase JWT default 1 hour. SDK auto-refresh — `api.js` retry once on 401
6. **`auth.users.email`** — UNIQUE in Supabase. Re-signup ด้วย email เดิม = 409 conflict

## Related Projects' Context

- **warehouse-scanner**: ใช้ `user_app_access` (warehouse app). อ่าน `warehouse-scanner/CLAUDE.md` ก่อนแก้
- **transport-dashboard**: ตอนนี้ใช้ data ของตัวเองใน `orders_for_transport` table (แยกจาก warehouse)

## เกี่ยวกับการทำงาน
- **ก่อนแก้ไขอะไร ขอ approve จาก user ก่อนทุกครั้ง**
- **Test local ก่อน push** — backend + static server วิ่งใน 2 terminal
- **Push แล้วต้อง deploy Railway** — auto-deploy on push to main (ต้องตั้ง service ก่อน)
