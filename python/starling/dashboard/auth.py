"""Bearer-token auth — constant-time compare; token from config (env-only)."""
from __future__ import annotations

import hmac

from fastapi import Header, HTTPException, status


def make_require_token(token: str):
    """Build a FastAPI dependency that enforces `Authorization: Bearer <token>`.

    When `token` is empty the gate is open (loopback dev). Comparison is
    constant-time; the token is never echoed in errors or logs.
    """
    async def require_token(authorization: str = Header(default="")) -> None:
        if not token:
            return
        prefix = "Bearer "
        supplied = authorization[len(prefix):] if authorization.startswith(prefix) else ""
        if not supplied or not hmac.compare_digest(supplied, token):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="invalid or missing bearer token",
            )

    return require_token
