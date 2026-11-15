"""The extraction stage (SPEC §6.3-6.8): raw_items -> opportunities waiting for review."""

import logging
from collections import Counter
from datetime import UTC, date, datetime, time
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from lina.config import Settings
from lina.models import Opportunity, PipelineRun, RawItem, Source
from lina.models.enums import OpportunityStatus, RawItemStatus
from lina.pipeline import scam
from lina.pipeline.clean import MAX_CHARS, looks_like_opportunity, main_text
from lina.pipeline.dedupe import dedupe_key, find_duplicate, unique_slug
from lina.pipeline.extract import Extractor
from lina.pipeline.http import FetchError, PoliteClient
from lina.pipeline.run import allowed_sites
from lina.pipeline.schema import Extraction
from lina.pipeline.urls import canonicalize_url, same_site
from lina.pipeline.validate import deadline_has_passed, lowest_confidence, parse_deadline, validate

log = logging.getLogger("lina.pipeline")

_REQUIRED = ("type", "title_en", "title_sw", "organization", "summary_en", "summary_sw")


def spent_today(session: Session, settings: Settings, now: datetime) -> Decimal:
    """Estimated LLM spend so far today (East Africa Time), across all runs."""
    zone = ZoneInfo(settings.timezone)
    midnight = datetime.combine(now.astimezone(zone).date(), time.min, tzinfo=zone)
    total = session.scalar(
        select(func.coalesce(func.sum(PipelineRun.estimated_cost_usd), 0)).where(
            PipelineRun.started_at >= midnight
        )
    )
    return Decimal(total or 0)


def run_extract(
    session: Session,
    extractor: Extractor,
    client: PoliteClient | None,
    settings: Settings,
    run: PipelineRun,
    now: datetime | None = None,
) -> PipelineRun:
    """Process waiting raw items into `run`, adding to its counts, errors, tokens and cost.
    Stops at MAX_ITEMS_PER_RUN or when today's spend reaches MAX_DAILY_LLM_USD; whatever is
    left stays `new` for the next run."""
    now = now or datetime.now(UTC)
    today = now.astimezone(ZoneInfo(settings.timezone)).date()
    counts: Counter[str] = Counter(run.counts)
    errors: list[dict[str, Any]] = list(run.errors)
    cap = Decimal(str(settings.max_daily_llm_usd))
    already_spent = spent_today(session, settings, now) - run.estimated_cost_usd

    items = session.scalars(
        select(RawItem)
        .where(RawItem.status == RawItemStatus.NEW.value, RawItem.html.is_not(None))
        .order_by(RawItem.id)
        .limit(settings.max_items_per_run)
    ).all()
    for position, item in enumerate(items):
        if already_spent + run.estimated_cost_usd >= cap:
            counts["waiting_spend_cap"] += len(items) - position
            errors.append({"source": "-", "error": f"Daily LLM spend cap of ${cap} reached"})
            break
        source = session.get_one(Source, item.source_id)
        outcome = _process_item(session, extractor, client, settings, run, item, source, today)
        counts[outcome] += 1
        if item.status == RawItemStatus.FAILED.value:
            errors.append({"source": source.key, "url": item.url, "error": item.error})
        run.counts = dict(counts)
        run.errors = errors
        session.commit()

    run.counts = dict(counts)
    run.errors = errors
    session.commit()
    return run


def _finish(item: RawItem, status: RawItemStatus, note: str | None = None) -> None:
    item.status = status.value
    item.error = note
    item.html = None  # the raw page is never kept past this point


