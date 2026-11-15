from pathlib import Path

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from lina.models import Source
from lina.pipeline.sources import SourceSpec, load_sources, sync_sources

SOURCES_FILE = Path(__file__).parent.parent / "sources.yaml"


def spec(**overrides: object) -> SourceSpec:
    data = {"key": "udsm", "name": "UDSM", "url": "https://www.udsm.ac.tz/", "kind": "html_list"}
    return SourceSpec.model_validate({**data, **overrides})


def test_the_real_sources_file_is_valid_and_within_the_proposed_range() -> None:
    specs = load_sources(SOURCES_FILE)
    assert 15 <= len(specs) <= 25
    assert all(str(s.url).startswith("https://") for s in specs)


def test_new_sources_are_unverified_unless_the_owner_says_otherwise() -> None:
    assert spec().verified is False


def test_rejects_typos_and_bad_values() -> None:
    for bad in (
        {"verifed": True},
        {"kind": "scrape"},
        {"key": "Not A Slug"},
        {"default_type": "gig"},
        {"url": "notaurl"},
        {"parsing_hints": {"selector": "a"}},
    ):
        with pytest.raises(ValidationError):
            spec(**bad)


def test_rejects_duplicate_keys(tmp_path: Path) -> None:
    entry = "  - {key: a, name: A, url: 'https://a.tz/', kind: rss}\n"
    path = tmp_path / "sources.yaml"
    path.write_text("sources:\n" + entry + entry)
    with pytest.raises(ValueError, match="Duplicate source keys"):
        load_sources(path)


def test_sync_creates_updates_and_deactivates(session: Session) -> None:
    assert sync_sources(session, [spec(), spec(key="heslb", name="HESLB")]) == {
        "created": 2,
        "updated": 0,
        "deactivated": 0,
    }
    counts = sync_sources(session, [spec(name="University of Dar es Salaam", verified=True)])
    assert counts == {"created": 0, "updated": 1, "deactivated": 1}

    sources = {s.key: s for s in session.scalars(select(Source))}
    assert sources["udsm"].name == "University of Dar es Salaam"
    assert sources["udsm"].verified is True
    assert sources["heslb"].active is False


def test_changing_a_url_forgets_the_old_robots_answer_and_cache(session: Session) -> None:
    sync_sources(session, [spec()])
    source = session.scalars(select(Source)).one()
    source.robots_allowed, source.etag = True, '"abc"'
    session.commit()

    sync_sources(session, [spec(url="https://www.udsm.ac.tz/announcements")])
    assert source.robots_allowed is None
    assert source.etag is None
