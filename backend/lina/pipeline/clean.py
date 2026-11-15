"""Reduce a fetched page to its main text."""

from bs4 import BeautifulSoup

MAX_CHARS = 60_000
_NOISE = [
    "script",
    "style",
    "noscript",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "svg",
    "iframe",
]
_BLOCKS = ["p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "br", "div", "section", "dd", "dt"]


def main_text(page: str) -> str:
    """Visible text of the page's main content, one block per line.

    Uses <main> or <article> when the page has one; otherwise the whole body
    minus navigation, headers, footers and forms.
    """
    soup = BeautifulSoup(page, "html.parser")
    for tag in soup(_NOISE):
        tag.decompose()
    root = soup.find("main") or soup.find("article") or soup.body or soup
    for tag in root.find_all(_BLOCKS):
        tag.append("\n")
    lines = (" ".join(line.split()) for line in root.get_text().splitlines())
    return "\n".join(line for line in lines if line)


_HINTS = (
    "apply", "application", "deadline", "scholarship", "fellowship", "vacanc", "internship",
    "grant", "competition", "hackathon", "conference", "training", "eligib", "call for",
    "closing date", "maombi", "nafasi", "ufadhili", "tarehe ya mwisho", "mafunzo", "ajira",
)  # fmt: skip


def looks_like_opportunity(text: str) -> bool:
    """Cheap check before paying for extraction: enough text, and at least one telltale word."""
    lowered = text.lower()
    return len(text) >= 200 and any(hint in lowered for hint in _HINTS)
