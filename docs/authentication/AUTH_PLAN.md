# AUTH PLAN — Email/Password (Sprint 4 / Week 7)

> **Mục tiêu:** đưa từ "anonymous user-by-UUID" hiện tại lên auth thực sự (email + password) với httpOnly cookie session, đồng thời chuẩn bị mặt đất cho Google OAuth ở sprint sau. PRD ràng buộc `US-N01`: *"không có bước đăng ký phức tạp (email + password là đủ)"*.

---

## 1. Hiện trạng (audit)

| Mảng | Trạng thái |
|---|---|
| Backend `User` model | có `email` (nullable, unique), **không có `password_hash`** |
| Backend `/api/v1/auth/*` | **không tồn tại** |
| Backend bảo vệ endpoint | không (mọi endpoint nhận `user_id` từ body/path, tin client) |
| Backend admin auth | `X-Admin-Token` header tĩnh (giữ nguyên) |
| Frontend `authStore` | persist `user` JSON vào `localStorage` (`a20.auth`) — không token |
| Frontend `ProtectedRoute` | "validate" bằng `GET /user/{user_id}` — biết UUID là vào được |
| Frontend `LoginPage` | **không tồn tại** |
| Frontend `OnboardingPage` | 3 bước: CEFR → industry → goals (không hỏi email/password) |
| CORS backend | `allow_origins=["*"]`, `allow_credentials` chưa bật → không cookie được |

---

## 2. Quyết định thiết kế (đã chốt với PO)

| Câu hỏi | Chốt |
|---|---|
| Auth method | **Email + password** (Google OAuth để Sprint sau) |
| Token transport | **httpOnly cookie** (`a20_session`, SameSite=Lax) |
| Token format | **JWT HS256** ký bằng `JWT_SECRET` (TTL 7 ngày, refresh = login lại) |
| Password hash | **bcrypt** (cost 12) |
| UX | **Gộp email/password vào step 1 OnboardingPage** (4 bước) + tách `LoginPage` cho user cũ |
| Demo user | giữ nguyên — luồng tách biệt, **không** có password, **không** set cookie session (FE biết là demo qua flag) |

> Hệ quả: `password_hash` là `NULLABLE` (demo user và user cũ migrate trước có thể null → các user này không login bằng password được, phải đặt password ở Settings hoặc tạo lại tài khoản — sẽ ghi chú trong release notes).

---

## 3. Thay đổi backend

### 3.1. Dependencies
- `requirements.txt`: thêm `bcrypt>=4.0.0`, `pyjwt>=2.8.0`.

### 3.2. Cấu hình (`core/config.py` + `.env.example`)
- `JWT_SECRET` (bắt buộc khác `change-me-in-prod` ở prod) — dùng cho HS256.
- `JWT_TTL_DAYS` (default 7).
- `COOKIE_SECURE` (default `False` cho dev, `True` cho prod/HTTPS).
- `FRONTEND_ORIGIN` (default `http://localhost:5173`) — dùng cho CORS allow_origins khi `allow_credentials=True`.

### 3.3. Migration
- `alembic/versions/0003_add_password_hash.py`: `ALTER TABLE user_profile ADD COLUMN password_hash VARCHAR(255) NULL`.

### 3.4. Files mới
- `app/core/security.py` — `hash_password`, `verify_password`, `create_session_token`, `decode_session_token`.
- `app/core/auth_dep.py` — FastAPI dependency `get_current_user(request, db) -> User` (đọc cookie `a20_session`, decode JWT, query DB, raise 401 nếu sai).
- `app/api/v1/auth.py`:
  - `POST /api/v1/auth/register` — body = email + password + cefr_level + industry + learning_goals + display_name. Tạo user, hash password, set cookie session, trả `MeResponse`.
  - `POST /api/v1/auth/login` — body = email + password. Verify, set cookie, trả `MeResponse`.
  - `POST /api/v1/auth/logout` — clear cookie, 204.
  - `GET /api/v1/auth/me` — depends `get_current_user`, trả profile.

### 3.5. Sửa file có
- `models/user.py` — thêm `password_hash = Column(String(255), nullable=True)`.
- `models/schemas.py` — thêm `RegisterRequest` (`OnboardingCreate` + `password: str ≥ 8 char`), `LoginRequest`, `MeResponse` (alias `UserOut`).
- `main.py`:
  - mount `auth.router`.
  - đổi CORS từ `allow_origins=["*"]` → `[settings.FRONTEND_ORIGIN]`, bật `allow_credentials=True`.

