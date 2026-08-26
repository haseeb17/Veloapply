"""Command-line entry point for list maintenance."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from tools.contribution import ContributionError, load_event, process_event, write_github_output
from tools.listings import load_companies, load_listings, save_listings, validate_company, validate_listings
from tools.readme import write_generated_docs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Maintain the VeloApply community job list.")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("validate", help="Validate listings.json and companies.json")
    generate = sub.add_parser("generate", help="Regenerate README.md and ATS.md")
    generate.add_argument("--date", dest="generated_at", help="Override generated-on date (YYYY-MM-DD)")

    process_cmd = sub.add_parser("process-issue", help="Apply an approved GitHub issue")
    process_cmd.add_argument("event_path", help="Path to the GitHub event JSON")

    args = parser.parse_args(argv)

    if args.command == "validate":
        return _validate()
    if args.command == "generate":
        return _generate(generated_at=args.generated_at)
    if args.command == "process-issue":
        return _process_issue(args.event_path)
    parser.error(f"unknown command {args.command}")
    return 2


def _validate() -> int:
    listings = load_listings()
    companies = load_companies()
    errors = validate_listings(listings)
    for index, company in enumerate(companies):
        for error in validate_company(company):
            errors.append(f"companies[{index}]: {error}")
    if errors:
        print("Validation failed:", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"OK: {len(listings)} listings, {len(companies)} companies")
    return 0


def _generate(*, generated_at: str | None = None) -> int:
    status = _validate()
    if status != 0:
        return status
    write_generated_docs(generated_at=generated_at)
    print("Wrote README.md and ATS.md")
    return 0


def _process_issue(event_path: str) -> int:
    listings = load_listings()
    try:
        result = process_event(load_event(event_path), listings)
    except ContributionError as exc:
        print(f"Contribution rejected: {exc}", file=sys.stderr)
        write_github_output(
            {
                "commit_username": "github-actions",
                "commit_email": "41898282+github-actions[bot]@users.noreply.github.com",
                "commit_message": "Skip invalid contribution",
                "summary_comment": f"Could not apply this contribution: {exc}",
            }
        )
        Path("comment.md").write_text(f"Could not apply this contribution: {exc}\n", encoding="utf-8")
        return 1
    save_listings(listings)
    write_generated_docs()
    write_github_output(result)
    Path("comment.md").write_text(result["summary_comment"] + "\n", encoding="utf-8")
    print(result["commit_message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
