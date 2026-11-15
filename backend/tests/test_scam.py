import pytest

from lina.pipeline import scam
from lina.pipeline.clean import main_text
from tests.conftest import fixture

SITES = {"example-university.ac.tz"}
URL = "https://www.example-university.ac.tz/announcements/x"


def flags(text: str, **kwargs: object) -> list[str]:
    return scam.screen(text, URL, None, SITES, **kwargs)  # type: ignore[arg-type]


def test_scam_page_raises_every_relevant_flag() -> None:
    found = flags(main_text(fixture("detail_scam.html")))
    assert set(found) == {
        "fee_requested",
        "personal_email_contact",
        "whatsapp_only_contact",
        "guarantee_claim",
        "urgency_pressure",
        "asks_for_id_or_bank_details",
    }


def test_honest_page_raises_nothing() -> None:
    assert flags(main_text(fixture("detail_scholarship.html"))) == []


@pytest.mark.parametrize(
    "sentence",
    [
        "Applicants must pay an application fee of TZS 10,000.",
        "A non-refundable registration fee is required.",
        "Send payment of 20 USD to confirm your seat.",
        "Lipia ada ya maombi kupitia M-Pesa.",
        "Tuma pesa kwa namba hii ili kuthibitisha.",
    ],
)
def test_fee_requests_are_caught(sentence: str) -> None:
    assert scam.FEE in flags(sentence)


@pytest.mark.parametrize(
    "sentence",
    [
        "There is no application fee.",
        "The application fee is waived for African applicants.",
        "Applying is free; we never charge a processing fee.",
        "Hakuna ada ya maombi.",
        "The scholarship covers tuition fees and a monthly stipend.",
        "Successful candidates will be paid TZS 800,000 per month.",
    ],
)
def test_mentions_of_no_fee_or_of_salary_are_not_fee_requests(sentence: str) -> None:
    assert scam.FEE not in flags(sentence)


def test_model_verified_payment_counts_as_fee() -> None:
    assert flags("Nothing suspicious in the wording.", model_says_payment=True) == ["fee_requested"]


def test_official_email_next_to_gmail_is_not_personal_contact() -> None:
    text = "Write to admissions@example-university.ac.tz or backup.office@gmail.com."
    assert "personal_email_contact" not in flags(text)


def test_domain_checks() -> None:
    assert "no_official_domain" in scam.screen("x", "https://jobs.blogspot.com/a", None, SITES)
    assert "organization_domain_mismatch" in scam.screen("x", URL, "https://other.org/", SITES)
    assert scam.screen("x", URL, "https://admission.example-university.ac.tz/", SITES) == []
