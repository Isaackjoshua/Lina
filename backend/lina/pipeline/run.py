"""The fetch stage of the daily pipeline (SPEC §6.1-6.3): listing -> detail pages -> raw_items."""

from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from lina.config import Settings
from lina.models import PipelineRun, RawItem, Source
from lina.models.enums import FetchFrequency, RawItemStatus, RunKind, RunStatus, SourceKind
from lina.pipeline.fetchers import content_hash, discover, feed_links, page_title
from lina.pipeline.http import FetchError, PoliteClient, RobotsDisallowed
from lina.pipeline.urls import same_site, site_of, url_hash

FAILURES_BEFORE_FLAG = 3


def allowed_sites(source: Source) -> set[str]:
    extra = source.parsing_hints.get("allowed_domains", [])
    return {site_of(source.url), *(domain.lower().removeprefix("www.") for domain in extra)}


def is_due(source: Source, now: datetime) -> bool:
    if source.fetch_frequency != FetchFrequency.WEEKLY or source.last_success_at is None:
        return True
    return now - source.last_success_at >= timedelta(days=6, hours=12)


def eligible_sources(session: Session, only: str | None, now: datetime) -> list[Source]:
    """Sources we may fetch: active, verified by the owner, not blocked by robots.txt, and due."""
    query = select(Source).where(
        Source.active.is_(True),
        Source.verified.is_(True),
        Source.robots_allowed.is_not(False),
        Source.kind != SourceKind.MANUAL.value,
    )
    if only:
        query = query.where(Source.key == only)
    return [s for s in session.scalars(query.order_by(Source.key)) if only or is_due(s, now)]


def run_fetch(
    session: Session,
    client: PoliteClient,
    settings: Settings,
    only: str | None = None,
    now: datetime | None = None,
    dry_run: bool = True,
) -> PipelineRun:
    now = now or datetime.now(UTC)
    run = PipelineRun(kind=RunKind.PIPELINE.value, status=RunStatus.RUNNING.value, dry_run=dry_run)
    session.add(run)
    session.commit()

    counts: Counter[str] = Counter()
    errors: list[dict[str, Any]] = []
    budget = settings.max_items_per_run

    for source in eligible_sources(session, only, now):
        if budget <= 0:
            counts["sources_deferred"] += 1
            continue
        counts["sources_tried"] += 1
        try:
            budget -= _fetch_source(session, client, settings, source, run, counts, errors, budget)
        except FetchError as exc:
            source.consecutive_failures += 1
            counts["sources_failed"] += 1
            errors.append({"source": source.key, "url": source.url, "error": str(exc)})
        else:
            source.consecutive_failures = 0
            source.last_success_at = now
            counts["sources_ok"] += 1
        session.commit()

    all_failed = counts["sources_tried"] > 0 and counts["sources_ok"] == 0
    run.status = (RunStatus.FAILED if all_failed else RunStatus.SUCCEEDED).value
    run.finished_at = datetime.now(UTC)
    run.counts = dict(counts)
    run.errors = errors
    session.commit()
    return run


def _fetch_source(
    session: Session,
    client: PoliteClient,
    settings: Settings,
    source: Source,
    run: PipelineRun,
    counts: Counter[str],
    errors: list[dict[str, Any]],
    budget: int,
) -> int:
    """Fetch one source. Returns how many detail pages were fetched.
    Raises FetchError only when the listing itself cannot be read."""
    listing = client.get(source.url, etag=source.etag, last_modified=source.last_modified)
    if listing.not_modified:
        counts["sources_not_modified"] += 1
        return 0

    sites = allowed_sites(source)
    candidates = discover(source.kind, listing.text, listing.url, source.parsing_hints, sites)
    counts["candidates_found"] += len(candidates)
    if not candidates:
        counts["sources_empty"] += 1
        errors.append(
            {"source": source.key, "url": source.url, "error": "No item links found; check hints"}
        )

    limit = min(source.parsing_hints.get("max_items") or settings.max_items_per_source, budget)
    fetched = 0
    left_over = False
    for candidate in candidates:
        key = url_hash(candidate.url)
        if session.scalar(select(RawItem.id).where(RawItem.url_hash == key)):
            counts["already_seen"] += 1
            continue
        if fetched >= limit:
            left_over = True
            counts["left_for_next_run"] += 1
            continue
        try:
            page = client.get(candidate.url)
        except RobotsDisallowed:
            counts["blocked_by_robots"] += 1
            continue
        except FetchError as exc:
            # Not stored, so the next run tries this page again.
            left_over = True
            counts["item_errors"] += 1
            errors.append({"source": source.key, "url": candidate.url, "error": str(exc)})
            continue
        fetched += 1
        if not same_site(page.url, sites):
            counts["off_site"] += 1
            continue

        digest = content_hash(page.text)
        duplicate = session.scalar(select(RawItem.id).where(RawItem.content_hash == digest))
        session.add(
            RawItem(
                source_id=source.id,
                pipeline_run_id=run.id,
                url=candidate.url,
                url_hash=key,
                title=candidate.title or page_title(page.text),
                published_at=candidate.published_at,
                http_status=page.status,
                content_hash=digest,
                html=None if duplicate else page.text,
                status=(RawItemStatus.SKIPPED if duplicate else RawItemStatus.NEW).value,
                error="Same content as an earlier item" if duplicate else None,
            )
        )
        session.flush()
        counts["duplicates" if duplicate else "stored"] += 1

    # Remember the listing's validators only when everything on it was handled;
    # otherwise an unchanged listing (304) would hide the pages we still owe.
    source.etag = None if left_over else listing.etag
    source.last_modified = None if left_over else listing.last_modified
    return fetched


