"""Stand-ins for the model, so no test calls the Claude API."""

from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

from lina.pipeline.extract import ExtractionResult
from lina.pipeline.schema import Extraction

SCHOLARSHIP: dict[str, Any] = {
    "is_opportunity": True,
    "not_opportunity_reason": None,
    "type": "scholarship",
    "title_en": "Postgraduate Scholarships 2027",
    "title_sw": "Ufadhili wa Masomo ya Uzamili 2027",
    "organization": "Example University",
    "organization_url": "https://www.example-university.ac.tz/",
    "apply_url": None,
    "summary_en": "Fully funded Master's scholarships for the 2027/2028 academic year.",
    "summary_sw": "Ufadhili kamili wa masomo ya shahada ya uzamili kwa mwaka wa masomo 2027/2028.",
    "fields": ["education"],
    "education_levels": ["bachelor"],
    "eligible_countries": ["TZ"],
    "open_to_tanzanians": "yes",
    "age_min": None,
    "age_max": None,
    "other_eligibility": "GPA of at least 3.5",
    "funding": "fully_funded",
    "funding_note": None,
    "location_city": None,
    "location_country": "TZ",
    "work_mode": "onsite",
    "deadline": "2026-11-30",
    "deadline_type": "fixed",
    "asks_for_payment": False,
    "risk_note": None,
    "evidence": {
        "deadline_quote": "The deadline for applications is 30 November 2026.",
        "eligibility_quote": "Applicants must be Tanzanian citizens holding a Bachelor's degree",
        "payment_quote": None,
    },
    "confidence": {
        "type": 0.95,
        "deadline": 0.95,
        "open_to_tanzanians": 0.9,
        "funding": 0.9,
        "education_levels": 0.8,
    },
}


def make_extraction(**overrides: Any) -> Extraction:
    """A correct reading of fixtures/detail_scholarship.html, with any fields overridden.
    Nested `evidence` / `confidence` overrides are merged into the defaults."""
    data: dict[str, Any] = {**SCHOLARSHIP}
    for key, value in overrides.items():
        data[key] = {**SCHOLARSHIP[key], **value} if key in ("evidence", "confidence") else value
    return Extraction.model_validate(data)


NOT_OPPORTUNITY = make_extraction(
    is_opportunity=False,
    not_opportunity_reason="A news article",
    type=None,
    title_en=None,
    title_sw=None,
    organization=None,
    organization_url=None,
    summary_en=None,
    summary_sw=None,
    fields=[],
    education_levels=[],
    eligible_countries=None,
    open_to_tanzanians="unclear",
    other_eligibility=None,
    funding="unclear",
    location_country=None,
    work_mode="unclear",
    deadline=None,
    deadline_type="unclear",
    evidence={"deadline_quote": None, "eligibility_quote": None},
)

Answer = Extraction | ExtractionResult | None


class FakeExtractor:
    """Returns canned answers. `answers` maps a model name (or "*") to an answer, or is a
    function of (url, model). Every call is recorded and costs one cent."""

    def __init__(self, answers: dict[str, Answer] | Callable[[str, str], Answer]) -> None:
        self.answers = answers
        self.calls: list[tuple[str, str]] = []

    def extract(
        self, text: str, source_url: str, default_type: str | None, today: date, model: str
    ) -> ExtractionResult:
        self.calls.append((source_url, model))
        if callable(self.answers):
            answer = self.answers(source_url, model)
        else:
            answer = self.answers.get(model, self.answers.get("*"))
        if isinstance(answer, ExtractionResult):
            return answer
        return ExtractionResult(
            answer,
            model,
            input_tokens=1000,
            output_tokens=200,
            cost_usd=Decimal("0.01"),
            problem=None if answer else "incomplete model output",
        )
