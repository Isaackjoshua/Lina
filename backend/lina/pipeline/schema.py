"""The extraction contract (SPEC §7): what the model must return for one page."""

from pydantic import BaseModel, Field

from lina.models.enums import (
    DeadlineType,
    EducationLevel,
    Funding,
    OpenToTanzanians,
    OpportunityType,
    WorkMode,
)

# Controlled list of sector / discipline tags (SPEC §5 `fields[]`).
FIELDS = [
    "agriculture", "arts-culture", "business", "climate-environment", "data-ai", "education",
    "engineering", "entrepreneurship", "finance", "health", "humanities", "law", "media",
    "natural-sciences", "public-service", "social-sciences", "technology", "tourism-hospitality",
    "any",
]  # fmt: skip


class Evidence(BaseModel):
    deadline_quote: str | None = Field(
        description="The exact sentence or phrase in the source that states the deadline, "
        "copied character for character. null if the source gives no deadline."
    )
    eligibility_quote: str | None = Field(
        description="The exact sentence in the source that states who may apply "
        "(nationality, age or level), copied character for character. null if none."
    )
    payment_quote: str | None = Field(
        description="The exact sentence asking applicants to pay any fee or send money. "
        "null if applicants are not asked to pay."
    )


class Confidence(BaseModel):
    """0.0 to 1.0 for each key field: how sure you are that the value is right."""

    type: float
    deadline: float
    open_to_tanzanians: float
    funding: float
    education_levels: float


class Extraction(BaseModel):
    is_opportunity: bool = Field(
        description="true only if this page announces one specific opportunity a person can "
        "apply to or register for. false for news, lists of many items, results, or general "
        "information pages."
    )
    not_opportunity_reason: str | None
    type: OpportunityType | None
    title_en: str | None
    title_sw: str | None
    organization: str | None = Field(description="The organization offering it, original name.")
    organization_url: str | None
    apply_url: str | None = Field(
        description="Where to apply, only if the source gives a link. Never guess a URL."
    )
    summary_en: str | None = Field(description="Your own words, at most 80 words.")
    summary_sw: str | None = Field(description="Natural Tanzanian Swahili, at most 80 words.")
    fields: list[str] = Field(description=f"Zero or more of: {', '.join(FIELDS)}")
    education_levels: list[EducationLevel]
    eligible_countries: list[str] | None = Field(
        description='ISO 3166-1 alpha-2 codes, or ["any"] if open to all. null if not stated.'
    )
    open_to_tanzanians: OpenToTanzanians
    age_min: int | None
    age_max: int | None
    other_eligibility: str | None = Field(description="Short. Other requirements, if any.")
    funding: Funding
    funding_note: str | None
    location_city: str | None
    location_country: str | None = Field(description="ISO 3166-1 alpha-2 code, or null.")
    work_mode: WorkMode
    deadline: str | None = Field(description="YYYY-MM-DD, or null if not stated or rolling.")
    deadline_type: DeadlineType
    asks_for_payment: bool = Field(
        description="true if applicants must pay any application, processing or registration fee."
    )
    risk_note: str | None = Field(
        description="One short sentence if anything looks like a scam (fees, personal email or "
        "WhatsApp-only contact, guarantees, unrealistic pay, pressure, requests for ID or bank "
        "details, organization does not match the website). null if nothing stands out."
    )
    evidence: Evidence
    confidence: Confidence
