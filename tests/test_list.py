"""Tests for listing validation and contribution processing."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.contribution import (
    ContributionError,
    listing_from_new_issue,
    parse_inactive_urls,
    parse_issue_body,
    process_event,
)
from tools.listings import listing_id_for_url, validate_listing, validate_listings
from tools.readme import generate_readme


NEW_ISSUE_BODY = """
### Link to Job Posting

https://jobs.ashbyhq.com/example/abc-123

### Company Name

Example Labs

### Company Website

https://example.com

### Role Title

Senior Software Engineer

### Location

Remote | Austin, TX

### Experience Level

Senior

### Category

Software Engineering

### Work Arrangement

Remote

### ATS / Application Platform

Ashby

### Visa Sponsorship

Unknown / not listed

### Is this role currently accepting applications?

Yes

### Custom screening or tailored application?

- [x] Yes — this posting has custom questions, a cover letter, or a long ATS form

### Date Posted

2026-08-20

### Email associated with your GitHub account (Optional)

_No response_

### Extra Notes (Optional)

_No response_
"""


def _base_listing(**overrides):
    listing = {
        "id": "abc123abc123",
        "company": "Example Labs",
        "title": "Senior Software Engineer",
        "category": "software-engineering",
        "level": "senior",
        "locations": ["Remote"],
        "work_arrangement": "remote",
        "ats": "ashby",
        "url": "https://jobs.ashbyhq.com/example/abc-123",
        "sponsorship": "unknown",
        "tailor_recommended": True,
        "active": True,
        "date_added": "2026-08-26",
    }
    listing.update(overrides)
    return listing


class ListingValidationTests(unittest.TestCase):
    def test_valid_listing(self):
        self.assertEqual(validate_listing(_base_listing()), [])

    def test_rejects_aggregator_urls(self):
        errors = validate_listing(_base_listing(url="https://www.linkedin.com/jobs/view/123"))
        self.assertTrue(any("aggregator" in error for error in errors))

    def test_rejects_internships(self):
        errors = validate_listing(_base_listing(title="Software Engineering Intern"))
        self.assertTrue(any("out of scope" in error for error in errors))

    def test_allows_internal_tools_title(self):
        errors = validate_listing(_base_listing(title="Senior Internal Tools Engineer"))
        self.assertFalse(any("out of scope" in error for error in errors))

    def test_duplicate_urls(self):
        first = _base_listing()
        second = _base_listing(id="otheridotherid")
        errors = validate_listings([first, second])
        self.assertTrue(any("duplicate url" in error for error in errors))

    def test_stable_ids(self):
        self.assertEqual(
            listing_id_for_url("https://jobs.ashbyhq.com/example/abc-123"),
            listing_id_for_url("https://www.jobs.ashbyhq.com/example/abc-123/"),
        )


class ContributionTests(unittest.TestCase):
    def test_parse_issue_body(self):
        parsed = parse_issue_body(NEW_ISSUE_BODY)
        self.assertEqual(parsed["Company Name"], "Example Labs")
        self.assertEqual(parsed["Experience Level"], "Senior")

    def test_new_listing_from_issue(self):
        from tools.contribution import NEW_LISTING_FIELDS, map_fields

        listing = listing_from_new_issue(
            map_fields(parse_issue_body(NEW_ISSUE_BODY), NEW_LISTING_FIELDS),
            today="2026-08-26",
        )
        self.assertEqual(listing["company"], "Example Labs")
        self.assertEqual(listing["level"], "senior")
        self.assertEqual(listing["locations"], ["Remote", "Austin, TX"])
        self.assertTrue(listing["tailor_recommended"])
        self.assertEqual(listing["date_posted"], "2026-08-20")

    def test_process_new_listing_event(self):
        event = {
            "issue": {
                "number": 12,
                "body": NEW_ISSUE_BODY,
                "user": {"login": "jane"},
                "labels": [{"name": "approved"}, {"name": "new_listing"}],
            }
        }
        listings: list[dict] = []
        result = process_event(event, listings, today="2026-08-26")
        self.assertEqual(result["action"], "added")
        self.assertEqual(len(listings), 1)
        self.assertEqual(listings[0]["company"], "Example Labs")
        self.assertIn("Example Labs", result["commit_message"])

    def test_duplicate_new_listing_is_rejected(self):
        listing = listing_from_new_issue(
            {
                "url": "https://jobs.ashbyhq.com/example/abc-123",
                "company": "Example Labs",
                "title": "Senior Software Engineer",
                "locations": "Remote",
                "level": "Senior",
                "category": "Software Engineering",
                "work_arrangement": "Remote",
                "ats": "Ashby",
                "sponsorship": "Unknown / not listed",
                "active": "Yes",
            },
            today="2026-08-26",
        )
        event = {
            "issue": {
                "body": NEW_ISSUE_BODY,
                "user": {"login": "jane"},
                "labels": [{"name": "approved"}, {"name": "new_listing"}],
            }
        }
        with self.assertRaises(ContributionError):
            process_event(event, [listing], today="2026-08-26")

    def test_mark_inactive(self):
        listing = _base_listing()
        event = {
            "issue": {
                "body": "### Job URL(s) to mark inactive\n\nhttps://jobs.ashbyhq.com/example/abc-123\n\n### Why is it inactive?\n\nFilled\n",
                "user": {"login": "maintainer"},
                "labels": [{"name": "approved"}, {"name": "mark_inactive"}],
            }
        }
        result = process_event(event, [listing], today="2026-08-26")
        self.assertEqual(result["action"], "marked_inactive")
        self.assertFalse(listing["active"])
        self.assertEqual(listing["date_inactive"], "2026-08-26")

    def test_parse_inactive_urls(self):
        urls = parse_inactive_urls(
            "https://jobs.lever.co/acme/1\nhttps://boards.greenhouse.io/acme/jobs/2\n"
        )
        self.assertEqual(len(urls), 2)

    def test_rejects_internship_contribution(self):
        with self.assertRaises(ContributionError):
            listing_from_new_issue(
                {
                    "url": "https://boards.greenhouse.io/acme/jobs/1",
                    "company": "Acme",
                    "title": "Software Engineering Intern",
                    "locations": "Remote",
                    "level": "Mid-level",
                    "category": "Software Engineering",
                    "work_arrangement": "Remote",
                    "ats": "Greenhouse",
                    "sponsorship": "Unknown / not listed",
                    "active": "Yes",
                }
            )


class ReadmeTests(unittest.TestCase):
    def test_readme_contains_role_and_cta(self):
        markdown = generate_readme(
            [_base_listing(company_url="https://example.com")],
            generated_at="2026-08-26",
        )
        self.assertIn("Senior Software Engineer", markdown)
        self.assertIn("Example Labs", markdown)
        self.assertIn("Ashby", markdown)
        self.assertIn("VeloApply", markdown)
        self.assertIn("1 open roles", markdown)
        self.assertNotIn("{{CATEGORY_SECTIONS}}", markdown)


class CliSmokeTests(unittest.TestCase):
    def test_github_output_file(self):
        from tools.contribution import write_github_output

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out"
            write_github_output(
                {
                    "commit_username": "jane",
                    "commit_email": "jane@users.noreply.github.com",
                    "commit_message": "Added listing: Example",
                    "summary_comment": "Accepted **Example**.\n\nDone.",
                },
                path=str(path),
            )
            text = path.read_text(encoding="utf-8")
            self.assertIn("commit_username=jane", text)
            self.assertIn("summary_comment<<EOF", text)


if __name__ == "__main__":
    unittest.main()
