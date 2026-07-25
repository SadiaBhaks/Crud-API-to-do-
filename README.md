# Task API — with Auth

Sign up, log in, log out, and protected routes — backed by **Supabase
Auth** as the Identity Provider. Built for the FlyRank Internship Backend
Track (Assignment 4, continuing the same repo as A1–A3).

This project never stores a password and never hashes anything itself —
Supabase does that. This code only ever forwards credentials to Supabase
and verifies the JWTs it hands back.

## The trust triangle

```
1. Client signs up / logs in  ->  Supabase        (credentials go here)
2. Supabase returns a JWT     ->  Client           (the access token)
3. Client calls your API      ->  your server      (token in Authorization header)
4. Your server asks Supabase  ->  "is this real?"   (verified via auth.get_user)
```

Your server never sees a password and never signs anything itself — it
only ever asks Supabase "is this token real?" and opens or refuses the
door based on the answer.

## Setup

### 1. Create a free Supabase project
- Go to [supabase.com](https://supabase.com), sign up, create a new project (e.g. `Auth-Practice`). Takes a minute or two to provision.
- In your Supabase Dashboard: **Project Settings → API** → copy your **Project URL** and your **anon key** (the public key — never use the `service_role` key here, it bypasses all security).
- **Turn off email confirmation for this practice project:** **Authentication → Sign In / Providers → Email** → toggle "Confirm email" off. (In a real production app you'd leave this on — it's a genuine security feature. It's off here purely so a fresh signup can log in immediately during testing.)

### 2. Configure your environment
```bash
cp .env.example .env
```
Fill in `.env` with your real Supabase values:
```
SUPABASE_URL=your_project_url
SUPABASE_KEY=your_anon_key
PORT=8000
```
`.env` is git-ignored — it never gets committed. Only `.env.example` (with placeholder values) is tracked.

### 3. Run it
```bash
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

Then open:
- `http://localhost:8000/docs` — **Swagger UI**, with a lock icon on protected routes
- `http://localhost:8000/public/info` — open to anyone

## Endpoints

| Method | Path | Auth required? | Description |
|---|---|---|---|
| POST | `/auth/signup` | No | Create an account. `400` if email/password missing. |
| POST | `/auth/login` | No | Log in, returns `access_token` + `refresh_token`. `401` on bad credentials. |
| POST | `/auth/refresh` | No | Exchange a `refresh_token` for a new `access_token`. |
| POST | `/auth/logout` | **Yes** | Ends the session. `204` on success. |
| GET | `/public/info` | No | Open, unauthenticated data. |
| GET | `/protected/profile` | **Yes** | Returns the verified user's id/email/created_at. |
| GET | `/protected/dashboard` | **Yes** | A second protected route — reuses the exact same guard, no new auth code. |
| GET | `/protected/admin` | **Yes** (+ admin only) | `403` for any logged-in user who isn't in the admin allow-list — demonstrates 401 vs 403. |

Status codes: `201` signup, `200` login/read, `204` logout, `400` missing
input, `401` missing/invalid/expired token, `403` authenticated but not
authorized — every error returns `{"error": "..."}`.

## The guard — one dependency, every protected route

All token verification lives in a single FastAPI dependency,
`get_current_user`, in `main.py`. It:
1. Extracts the token from `Authorization: Bearer <token>`
2. If missing → `401 {"error": "Access token required"}`
3. Verifies it with Supabase (`auth.get_user`, a real network call)
4. If invalid/expired → `401 {"error": "Invalid or expired token"}`
5. If valid → the route receives the verified user

Every protected route just adds `user: dict = Depends(get_current_user)`
to its signature — see `/protected/dashboard`, which reuses the identical
dependency as `/protected/profile` with zero new auth code.

## Testing with curl

```bash
# Sign up
curl -i -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'      # 201

# Log in — copy the access_token from the response
curl -i -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"password123"}'      # 200

# Public route — no token needed
curl -i http://localhost:8000/public/info                          # 200

# Protected route — no token
curl -i http://localhost:8000/protected/profile                    # 401

# Protected route — with token
curl -i http://localhost:8000/protected/profile \
  -H "Authorization: Bearer PASTE_YOUR_ACCESS_TOKEN_HERE"           # 200

# Tamper with one character of the token and re-run — watch it get rejected
curl -i http://localhost:8000/protected/profile \
  -H "Authorization: Bearer PASTE_YOUR_ACCESS_TOKEN_HERE_but_wrong" # 401

# Logout (also protected)
curl -i -X POST http://localhost:8000/auth/logout \
  -H "Authorization: Bearer PASTE_YOUR_ACCESS_TOKEN_HERE"           # 204
```

## Testing with Swagger UI

1. Open `http://localhost:8000/docs`.
2. Run `/auth/signup` then `/auth/login` via **Try it out**, copy the
   `access_token` from the response.
3. Click the green **Authorize** button (top right), paste the token,
   click **Authorize**, then **Close**.
4. Now **Try it out** on any lock-icon route (`/protected/profile`,
   `/protected/dashboard`) — it authenticates automatically.

*(Insert your Swagger screenshot here — showing the lock icons and a
successful authorized call.)*

## 401 vs 403

`401 Unauthorized` means "I don't know who you are" — no token, or the
token is missing/invalid/expired. `403 Forbidden` means "I know exactly
who you are, and you still may not." `/protected/admin` demonstrates
this: any authenticated, valid-token user who isn't on the `ADMIN_EMAILS`
list gets a `403`, not a `401` — the difference between authentication
and authorization.

## Reading a JWT (optional exploration)

Paste an `access_token` into [jwt.io](https://jwt.io) — the decoded
payload shows claims like your user id and expiry, in plain readable
JSON. This is exactly why a JWT should never contain a real secret:
anyone holding the token can read its contents; only the *signature*
(which you can't forge without Supabase's private key) is what makes it
trustworthy.

## Notes for your submission

- Same public GitHub repo as A1–A3 — this is a continuation.
- `.env` must never appear in git history — verify with
  `git log --all --full-history -- .env` (should print nothing).
- Commit per stage (`git add . && git commit -m "Stage N: ..."`).
- Add your Swagger screenshot to this README before submitting.

Swagger UI screenshot (Assignment 1):

<img width="1918" height="932" alt="Screenshot 2026-07-18 194259" src="https://github.com/user-attachments/assets/b02a1ed7-2109-476d-b3f6-4f71594895e1" />

Swagger UI screenshot (Assignment 2):

<img width="431" height="318" alt="Screenshot 2026-07-24 125259" src="https://github.com/user-attachments/assets/74978459-5269-4e59-83c8-5391083f1f37" />

