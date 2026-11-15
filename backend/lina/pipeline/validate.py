"""Quality gates on an extraction (SPEC §2 trust, §6.5): nothing here trusts the model."""

import re
from datetime import date

from lina.models.enums import DeadlineType, OpenToTanzanians
from lina.pipeline.schema import FIELDS, Extraction

MIN_QUOTE_CHARS = 8
MAX_SUMMARY_WORDS = 100  # the target is 80; a little slack before a reviewer is bothered

_TANZANIA_ELIGIBLE = re.compile(
    r"tanzania|east africa|\bafrica|sub-saharan|developing countr|low- and middle-income|"
    r"low and middle income|all nationalities|any nationality|all countries|international "
    r"(students|applicants)|worldwide",
    re.IGNORECASE,
)


def normalize_for_evidence(text: str) -> str:
    """The form in which a quote and the page are compared.

    TODO(human): decide what else should be treated as "the same text".
    Today this ignores only letter case and whitespace differences, the strictest
    sensible choice: a quote the model retyped with different punctuation fails,
    the deadline is blanked, and the item is flagged for review. Candidates to
    also normalize: curly vs straight quotes, en/em dashes vs hyphens,
    non-breaking spaces. Looser matching means fewer false alarms but a slightly
    wider door for a quote that is not really in the page.
    """
    return " ".join(text.casefold().split())


def quote_in_source(quote: str | None, source_text: str) -> bool:
    if not quote or len(quote.strip()) < MIN_QUOTE_CHARS:
        return False
    return normalize_for_evidence(quote) in normalize_for_evidence(source_text)


def parse_deadline(value: str | None) -> date | None:
    try:
        return date.fromisoformat(value) if value else None
    except ValueError:
        return None


def validate(extraction: Extraction, source_text: str, today: date) -> tuple[Extraction, list[str]]:
    """Return a corrected copy and the review flags raised. Never raises on bad content:
    a failed check blanks the field and flags the item instead."""
    data = extraction.model_copy(deep=True)
    flags: list[str] = []

    # --- Deadline: needs a parseable date and a quote that is really in the page. ---
    if data.deadline is not None:
        if parse_deadline(data.deadline) is None:
            flags.append("deadline_unparseable")
            data.deadline = None
        elif not quote_in_source(data.evidence.deadline_quote, source_text):
            flags.append("evidence_deadline_failed")
            data.deadline = None
        if data.deadline is None:
            data.deadline_type = DeadlineType.UNCLEAR
            data.evidence.deadline_quote = None

    # --- Eligibility: any stated restriction needs a quote that is really in the page. ---
    claims_eligibility = (
        data.open_to_tanzanians != OpenToTanzanians.UNCLEAR
        or data.eligible_countries is not None
        or data.age_min is not None
        or data.age_max is not None
    )
    if claims_eligibility and not quote_in_source(data.evidence.eligibility_quote, source_text):
        flags.append("evidence_eligibility_failed")
        data.open_to_tanzanians = OpenToTanzanians.UNCLEAR
        data.eligible_countries = None
        data.age_min = data.age_max = None
        data.evidence.eligibility_quote = None
    elif data.open_to_tanzanians == OpenToTanzanians.YES and not _TANZANIA_ELIGIBLE.search(
        source_text
    ):
        # SPEC §7: "yes" only if the text names Tanzania, the region, or all nationalities.
        flags.append("open_to_tanzanians_unsupported")
        data.open_to_tanzanians = OpenToTanzanians.UNCLEAR

    if data.age_min is not None and data.age_max is not None and data.age_min > data.age_max:
        flags.append("age_range_invalid")
        data.age_min = data.age_max = None

    # --- Payment: only count a fee claim the page really makes. ---
    if data.evidence.payment_quote and not quote_in_source(
        data.evidence.payment_quote, source_text
    ):
        data.evidence.payment_quote = None

    # --- Controlled values. ---
    data.fields = [f for f in dict.fromkeys(data.fields) if f in FIELDS]
    if data.eligible_countries is not None:
        codes = [c.strip() for c in data.eligible_countries]
        if any(c.lower() == "any" for c in codes):
            data.eligible_countries = ["any"]
        else:
            data.eligible_countries = [c.upper() for c in codes if re.fullmatch(r"[A-Za-z]{2}", c)]
    if data.location_country and not re.fullmatch(r"[A-Za-z]{2}", data.location_country.strip()):
        data.location_country = None

    for name in ("summary_en", "summary_sw"):
        if len((getattr(data, name) or "").split()) > MAX_SUMMARY_WORDS:
            flags.append(f"{name}_too_long")

    return data, flags


def deadline_has_passed(extraction: Extraction, today: date) -> bool:
    deadline = parse_deadline(extraction.deadline)
    return deadline is not None and deadline < today


def lowest_confidence(extraction: Extraction) -> float:
    scores: list[float] = list(extraction.confidence.model_dump().values())
    return min(scores)
