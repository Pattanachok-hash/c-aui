# DSC Portal (`c-aui.com`) — Project Context

## Overview
ระบบ portal กลางสำหรับ login + จัดการสิทธิ์ของ user ที่จะใช้ apps ในกลุ่ม DSC CTC:
- Warehouse (`warehouse.c-aui.com`) — สแกนสินค้า
- Transport (`transport.c-aui.com`) — ติดตามขนส่ง
- Shipping Co. (`shipco.c-aui.com`) — booking & local charges

Portal เป็นจุดเดียวที่ user ใช้:
- สมัครใหม่ (รอ portal developer อนุมัติทาง email)
- Login → SSO ไปทุก app ที่ได้รับสิทธิ์
- เปลี่ยน password / ลืม password
- Portal developer: list/approve/reject pending signups + จัดการ per-app permissions

## Architecture (Option B — bootstrap phase)
```
c-aui.com        → Frontend static (GitHub Pages)
api.c-aui.com    → Backend FastAPI (Railway)
```
Backend ใช้ **Supabase project เดียวกันกับ warehouse-scanner** เป็น auth store + permission table
(ตัดสินใจ: ใช้ project เดิมก่อน เพื่อไม่ migrate users ครั้งใหญ่ — เป็น tech debt ที่ยอมรับจน scale คุ้ม Pro $25/mo)

## Tech Stack
- **Backend**: FastAPI (Python 3.11), `supabase-py`, `httpx`, `pydantic`, `resend`
- **Frontend**: Vanilla HTML/CSS/JS — เน้นเบาและ deploy ง่าย (GitHub Pages)
- **Auth**: Supabase Auth (ES256 JWT — verify ผ่าน `/auth/v1/user` endpoint)
- **Email**: Resend (`noreply@c-aui.com`, verified domain)
- **Hosting**: Railway (backend) + GitHub Pages (frontend)

## Folder Structure
```
c-aui/
├── AGENTS.md                  ← this file
├── CNAME                      (GitHub Pages domain)
├── Dockerfile                 (Railway backend image)
├── railway.toml
├── .dockerignore              (exclude frontend from backend image)
├── .gitignore                 (excludes backend/.env)
├── index.html                 ← auth-aware portal (filters cards by access)
├── login.html
├── signup.html
├── change-password.html
├── forgot-password.html
├── reset-password.html
├── admin/
│   └── approvals.html         ← list pending + approve/reject + assign apps
├── css/
│   └── portal.css             ← design system (DHL red, glassmorphism, animations)
├── js/
│   ├── auth.js                ← Supabase SDK wrapper
│   ├── api.js                 ← Backend fetch wrapper (auto-refresh on 401)
│   └── utils.js               ← toast, alert, topbar, escapeHtml, formatDateTime
└── backend/
    ├── main.py                ← FastAPI app + CORS
    ├── config.py              ← env settings (pydantic-settings)
    ├── dependencies.py        ← get_current_user / require_developer
    ├── requirements.txt
    ├── .env.example
    ├── routers/
    │   ├── auth.py            ← signup, /me, change-password, forgot, reset
    │   └── admin.py           ← pending-approvals, approve, reject, users, access
    └── services/
        ├── supabase_client.py ← service-role client + db_execute() retry
        └── email_service.py   ← Resend templates (signup notify, approval, reset, reject)
```

## Database Tables (อยู่ใน Supabase warehouse-scanner project)

### `user_app_access` — per-app permissions
| col | type | note |
|-----|------|------|
| user_id | UUID (FK auth.users) | PK part 1 |
| app | TEXT | PK part 2 — 'warehouse' / 'transport' / 'shipco' |
| role | TEXT | 'admin' or 'operator' |
| granted_at | TIMESTAMPTZ | |
| granted_by | UUID | who granted (portal developer user_id) |

### `pending_approvals` — signup queue
| col | type | note |
|-----|------|------|
| id | UUID PK | |
| email | TEXT UNIQUE | |
| user_id | UUID (FK auth.users CASCADE) | |
| status | TEXT | 'pending' / 'approved' / 'rejected' |
| requested_at | TIMESTAMPTZ | |
| decided_at | TIMESTAMPTZ | |
| decided_by | UUID | portal developer user_id |
| note | TEXT | reason for rejection (optional) |

### `password_reset_tokens` — custom reset flow (we don't use Supabase's built-in)
| col | type | note |
|-----|------|------|
| token | TEXT PK | 256-bit `secrets.token_urlsafe(32)` |
| user_id | UUID (FK auth.users CASCADE) | |
| email | TEXT | |
| created_at | TIMESTAMPTZ | |
| expires_at | TIMESTAMPTZ | now() + 1 hour |
| used_at | TIMESTAMPTZ | NULL = unused |

