"""FastAPI application. Run with: uvicorn lina.api.main:app"""

from typing import Annotated

from fastapi import APIRouter, Depends, FastAPI
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from lina.api.deps import require_internal_token
from lina.db import get_session
from lina.models import Opportunity, Source

app = FastAPI(title="LINA API", version="0.1.0")

internal = APIRouter(prefix="/internal", dependencies=[Depends(require_internal_token)])


@app.get("/health")
def health() -> dict[str, str]:
    """Liveness only: the process is up. Does not touch the database."""
    return {"status": "ok"}


@internal.get("/status")
def internal_status(session: Annotated[Session, Depends(get_session)]) -> dict[str, object]:
    """Readiness for the admin dashboard: database reachable, schema migrated."""
    revision = session.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
    return {
        "database": "ok",
        "schema_revision": revision,
        "opportunities": session.execute(
            select(func.count()).select_from(Opportunity)
        ).scalar_one(),
        "sources": session.execute(select(func.count()).select_from(Source)).scalar_one(),
    }


app.include_router(internal)
