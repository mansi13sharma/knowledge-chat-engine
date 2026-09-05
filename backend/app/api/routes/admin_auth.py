"""Login endpoint for the single hardcoded admin account. Issues the session
token that `app/services/auth.require_admin` checks on every other
`/api/admin/*` route."""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.auth import issue_token, verify_credentials

logger = logging.getLogger("app.api.routes.admin_auth")
router = APIRouter(prefix="/api/admin/auth", tags=["admin-auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    email: str


@router.post("/login", response_model=LoginResponse)
def login(body: LoginRequest) -> LoginResponse:
    email = body.email.strip().lower()
    if not verify_credentials(email, body.password):
        logger.warning("Admin login failed for email=%s", email)
        raise HTTPException(401, "Invalid email or password.")

    logger.info("Admin login succeeded for email=%s", email)
    return LoginResponse(token=issue_token(email), email=email)