def check_sources(
    session: Session, client: PoliteClient, only: str | None = None, probe: bool = False
) -> list[dict[str, Any]]:
    """Check robots.txt for every source's listing URL and record the answer.
    With probe=True, also fetch each allowed listing once to confirm it loads."""
    query = select(Source).where(Source.kind != SourceKind.MANUAL.value).order_by(Source.key)
    if only:
        query = query.where(Source.key == only)
    rows = []
    for source in session.scalars(query):
        row: dict[str, Any] = {"key": source.key, "url": source.url}
        try:
            row["robots_allowed"] = client.allowed(source.url)
        except FetchError as exc:
            row["robots_allowed"] = False
            row["note"] = str(exc)
        source.robots_allowed = row["robots_allowed"]
        source.robots_checked_at = datetime.now(UTC)
        if probe and row["robots_allowed"]:
            try:
                page = client.get(source.url)
            except FetchError as exc:
                row["listing"] = f"failed: {exc}"
            else:
                found = discover(
                    source.kind, page.text, page.url, source.parsing_hints, allowed_sites(source)
                )
                row["listing"] = f"ok, {len(found)} links"
                if page.url.rstrip("/") != source.url.rstrip("/"):
                    row["redirected_to"] = page.url
                row["feeds"] = feed_links(page.text, page.url)
        session.commit()
        rows.append(row)
    return rows


def format_report(session: Session, run: PipelineRun) -> str:
    counts = run.counts
    lines = [
        f"Pipeline run #{run.id}{' (fetch only)' if run.dry_run else ''} — {run.status}",
        f"  sources: {counts.get('sources_tried', 0)} tried, {counts.get('sources_ok', 0)} ok, "
        f"{counts.get('sources_failed', 0)} failed, "
        f"{counts.get('sources_not_modified', 0)} unchanged, "
        f"{counts.get('sources_deferred', 0)} deferred",
        f"  items:   {counts.get('candidates_found', 0)} links found, "
        f"{counts.get('stored', 0)} new stored, {counts.get('already_seen', 0)} already seen, "
        f"{counts.get('duplicates', 0)} duplicate content, "
        f"{counts.get('left_for_next_run', 0)} left for next run",
        f"  skipped: {counts.get('blocked_by_robots', 0)} blocked by robots.txt, "
        f"{counts.get('off_site', 0)} redirected off the official site, "
        f"{counts.get('item_errors', 0)} page errors",
    ]
    if not run.dry_run:
        lines += [
            f"  review:  {counts.get('queued', 0)} new candidates for review, "
            f"{counts.get('duplicates_merged', 0)} merged into existing listings, "
            f"{counts.get('rejected_fee', 0)} auto-rejected (asked for money)",
            f"  dropped: {counts.get('skipped_prefilter', 0)} not opportunity pages (free check), "
            f"{counts.get('skipped_not_opportunity', 0)} not opportunities (model), "
            f"{counts.get('skipped_deadline_passed', 0)} deadline passed, "
            f"{counts.get('extraction_failed', 0)} failed, "
            f"{counts.get('extraction_retry', 0)} to retry, "
            f"{counts.get('waiting_spend_cap', 0)} waiting (spend cap)",
            f"  cost:    {run.input_tokens} input + {run.output_tokens} output tokens, "
            f"about ${run.estimated_cost_usd:.4f}",
        ]
    if run.errors:
        lines.append("  errors:")
        lines += [f"    [{e.get('source', '-')}] {e.get('error')}" for e in run.errors]
    flagged = session.scalars(
        select(Source)
        .where(Source.consecutive_failures >= FAILURES_BEFORE_FLAG, Source.active.is_(True))
        .order_by(Source.key)
    ).all()
    if flagged:
        lines.append("  FLAGGED sources (3 or more failures in a row):")
        lines += [f"    {s.key}: {s.consecutive_failures} failures" for s in flagged]
    if run.dry_run and not counts.get("sources_tried"):
        lines.append("  No source was fetched. Sources need `verified: true` in sources.yaml.")
    return "\n".join(lines)