### 3.6. Endpoints không bị bảo vệ
Để giữ scope, **chỉ** `/auth/me` và (sau này) một số endpoint user-scoped sẽ dùng `get_current_user`. Phần còn lại (chat, review…) tiếp tục nhận `user_id` từ body như cũ — không nằm trong scope sprint này, đã ghi chú vào "follow-up".

---

## 4. Thay đổi frontend

### 4.1. `services/api.js`
- `axios.create({ withCredentials: true, ... })`.
- Thêm `tutorAPI.auth = { register, login, logout, me }`.
- Loại bỏ truyền `user_id` ở các call `auth.*`.

### 4.2. `stores/authStore.js`
- Bỏ `persist` middleware (cookie là source of truth).
- State: `user`, `status` (`idle | loading | authenticated | unauthenticated`).
- Actions: `setUser`, `clear`, `hydrate()` gọi `/auth/me` và set state.

### 4.3. `App.jsx`
- Bootstrap: `useEffect(() => authStore.hydrate(), [])`.
- `ProtectedRoute` dựa vào `status === 'authenticated'`.
- Thêm route `/login` → `LoginPage`.

### 4.4. Pages
- `pages/LoginPage.jsx` (mới) — form email + password, gọi `auth.login()`, redirect `/chat` nếu thành công.
- `pages/OnboardingPage.jsx` — thêm step 0 (email + password + confirm), submit cuối cùng đổi từ `/onboarding` sang `/auth/register`.
- `pages/HomePage.jsx` — thêm nút "Đăng nhập" cạnh nút "Bắt đầu 🚀" cho user chưa đăng nhập; "Đăng xuất" gọi `auth.logout()` thay vì chỉ clear store.

---

## 5. Kế hoạch test thật (chạy trước khi báo cáo)

```bash
cd src
docker compose up -d --build
docker compose exec backend alembic upgrade head
docker compose exec backend pytest -q   # đảm bảo regression sạch
```

Smoke test thủ công với `curl` (dùng `-c` / `-b` để giữ cookie):

```bash
# 1. Register
curl -i -c cookies.txt -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"Pa55word!","cefr_level":"B1","industry":"marketing","learning_goals":["business"]}'
# kỳ vọng: 201, Set-Cookie: a20_session=...; HttpOnly; SameSite=Lax

# 2. /auth/me với cookie
curl -i -b cookies.txt http://localhost:8000/api/v1/auth/me
# kỳ vọng: 200 + JSON user

# 3. /auth/me KHÔNG cookie
curl -i http://localhost:8000/api/v1/auth/me
# kỳ vọng: 401

# 4. Logout
curl -i -b cookies.txt -X POST http://localhost:8000/api/v1/auth/logout
# kỳ vọng: 204, Set-Cookie xoá

# 5. Login lại
curl -i -c cookies.txt -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"Pa55word!"}'

# 6. Sai password
curl -i -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"wrong"}'
# kỳ vọng: 401

# 7. Email trùng
curl -i -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"a@b.com","password":"Pa55word!","cefr_level":"B1","industry":"marketing","learning_goals":["business"]}'
# kỳ vọng: 409
```

Frontend test (browser):
- `/onboarding` → điền email/password/CEFR/industry/goals → submit → vào `/chat`, DevTools → Application → Cookies thấy `a20_session`.
- F5 trang `/chat` → vẫn vào được (không relogin).
- `/settings` → "Đăng xuất" → cookie biến mất → bị đẩy về `/`.
- Mở tab ẩn danh → `/chat` → bị redirect `/login`.

---

## 6. Biến môi trường cần PO cung cấp

| Biến | Khi nào cần |
|---|---|
| `JWT_SECRET` | **Bắt buộc** trước khi deploy prod. Dev có thể dùng default fixed string trong `.env`. Tôi sẽ đặt placeholder `change-me-jwt-secret` trong `.env.example`, và backend sẽ **fail fast** nếu giá trị này còn ở prod (sẽ thêm cảnh báo log). |
| `COOKIE_SECURE` | `False` cho dev (HTTP), `True` cho prod (HTTPS). |
| `FRONTEND_ORIGIN` | dev = `http://localhost:5173`, prod = URL Vercel/Railway. |
| `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` / `GOOGLE_REDIRECT_URI` | **không cần ngay** — Sprint sau. |

---

## 7. Out-of-scope (follow-up)

