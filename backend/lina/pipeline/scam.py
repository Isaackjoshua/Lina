"""Rule-based scam screening (SPEC §6.6). Runs on every item, in addition to the model's note.

Each rule returns a flag name. `fee_requested` is special: it rejects the listing outright.
"""

import re

from lina.pipeline.urls import same_site

FEE = "fee_requested"

_SENTENCE = re.compile(r"[^.!?\n]+[.!?]?")
_FEE = re.compile(
    r"(application|processing|registration|admission|booking|interview|training|visa processing)"
    r"\s+(fee|fees|charge|charges|deposit)|"
    r"\bpay(ment)?\b[^.\n]{0,40}\b(tzs|tsh|tshs|shillings?|usd|\$|m-?pesa|tigo ?pesa|airtel money)|"
    r"\bada ya (maombi|usajili|fomu)|\blipia\b|\btuma (pesa|fedha)",
    re.IGNORECASE,
)
# A sentence that mentions a fee only to say there is none.
_NO_FEE = re.compile(
    r"\bno\b|\bnot\b|\bfree\b|\bwithout\b|\bwaive[ds]?\b|\bnever\b|\bcovered\b|\bcovers\b|"
    r"\bhakuna\b|\bbila\b|\bbure\b|\bhaina\b",
    re.IGNORECASE,
)
_FREE_MAIL = re.compile(
    r"[\w.+-]+@(gmail|yahoo|hotmail|outlook|ymail|aol|protonmail|icloud)\.[a-z.]+", re.IGNORECASE
)
_ANY_MAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
_WHATSAPP = re.compile(r"whats\s?app|wa\.me/", re.IGNORECASE)
_GUARANTEE = re.compile(
    r"100\s?%\s*(visa|guarantee|job|success|placement)|guaranteed\s+(job|visa|admission|"
    r"employment|placement|selection)|visa\s+guarantee",
    re.IGNORECASE,
)
_URGENCY = re.compile(
    r"limited (slots|spaces|seats)|hurry|act (now|fast)|only \d+ (slots|spaces) (left|remaining)|"
    r"before it'?s too late|first come,? first served|haraka",
    re.IGNORECASE,
)
_SENSITIVE = re.compile(
    r"(send|submit|share|provide|whatsapp)[^.\n]{0,60}"
    r"(bank (account )?details|atm|pin\b|card number|copy of (your )?(passport|national id|nida))",
    re.IGNORECASE,
)


def fee_sentences(text: str) -> list[str]:
    """Sentences that ask the applicant for money (ignoring ones that say there is no fee)."""
    return [
        sentence.strip()
        for sentence in _SENTENCE.findall(text)
        if _FEE.search(sentence) and not _NO_FEE.search(sentence)
    ]


def screen(
    text: str,
    source_url: str,
    organization_url: str | None,
    official_sites: set[str],
    model_says_payment: bool = False,
) -> list[str]:
    flags = []
    if fee_sentences(text) or model_says_payment:
        flags.append(FEE)

    emails = [match.group(0) for match in _ANY_MAIL.finditer(text)]
    free_mail = [email for email in emails if _FREE_MAIL.fullmatch(email)]
    official_mail = len(emails) > len(free_mail)
    if free_mail and not official_mail:
        flags.append("personal_email_contact")
    if _WHATSAPP.search(text) and not official_mail:
        flags.append("whatsapp_only_contact")
    if _GUARANTEE.search(text):
        flags.append("guarantee_claim")
    if _URGENCY.search(text):
        flags.append("urgency_pressure")
    if _SENSITIVE.search(text):
        flags.append("asks_for_id_or_bank_details")
    if not same_site(source_url, official_sites):
        flags.append("no_official_domain")
    if organization_url and not same_site(organization_url, official_sites):
        flags.append("organization_domain_mismatch")
    return flags
