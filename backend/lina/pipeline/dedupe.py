"""Duplicate detection (SPEC §6.7): the same opportunity seen again must not become a new row."""

import hashlib
import re
import unicodedata
from datetime import date
from difflib import SequenceMatcher

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from lina.models import Opportunity
from lina.models.enums import OpportunityStatus

TITLE_SIMILARITY = 0.9


def normalize(value: str) -> str:
    """Lower-case, strip accents and punctuation, collapse spaces."""
    ascii_text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", ascii_text.lower()).split())


def dedupe_key(organization: str, title: str, deadline: date | None) -> str:
    parts = [normalize(organization), normalize(title), deadline.isoformat() if deadline else ""]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def slugify(title: str, limit: int = 80) -> str:
    slug = normalize(title).replace(" ", "-")[:limit].strip("-")
    return slug or "fursa"


def unique_slug(session: Session, column: str, title: str) -> str:
    base = slugify(title)
    slug, n = base, 1
    field = getattr(Opportunity, column)
    while session.scalar(select(Opportunity.id).where(field == slug)):
        n += 1
        slug = f"{base}-{n}"
    return slug


def find_duplicate(
    session: Session, source_url: str, organization: str, title_en: str, deadline: date | None
) -> Opportunity | None:
    """An existing listing for the same opportunity, if any: same official page, same
    organization + title + deadline, or the same organization and deadline with a
    near-identical title."""
    key = dedupe_key(organization, title_en, deadline)
    exact = session.scalars(
        select(Opportunity)
        .where(or_(Opportunity.source_url == source_url, Opportunity.dedupe_key == key))
        .order_by(Opportunity.id)
    ).first()
    if exact:
        return exact

    wanted_org, wanted_title = normalize(organization), normalize(title_en)
    candidates = session.scalars(
        select(Opportunity).where(
            Opportunity.deadline.is_(None)
            if deadline is None
            else Opportunity.deadline == deadline,
            Opportunity.status != OpportunityStatus.REJECTED.value,
        )
    )
    for candidate in candidates:
        if normalize(candidate.organization) != wanted_org:
            continue
        ratio = SequenceMatcher(None, normalize(candidate.title_en), wanted_title).ratio()
        if ratio >= TITLE_SIMILARITY:
            return candidate
    return None
