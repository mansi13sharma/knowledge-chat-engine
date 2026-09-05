"""Single-admin email/password auth gating the admin API.

Deliberately minimal for a one-account portfolio project: no user table, no
password reset flow, no refresh tokens. The password is never stored in
plaintext — only an HMAC keyed by `admin_auth_secret` (a "hash" in the same
sense a peppered hash is: unrecoverable without the secret, resistant to
rainbow tables). Session tokens are a small HMAC-signed payload (email +
expiry), not a JWT library, since that's all a single-role session needs.
"""

import base64
import hashlib
import hmac
import json
import time

from fastapi import Header, HTTPException

from app.core.config import settings


def hash_password(password: str) -> str:
    return hmac.new(settings.admin_auth_secret.encode(), password.encode(), hashlib.sha256).hexdigest()


def verify_credentials(email: str, password: str) -> bool:
    if not settings.admin_email or not settings.admin_password_hash or not settings.admin_auth_secret:
        return False
    email_ok = hmac.compare_digest(email.strip().lower(), settings.admin_email.strip().lower())
    password_ok = hmac.compare_digest(hash_password(password), settings.admin_password_hash)
    return email_ok and password_ok


def _sign(payload: bytes) -> str:
    return hmac.new(settings.admin_auth_secret.encode(), payload, hashlib.sha256).hexdigest()


def issue_token(email: str) -> str:
    payload = json.dumps({"email": email, "exp": int(time.time()) + settings.admin_session_ttl_seconds}).encode()
    payload_b64 = base64.urlsafe_b64encode(payload).decode()
    return f"{payload_b64}.{_sign(payload)}"


def _verify_token(token: str) -> str | None:
    """Returns the session's email if `token` has a valid signature and
    hasn't expired, else `None`."""
    try:
        payload_b64, signature = token.split(".", 1)
        payload = base64.urlsafe_b64decode(payload_b64.encode())
    except (ValueError, UnicodeDecodeError):
        return None

    if not hmac.compare_digest(_sign(payload), signature):
        return None

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if data.get("exp", 0) < time.time():
        return None
    return data.get("email")


def require_admin(authorization: str | None = Header(default=None)) -> str:
    """FastAPI dependency: raises 401 unless `Authorization: Bearer <token>`
    carries a currently-valid session token, otherwise returns the email."""
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing or invalid authorization header.")

    email = _verify_token(authorization.removeprefix("Bearer ").strip())
    if not email:
        raise HTTPException(401, "Invalid or expired session. Please log in again.")
    return email
