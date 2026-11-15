from lina.eval import SCORED_FIELDS, Case, evaluate, format_eval, load_cases
from tests.helpers import NOT_OPPORTUNITY, FakeExtractor, make_extraction


def test_golden_cases_load_and_are_well_formed() -> None:
    cases = load_cases()
    assert len(cases) >= 5
    for case in cases:
        assert case.page and case.source_url.startswith("https://")
        if case.expected["is_opportunity"]:
            assert set(SCORED_FIELDS) <= set(case.expected), case.name


def scholarship_case() -> Case:
    return next(c for c in load_cases() if c.name == "synthetic_scholarship")


def test_perfect_answer_scores_full_marks() -> None:
    report = evaluate([scholarship_case()], FakeExtractor({"*": make_extraction()}), "m")
    assert report.scored == 1 and report.misses == []
    assert all(report.correct[name] == 1 for name in SCORED_FIELDS)
    assert "deadline               1/1   100.0%" in format_eval(report, "m")


def test_wrong_fields_are_counted_and_listed() -> None:
    wrong = make_extraction(funding="unpaid", education_levels=["master", "phd"])
    report = evaluate([scholarship_case()], FakeExtractor({"*": wrong}), "m")
    assert (report.correct["funding"], report.correct["education_levels"]) == (0, 0)
    assert report.correct["deadline"] == 1
    assert "synthetic_scholarship: funding expected 'fully_funded', got 'unpaid'" in report.misses


def test_score_is_taken_after_the_evidence_gate() -> None:
    """A right date with a made-up quote is stored as blank, so it scores as a miss."""
    made_up = make_extraction(evidence={"deadline_quote": "Deadline: thirtieth of November."})
    report = evaluate([scholarship_case()], FakeExtractor({"*": made_up}), "m")
    assert report.correct["deadline"] == 0


def test_missed_opportunity_and_failed_call() -> None:
    report = evaluate([scholarship_case()], FakeExtractor({"*": NOT_OPPORTUNITY}), "m")
    assert (report.opportunity_correct, report.scored) == (0, 0)
    report = evaluate([scholarship_case()], FakeExtractor({"*": None}), "m")
    assert report.failed_calls == 1