def _process_item(
    session: Session,
    extractor: Extractor,
    client: PoliteClient | None,
    settings: Settings,
    run: PipelineRun,
    item: RawItem,
    source: Source,
    today: date,
) -> str:
    """Handle one raw item. Returns the name of the count to increment."""
    text = main_text(item.html or "")
    truncated = len(text) > MAX_CHARS
    text = text[:MAX_CHARS]

    if not looks_like_opportunity(text):
        _finish(item, RawItemStatus.SKIPPED, "Does not look like an opportunity page")
        return "skipped_prefilter"

    retry_later = False

    def ask(model: str) -> Extraction | None:
        nonlocal retry_later
        result = extractor.extract(text, item.url, source.default_type, today, model)
        run.input_tokens += result.input_tokens
        run.output_tokens += result.output_tokens
        run.estimated_cost_usd += result.cost_usd
        if result.extraction is None:
            item.error = result.problem
            retry_later = result.retryable
        return result.extraction

    raw_extraction = ask(settings.extract_model)
    if raw_extraction is None:
        if retry_later:
            return "extraction_retry"  # stays `new`, page kept, tried again next run
        _finish(item, RawItemStatus.FAILED, item.error)
        return "extraction_failed"
    extraction, flags = validate(raw_extraction, text, today)

    # A second opinion from the stronger model, only when the first answer is shaky.
    shaky = lowest_confidence(extraction) < settings.review_confidence_threshold or any(
        flag.startswith("evidence_") for flag in flags
    )
    if extraction.is_opportunity and shaky and settings.review_model != settings.extract_model:
        second = ask(settings.review_model)
        if second is not None:
            extraction, flags = validate(second, text, today)
            flags.append("second_opinion_used")
        item.error = None

    if not extraction.is_opportunity:
        _finish(
            item, RawItemStatus.SKIPPED, extraction.not_opportunity_reason or "Not an opportunity"
        )
        return "skipped_not_opportunity"
    if deadline_has_passed(extraction, today):
        _finish(item, RawItemStatus.SKIPPED, f"Deadline {extraction.deadline} has passed")
        return "skipped_deadline_passed"
    missing = [name for name in _REQUIRED if not getattr(extraction, name)]
    if missing:
        _finish(item, RawItemStatus.FAILED, f"Extraction is missing: {', '.join(missing)}")
        return "extraction_failed"
    if truncated:
        flags.append("source_text_truncated")

    sites = allowed_sites(source)
    apply_url = _checked_apply_url(extraction.apply_url, item.url, sites, client, flags)
    organization_url = canonicalize_url(extraction.organization_url or "")
    scam_flags = scam.screen(
        text,
        item.url,
        organization_url,
        sites,
        model_says_payment=extraction.asks_for_payment
        and extraction.evidence.payment_quote is not None,
    )
    rejected = scam.FEE in scam_flags
    reason = None
    if rejected:
        quotes = scam.fee_sentences(text) or [extraction.evidence.payment_quote or ""]
        reason = f"Auto-rejected: asks applicants for money. Source says: “{quotes[0][:300]}”"
        log.info("auto-rejected %s: %s", item.url, reason)

    deadline = parse_deadline(extraction.deadline)
    title_en, organization = str(extraction.title_en), str(extraction.organization)
    existing = find_duplicate(session, item.url, organization, title_en, deadline)
    outcome = "rejected_fee" if rejected else "queued"
    if existing is not None and existing.status != OpportunityStatus.NEEDS_REVIEW.value:
        # Already decided by the reviewer (or expired): never change it behind their back.
        _finish(item, RawItemStatus.SKIPPED, f"Duplicate of listing #{existing.id}")
        item.opportunity_id = existing.id
        return "duplicates_merged"

    listing = existing or Opportunity(
        slug_en=unique_slug(session, "slug_en", title_en),
        slug_sw=unique_slug(session, "slug_sw", str(extraction.title_sw)),
        source_url=item.url,
        source_id=source.id,
    )
    listing.type = str(extraction.type)
    listing.title_en = title_en
    listing.title_sw = str(extraction.title_sw)
    listing.organization = organization
    listing.organization_url = organization_url
    listing.apply_url = apply_url
    listing.summary_en = str(extraction.summary_en)
    listing.summary_sw = str(extraction.summary_sw)
    listing.fields = extraction.fields
    listing.education_levels = [level.value for level in extraction.education_levels]
    listing.eligible_countries = extraction.eligible_countries
    listing.open_to_tanzanians = extraction.open_to_tanzanians.value
    listing.age_min = extraction.age_min
    listing.age_max = extraction.age_max
    listing.other_eligibility = extraction.other_eligibility
    listing.funding = extraction.funding.value
    listing.funding_note = extraction.funding_note
    listing.location_city = extraction.location_city
    listing.location_country = (extraction.location_country or "").upper() or None
    listing.work_mode = extraction.work_mode.value
    listing.deadline = deadline
    listing.deadline_type = extraction.deadline_type.value
    listing.evidence = {
        "deadline_quote": extraction.evidence.deadline_quote,
        "eligibility_quote": extraction.evidence.eligibility_quote,
    }
    listing.confidence = extraction.confidence.model_dump()
    listing.scam_flags = scam_flags
    listing.review_flags = list(dict.fromkeys(flags))
    listing.risk_note = extraction.risk_note
    listing.status = (
        OpportunityStatus.REJECTED if rejected else OpportunityStatus.NEEDS_REVIEW
    ).value
    listing.reviewer_note = reason
    listing.content_hash = item.content_hash
    listing.dedupe_key = dedupe_key(organization, title_en, deadline)
    if existing is None:
        session.add(listing)
    else:
        outcome = "duplicates_merged"
    session.flush()

    _finish(item, RawItemStatus.PROCESSED)
    item.text = text  # kept for the reviewer; cleared when the listing is decided (M4)
    item.opportunity_id = listing.id
    return outcome


def _checked_apply_url(
    url: str | None, source_url: str, sites: set[str], client: PoliteClient | None, flags: list[str]
) -> str | None:
    """SPEC §6.5: the apply link must resolve and should stay on the official domain."""
    canonical = canonicalize_url(url or "", source_url)
    if canonical is None:
        return None
    if canonical == source_url:
        return canonical
    if not same_site(canonical, sites):
        # Often legitimate (an external application portal), so the reviewer decides.
        flags.append("apply_url_off_official_domain")
        return canonical
    if client is None:
        flags.append("apply_url_unchecked")
        return canonical
    try:
        final = client.get(canonical).url
    except FetchError:
        flags.append("apply_url_unreachable")
        return None
    if not same_site(final, sites):
        flags.append("apply_url_off_official_domain")
    return canonicalize_url(final)
