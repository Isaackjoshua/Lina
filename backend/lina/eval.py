"""Golden-set evaluation (SPEC §7). Run with: python -m lina.eval

Each case in eval/golden/ is a saved page plus the answers a person checked by hand.
The score is what the pipeline would actually store: the model's answer after the
evidence and validation gates. Running this calls the Claude API and costs money
(a few cents for 20 pages on the default model).
"""

import argparse
import json
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from lina.config import get_settings
from lina.pipeline.clean import main_text
from lina.pipeline.extract import ClaudeExtractor, Extractor, ExtractorNotConfigured
from lina.pipeline.validate import validate

GOLDEN_DIR = Path(__file__).parent.parent / "eval" / "golden"
SCORED_FIELDS = ("type", "deadline", "open_to_tanzanians", "funding", "education_levels")


@dataclass(frozen=True)
class Case:
    name: str
    page: str
    source_url: str
    default_type: str | None
    today: date
    expected: dict[str, Any]


@dataclass
class Report:
    cases: int = 0
    failed_calls: int = 0
    opportunity_correct: int = 0
    scored: int = 0  # cases where both sides say "this is an opportunity"
    correct: dict[str, int] = field(default_factory=lambda: dict.fromkeys(SCORED_FIELDS, 0))
    misses: list[str] = field(default_factory=list)
    cost_usd: Decimal = Decimal("0")


def load_cases(directory: Path = GOLDEN_DIR) -> list[Case]:
    cases = []
    for path in sorted(directory.glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        cases.append(
            Case(
                name=path.stem,
                page=(directory / data["page"]).read_text(encoding="utf-8"),
                source_url=data["source_url"],
                default_type=data.get("default_type"),
                today=date.fromisoformat(data["today"]),
                expected=data["expected"],
            )
        )
    return cases


def _comparable(name: str, value: Any) -> Any:
    if name == "education_levels":
        return sorted(str(getattr(v, "value", v)) for v in value or [])
    return getattr(value, "value", value)


def evaluate(cases: list[Case], extractor: Extractor, model: str) -> Report:
    report = Report(cases=len(cases))
    for case in cases:
        text = main_text(case.page)
        result = extractor.extract(text, case.source_url, case.default_type, case.today, model)
        report.cost_usd += result.cost_usd
        if result.extraction is None:
            report.failed_calls += 1
            report.misses.append(f"{case.name}: no answer ({result.problem})")
            continue
        answer, _flags = validate(result.extraction, text, case.today)
        expected_opportunity = bool(case.expected["is_opportunity"])
        if answer.is_opportunity == expected_opportunity:
            report.opportunity_correct += 1
        else:
            report.misses.append(
                f"{case.name}: is_opportunity expected {expected_opportunity}, "
                f"got {answer.is_opportunity}"
            )
        if not (answer.is_opportunity and expected_opportunity):
            continue
        report.scored += 1
        for name in SCORED_FIELDS:
            expected = _comparable(name, case.expected.get(name))
            got = _comparable(name, getattr(answer, name))
            if expected == got:
                report.correct[name] += 1
            else:
                report.misses.append(f"{case.name}: {name} expected {expected!r}, got {got!r}")
    return report


def format_eval(report: Report, model: str) -> str:
    def line(label: str, right: int, total: int) -> str:
        share = f"{100 * right / total:5.1f}%" if total else "   n/a"
        return f"  {label:<20} {right:>3}/{total:<3} {share}"

    lines = [
        f"Golden set: {report.cases} pages, model {model}",
        line("is_opportunity", report.opportunity_correct, report.cases),
        *(line(name, report.correct[name], report.scored) for name in SCORED_FIELDS),
        f"  failed calls: {report.failed_calls}   estimated cost: ${report.cost_usd:.4f}",
    ]
    if report.misses:
        lines += ["Misses:", *(f"  {miss}" for miss in report.misses)]
    return "\n".join(lines)


def main() -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(prog="python -m lina.eval")
    parser.add_argument("--model", default=settings.extract_model)
    args = parser.parse_args()
    cases = load_cases()
    if not cases:
        print(f"No cases in {GOLDEN_DIR}")
        return 1
    try:
        extractor = ClaudeExtractor(settings.glossary_file)
    except ExtractorNotConfigured as exc:
        print(f"Cannot run the eval: {exc}")
        return 2
    print(format_eval(evaluate(cases, extractor, args.model), args.model))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
