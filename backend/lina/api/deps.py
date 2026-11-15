"""Shared FastAPI dependencies."""

import secrets
from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from lina.config import Settings, get_settings


def require_internal_token(
    settings: Annotated[Settings, Depends(get_settings)],
    authorization: Annotated[str | None, Header()] = None,
) -> None:
    """Guard for /internal/* routes, which only the Next.js server may call.

    The admin's GitHub login is checked in Next.js; this token proves the call
    comes from our own web server. Fails closed when the token is not configured.
    """
    expected = settings.internal_api_token
    if not expected:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "INTERNAL_API_TOKEN is not configured"
        )
    supplied = (authorization or "").removeprefix("Bearer ")
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid internal token")