1. Áp `get_current_user` cho `/chat`, `/review/*`, `/analytics/*`, `/user/{id}` (hiện vẫn nhận `user_id` từ body — không impersonation-safe).
2. Refresh token rotation (hiện 1 cookie 7 ngày).
3. Reset password / email verification.
4. Rate limit riêng cho `/auth/login` (chống brute-force) — middleware `RateLimitMiddleware` hiện áp trên `user_id`, login chưa có user_id; cần per-IP.
5. ~~Google OAuth — đã reserve env var, sẽ thêm `/auth/google/start` và `/auth/google/callback` ở sprint sau.~~ **DONE in same sprint** — see §9.

---

## 9. Google OAuth (delivered)

### Flow chosen

User registered `http://localhost:5173` (SPA root) as the only Authorized
redirect URI in Google Cloud Console. The flow accommodates that:

1. SPA: `<a href="/api/v1/auth/google/start">` — full-page navigate (Vite proxies `/api/*` → backend in dev).
2. Backend `GET /auth/google/start`: generates random `state`, sets `a20_oauth_state` httpOnly cookie (TTL 10 min), 302 redirects to Google with `redirect_uri = settings.GOOGLE_REDIRECT_URI`, scope `openid email profile`.
3. User accepts on Google → Google redirects browser to `http://localhost:5173/?code=...&state=...`.
4. SPA `HomePage.jsx` `useEffect` detects `?code` & `?state`, strips the query string from history, then calls `POST /api/v1/auth/google/callback` with `{ code, state }`.
5. Backend verifies the `state` cookie (`secrets.compare_digest`), exchanges code via `https://oauth2.googleapis.com/token`, fetches profile via `https://openidconnect.googleapis.com/v1/userinfo`, finds-or-creates `User` (new users get `cefr_level="A2"`, `industry="general"`, `learning_goals=[]` as placeholders), sets `a20_session` cookie, deletes the one-shot state cookie, returns `UserOut`.
6. SPA receives the user, calls `setUser`, navigates to `/chat`.

### Files

- `app/api/v1/auth_google.py` (new)
- `app/core/config.py` — `GOOGLE_CLIENT_ID/SECRET/REDIRECT_URI`
- `app/main.py` — mount router
- `services/api.js` — `authAPI.googleStartUrl()` + `authAPI.googleCallback()`
- `pages/LoginPage.jsx`, `pages/OnboardingPage.jsx` — "Tiếp tục với Google" button
- `pages/HomePage.jsx` — OAuth callback `useEffect`

### Verified

- `GET /api/v1/auth/google/start` returns **302** to `accounts.google.com/o/oauth2/v2/auth` with `redirect_uri=http://localhost:5173`, scope `openid email profile`, random `state`, and `Set-Cookie: a20_oauth_state=...; HttpOnly; Max-Age=600`.
- `POST /api/v1/auth/google/callback` with mismatched state → **400 invalid oauth state**.
- Frontend `vite build` clean; new `LoginPage`, `OnboardingPage`, `HomePage` chunks emit.

### Known caveats / follow-up

- New Google users get placeholder `cefr_level=A2`, `industry=general`. They land on `/chat` directly. A "complete profile" step (Settings page able to edit CEFR/industry/learning_goals) is the next polish item.
- The state cookie uses `SameSite=Lax`, which is fine for top-level redirects from Google.
- Production checklist when going live: register the prod redirect URI on Google Cloud Console (e.g. `https://your-domain.com`), set `COOKIE_SECURE=true`, and put real `GOOGLE_CLIENT_SECRET` in the prod secret store (do not commit).

---

## 8. Status

- [x] Plan reviewed
- [x] Backend implemented (alembic 0003, `core/security.py`, `core/auth_dep.py`, `api/v1/auth.py`, CORS tightened, demo user issues cookie too)
- [x] Frontend implemented (`authStore` cookie-hydrated, `LoginPage`, 4-step onboarding with email/password, `App.jsx` ProtectedRoute via `/auth/me`, axios `withCredentials`)
- [x] Manual smoke (PowerShell `Invoke-WebRequest` against http://localhost:8000): 10/10 cases pass — register 201, /me 200/401, dup-register 409, logout 204 + cookie cleared, wrong-pw 401, login 200, weak-pw 422
- [x] `pytest tests/test_auth_security.py` — 5/5 pass
- [x] Existing pytest regression — 21 pass / 3 skipped / 2 fail (the 2 failures are pre-existing async test plumbing, unrelated)
- [x] Frontend `vite build` clean (LoginPage chunk emitted)
