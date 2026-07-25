"""
auth.py — the only module that talks to Supabase.

Every route in main.py calls functions from here instead of touching the
Supabase client directly. Same "one module owns the external service"
pattern as db.py in Assignment 2/3 — if the auth provider ever changed,
this is the only file that should need to change.

We never store a password and never hash anything ourselves. Supabase
does all of that; this file only ever forwards credentials to Supabase
and verifies the tokens it hands back.
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError(
        "SUPABASE_URL and SUPABASE_KEY must be set in your .env file. "
        "Copy .env.example to .env and fill in your project's values."
    )

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)


@dataclass
class AuthResult:
    ok: bool
    data: Optional[dict] = None
    error: Optional[str] = None


def sign_up(email: str, password: str) -> AuthResult:
    try:
        result = supabase.auth.sign_up({"email": email, "password": password})
        user = result.user
        if user is None:
            return AuthResult(ok=False, error="Sign up failed")
        return AuthResult(
            ok=True,
            data={
                "id": user.id,
                "email": user.email,
                "created_at": str(user.created_at),
            },
        )
    except Exception as exc:
        return AuthResult(ok=False, error=str(exc))


def sign_in(email: str, password: str) -> AuthResult:
    try:
        result = supabase.auth.sign_in_with_password(
            {"email": email, "password": password}
        )
        session = result.session
        if session is None:
            return AuthResult(ok=False, error="Invalid login credentials")
        return AuthResult(
            ok=True,
            data={
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "token_type": "bearer",
                "expires_in": session.expires_in,
            },
        )
    except Exception:
        # Supabase raises on bad credentials rather than returning a session.
        return AuthResult(ok=False, error="Invalid login credentials")


def get_user(access_token: str) -> AuthResult:
    """Verify a JWT with Supabase and return the user it belongs to."""
    try:
        result = supabase.auth.get_user(access_token)
        user = result.user
        if user is None:
            return AuthResult(ok=False, error="Invalid or expired token")
        return AuthResult(
            ok=True,
            data={
                "id": user.id,
                "email": user.email,
                "created_at": str(user.created_at),
            },
        )
    except Exception:
        return AuthResult(ok=False, error="Invalid or expired token")


def sign_out(access_token: str) -> AuthResult:
    try:
        # supabase-py's sign_out affects the SDK's own stored session; since
        # our server is stateless, verifying-then-discarding the token
        # everywhere it's used is what actually "logs out" a stateless JWT
        # client-side. We still call sign_out for the server-side session
        # Supabase tracks.
        supabase.auth.sign_out()
        return AuthResult(ok=True)
    except Exception as exc:
        return AuthResult(ok=False, error=str(exc))


def refresh(refresh_token: str) -> AuthResult:
    try:
        result = supabase.auth.refresh_session(refresh_token)
        session = result.session
        if session is None:
            return AuthResult(ok=False, error="Invalid refresh token")
        return AuthResult(
            ok=True,
            data={
                "access_token": session.access_token,
                "refresh_token": session.refresh_token,
                "token_type": "bearer",
                "expires_in": session.expires_in,
            },
        )
    except Exception:
        return AuthResult(ok=False, error="Invalid refresh token")