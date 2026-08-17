"""
Task API — Assignment 4: Auth.

Adds Supabase-backed authentication on top of the existing project:
sign up, log in, log out, a public route, and protected routes guarded
by a reusable bearer-token dependency that verifies the JWT with
Supabase on every request.

Run with:
    uvicorn main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
  - Click "Authorize", paste an access_token from /auth/login, and
    "Try it out" on any lock-icon route.
"""

from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

import auth
import llm.client as llm_client
from llm.schema import TriageInput

app = FastAPI(
    title="Task API",
    version="4.0",
    description="A Supabase-authenticated API — signup/login/logout and protected routes, built for FlyRank W2 A4.",
)

# auto_error=False so our own exception handler controls the exact 401
# body/status, instead of FastAPI's default HTTPBearer behaviour.
bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Every error in this API returns {"error": "..."} — a single exception
# handler makes that true everywhere, including for our own 401s/403s
# raised via HTTPException below.
# ---------------------------------------------------------------------------

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    detail = exc.detail
    message = detail if isinstance(detail, str) else str(detail)
    return JSONResponse(status_code=exc.status_code, content={"error": message})


# ---------------------------------------------------------------------------
# The guard — a reusable dependency, applied to every protected route.
# This is the ONE place token verification happens (Stage 4's golden rule).
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    if credentials is None or not credentials.credentials:
        raise HTTPException(status_code=401, detail="Access token required")

    result = auth.get_user(credentials.credentials)
    if not result.ok:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return result.data


# ---------------------------------------------------------------------------
# Root & public
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "Task API",
        "version": "4.0",
        "endpoints": [
            "/auth/signup", "/auth/login", "/auth/logout",
            "/public/info", "/protected/profile", "/protected/dashboard",
        ],
    }


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/public/info")
def public_info():
    return {"message": "Welcome stranger! This info is public."}


# ---------------------------------------------------------------------------
# Stage 1 — signup & login
# ---------------------------------------------------------------------------

@app.post("/auth/signup", status_code=201)
def signup(payload: dict):
    email = payload.get("email") if isinstance(payload, dict) else None
    password = payload.get("password") if isinstance(payload, dict) else None

    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    result = auth.sign_up(email, password)
    if not result.ok:
        raise HTTPException(status_code=400, detail=result.error or "Sign up failed")

    return JSONResponse(status_code=201, content={"user": result.data})


@app.post("/auth/login")
def login(payload: dict):
    email = payload.get("email") if isinstance(payload, dict) else None
    password = payload.get("password") if isinstance(payload, dict) else None

    if not email or not password:
        raise HTTPException(status_code=400, detail="email and password are required")

    result = auth.sign_in(email, password)
    if not result.ok:
        raise HTTPException(status_code=401, detail="Invalid login credentials")

    return result.data


@app.post("/auth/refresh")
def refresh_token(payload: dict):
    refresh_value = payload.get("refresh_token") if isinstance(payload, dict) else None
    if not refresh_value:
        raise HTTPException(status_code=400, detail="refresh_token is required")

    result = auth.refresh(refresh_value)
    if not result.ok:
        raise HTTPException(status_code=401, detail=result.error or "Invalid refresh token")

    return result.data


# ---------------------------------------------------------------------------
# Stage 2 & 3 — protected routes, verified via the shared dependency
# ---------------------------------------------------------------------------

@app.get("/protected/profile")
def profile(user: dict = Depends(get_current_user)):
    return {"user": user}


@app.get("/protected/dashboard")
def dashboard(user: dict = Depends(get_current_user)):
    # A second protected route reusing the exact same dependency — no new
    # auth code, which is the whole point of Stage 4.
    return {"message": f"Welcome to your dashboard, {user['email']}."}


# ---------------------------------------------------------------------------
# Stretch — a real 403 case: authenticated, but not authorized.
# 401 = "I don't know who you are." 403 = "I know you, and no."
# ---------------------------------------------------------------------------

ADMIN_EMAILS = {"admin@example.com"}


@app.get("/protected/admin")
def admin_only(user: dict = Depends(get_current_user)):
    if user["email"] not in ADMIN_EMAILS:
        raise HTTPException(status_code=403, detail="You do not have permission to access this resource")
    return {"message": "Welcome, admin."}


# ---------------------------------------------------------------------------
# Stage 4 — logout (a protected route itself)
# ---------------------------------------------------------------------------

@app.post("/auth/logout", status_code=204)
def logout(user: dict = Depends(get_current_user)):
    auth.sign_out(None)
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# A17 — /triage: one messy task description in, one validated JSON out.
# Validate -> build prompt -> call model (timeout + bounded retries) ->
# parse + validate -> repair once on failure -> return clean JSON or 422.
# ---------------------------------------------------------------------------

@app.post("/triage")
def triage_task(payload: dict):
    # Validate the input before spending a single model call.
    try:
        parsed_input = TriageInput.model_validate(payload if isinstance(payload, dict) else {})
    except ValidationError as exc:
        first_error = exc.errors()[0]
        field = ".".join(str(p) for p in first_error["loc"]) or "text"
        raise HTTPException(status_code=400, detail=f"{field}: {first_error['msg']}")

    try:
        outcome = llm_client.triage(parsed_input.text)
    except llm_client.LLMDisabledError:
        raise HTTPException(status_code=503, detail="LLM feature is currently disabled")
    except llm_client.ModelTimeoutError:
        raise HTTPException(status_code=504, detail="The model took too long to respond")
    except ValueError as exc:
        # Validation failed twice (once + one repair retry) — quarantined already.
        raise HTTPException(status_code=422, detail=str(exc))

    return outcome.result.model_dump()