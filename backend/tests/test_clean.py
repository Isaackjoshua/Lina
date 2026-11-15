from lina.pipeline.clean import looks_like_opportunity, main_text
from tests.conftest import fixture


def test_main_text_keeps_content_and_drops_chrome() -> None:
    text = main_text(fixture("list_page.html"))
    assert "Postgraduate Scholarships 2027" in text
    assert "Privacy" not in text and "Email us" not in text


def test_main_text_drops_scripts_and_keeps_lines_separate() -> None:
    text = main_text(fixture("detail_scholarship.html"))
    assert "analytics" not in text and "font-family" not in text
    assert "The deadline for applications is 30 November 2026." in text.splitlines()


def test_prefilter_passes_opportunities_and_stops_news_and_stubs() -> None:
    assert looks_like_opportunity(main_text(fixture("detail_scholarship.html")))
    assert not looks_like_opportunity(main_text(fixture("detail_news.html")))
    assert not looks_like_opportunity("Apply now")  # too short to be a real page
