"""Pipeline commands. Run with: python -m lina.pipeline <command>

sync             copy sources.yaml into the database
check [--probe]  check robots.txt for each source (and, with --probe, load each listing once)
fetch            dry run: fetch verified sources, store raw items, print a report
"""

import argparse
import logging

from lina.config import get_settings
from lina.db import get_sessionmaker
from lina.models import PipelineRun
from lina.models.enums import RunKind, RunStatus
from lina.pipeline.extract import ClaudeExtractor, ExtractorNotConfigured
from lina.pipeline.http import FetchError, PoliteClient
from lina.pipeline.process import run_extract
from lina.pipeline.run import check_sources, format_report, run_fetch
from lina.pipeline.sources import load_sources, sync_sources


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m lina.pipeline")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("sync", help="copy sources.yaml into the database")
    check = commands.add_parser("check", help="check robots.txt for each source")
    check.add_argument("--probe", action="store_true", help="also load each allowed listing once")
    check.add_argument("--source", help="only this source key")
    fetch = commands.add_parser("fetch", help="dry run: fetch verified sources and store raw items")
    fetch.add_argument("--source", help="only this source key (ignores the weekly schedule)")
    run_all = commands.add_parser("run", help="fetch, then extract into the review queue")
    run_all.add_argument("--source", help="only fetch this source key")
    commands.add_parser("extract", help="extract raw items that are already fetched")
    return run_command(parser.parse_args())


def run_command(args: argparse.Namespace) -> int:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level, format="%(levelname)s %(name)s %(message)s")

    with get_sessionmaker()() as session:
        counts = sync_sources(session, load_sources(settings.sources_file))
        if args.command == "sync":
            print(f"sources.yaml synced: {counts}")
            return 0

        try:
            client = PoliteClient(settings)
        except FetchError as exc:
            print(f"Cannot fetch: {exc}")
            return 2
        try:
            if args.command == "check":
                for row in check_sources(session, client, only=args.source, probe=args.probe):
                    extras = "  ".join(
                        f"{k}={v}" for k, v in row.items() if k not in ("key", "url")
                    )
                    print(f"{row['key']:<26} {extras}\n{'':<26} {row['url']}")
                return 0
            if args.command == "fetch":
                run = run_fetch(session, client, settings, only=args.source)
            else:
                try:
                    extractor = ClaudeExtractor(settings.glossary_file)
                except ExtractorNotConfigured as exc:
                    print(f"Cannot extract: {exc}")
                    return 2
                if args.command == "run":
                    run = run_fetch(session, client, settings, only=args.source, dry_run=False)
                else:
                    run = PipelineRun(kind=RunKind.PIPELINE.value, status=RunStatus.SUCCEEDED.value)
                    session.add(run)
                    session.commit()
                run = run_extract(session, extractor, client, settings, run)
            print(format_report(session, run))
            return 0 if run.status == "succeeded" else 1
        finally:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
