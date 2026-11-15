"""sources.yaml: the list of official sources, and syncing it into the database.

Until the admin sources page exists (M4), sources.yaml is the place to add,
verify and disable sources. `sync` copies it into the database.
"""

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from lina.models import Source
from lina.models.enums import FetchFrequency, OpportunityType, SourceKind


class Hints(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_selector: str | None = None  # CSS selector for item links on an HTML list page
    url_pattern: str | None = None  # regex a detail-page URL must match
    allowed_domains: list[str] = []  # extra official domains detail pages may live on
    max_items: int | None = Field(default=None, ge=1, le=50)  # per run, for this source


class SourceSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$", max_length=80)
    name: str = Field(min_length=1, max_length=200)
    url: HttpUrl
    kind: SourceKind
    default_type: OpportunityType | None = None
    country: str | None = Field(default=None, pattern=r"^[A-Z]{2}$")  # omit for international
    active: bool = True
    verified: bool = False  # only the owner sets this to true
    fetch_frequency: FetchFrequency = FetchFrequency.DAILY
    parsing_hints: Hints = Hints()
    notes: str | None = None

    @field_validator("notes")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        return value.strip() if value else None


def load_sources(path: str | Path) -> list[SourceSpec]:
    data: Any = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    specs = [SourceSpec.model_validate(item) for item in data["sources"]]
    keys = [spec.key for spec in specs]
    duplicates = sorted({key for key in keys if keys.count(key) > 1})
    if duplicates:
        raise ValueError(f"Duplicate source keys in {path}: {', '.join(duplicates)}")
    return specs


def sync_sources(session: Session, specs: list[SourceSpec]) -> dict[str, int]:
    """Make the database match sources.yaml. Sources removed from the file are
    switched off, not deleted, so their history stays."""
    existing = {source.key: source for source in session.scalars(select(Source))}
    counts = {"created": 0, "updated": 0, "deactivated": 0}
    for spec in specs:
        source = existing.pop(spec.key, None)
        if source is None:
            source = Source(key=spec.key)
            session.add(source)
            counts["created"] += 1
        else:
            counts["updated"] += 1
        url = str(spec.url)
        if source.url != url:
            # A different page: old cache validators and robots result no longer apply.
            source.etag = source.last_modified = None
            source.robots_allowed = source.robots_checked_at = None
        source.name = spec.name
        source.url = url
        source.kind = spec.kind.value
        source.default_type = spec.default_type.value if spec.default_type else None
        source.country = spec.country
        source.active = spec.active
        source.verified = spec.verified
        source.fetch_frequency = spec.fetch_frequency.value
        source.parsing_hints = spec.parsing_hints.model_dump(exclude_defaults=True)
        source.notes = spec.notes
    for source in existing.values():
        if source.active:
            source.active = False
            counts["deactivated"] += 1
    session.commit()
    return counts