## Key Conventions

### Bootstrap portal developer
- Developer email = `settings.DEVELOPER_EMAIL` (currently `pattanachok_msn@hotmail.com`)
- On signup, if email matches DEVELOPER_EMAIL → auto-approve + grant app-admin access on ALL apps (no ban, no queue)
- Anyone else: ban 1 year + add to pending_approvals + email portal developer

### JWT verification
- Supabase now signs with **ES256** (asymmetric) — we **don't decode locally** with HS256 secret
- Backend calls `GET /auth/v1/user` with the user's bearer token to verify
- See `dependencies.py:get_current_user`

### Cross-origin (CORS)
- Backend allows any `*.c-aui.com` subdomain + `localhost:<port>` during dev
- Pattern: `^(http://localhost:\d+|https?://(.*\.)?c-aui\.com)$`

### Email best-effort
- All email sends are wrapped in `try/except` and never fail the parent request
- A scan / approval / signup succeeds even if Resend goes down

### "Developer" vs "Admin" definition
- **Portal developer** = email matches `DEVELOPER_EMAIL` config or Supabase Auth `app_metadata.portal_role = 'developer'` — can approve/reject signups + manage permissions
- **App admin** = `user_app_access.role = 'admin'` for that specific app — used by each app's own backend (warehouse-scanner, etc.)

## API Endpoints (`api.c-aui.com/api/*`)

### Public
| Method | Path | Purpose |
|--------|------|---------|
| POST | `/auth/signup` | สมัครใหม่ — ban + email portal developer (auto-approve ถ้าเป็น DEVELOPER_EMAIL) |
| POST | `/auth/forgot-password` | gen token + email reset link (never reveals if email exists) |
| POST | `/auth/reset-password` | validate token + update password |

### Authenticated (JWT bearer)
| Method | Path | Purpose |
|--------|------|---------|
| GET  | `/auth/me` | user info + `apps` list (from user_app_access) |
| POST | `/auth/change-password` | verify current + update (no admin needed) |

### Portal developer only (`email == DEVELOPER_EMAIL`)
| Method | Path | Purpose |
|--------|------|---------|
| GET   | `/admin/pending-approvals` | list pending signups |
| POST  | `/admin/approve-user/{id}` | unban + grant `apps` array + email user |
| POST  | `/admin/reject-user/{id}` | delete auth user + email user |
| GET   | `/admin/users` | list approved users + their `apps` |
| PATCH | `/admin/users/{id}/access` | replace user's access set |
| PATCH | `/admin/users/{id}/portal-role` | promote/demote portal developer access |

## Environment Variables
ดูตัวอย่างใน `backend/.env.example`
- `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`
- `RESEND_API_KEY`, `EMAIL_FROM` (default `noreply@c-aui.com`)
- `DEVELOPER_EMAIL` (default `pattanachok_msn@hotmail.com`)
- `PORTAL_FRONTEND_URL` (default `https://c-aui.com`)
- `CORS_ALLOW_ORIGIN_REGEX` (default allows c-aui.com + localhost)

## Local Development
```bash
# Backend
cd backend
cp .env.example .env  # fill in real values
pip install -r requirements.txt
uvicorn main:app --reload --port 8000

# Frontend (separate terminal, from repo root)
python -m http.server 5500

# Open http://localhost:5500/login.html
```

Frontend's `js/api.js` auto-detects localhost and points to `http://localhost:8000`.

## Cross-subdomain Auth (planned)
Currently: each subdomain keeps its own localStorage session.
Plan: share via cookie on `.c-aui.com` (parent domain) so login at portal → all subdomains logged in automatically.

## Known Decisions / Tech Debt
- **Auth in warehouse project**: ใช้ shared project ก่อน — migrate ไป dedicated auth project เมื่อ scale คุ้ม Pro plan ($25/mo)
- **Frontend on GitHub Pages**: free + CDN. ถ้าจะใช้ Server-Side Rendering ภายหลัง ต้องเปลี่ยน
- **No backend for login**: login ทำ client-side ผ่าน Supabase SDK โดยตรง — backend แค่ตรวจ JWT ผ่าน /auth/v1/user
- **Forgot password custom (not Supabase built-in)**: เลือก custom เพื่อ branded email + consistent UX กับ signup notification
- **Root portal developer**: `DEVELOPER_EMAIL` กันไว้เป็น owner ที่ลบ/demote ไม่ได้; portal developer คนอื่นเก็บที่ Supabase Auth `app_metadata.portal_role`

## ก่อนแก้ไขอะไรให้ขอ approve จากผู้ใช้ก่อนทุกครั้ง
