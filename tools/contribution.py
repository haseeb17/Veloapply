"""Parse GitHub issue forms and apply listing updates."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from tools.constants import (
    DISPLAY_ARRANGEMENT,
    DISPLAY_ATS,
    DISPLAY_CATEGORY,
    DISPLAY_LEVEL,
    DISPLAY_SPONSORSHIP,
    EDIT_LISTING_FIELDS,
    MARK_INACTIVE_FIELDS,
    NEW_LISTING_FIELDS,
)
from tools.listings import (
    canonical_url,
    find_by_url,
    listing_id_for_url,
    split_locations,
    utc_today,
    validate_listing,
)

NO_RESPONSE = {"_no response_", "n/a", "na", "none", "-", ""}


class ContributionError(ValueError):
    """Raised when an issue cannot be turned into a listing change."""


def parse_issue_body(body: str) -> dict[str, str]:
    """Parse a GitHub issue-form body into heading -> value."""
    text = body.replace("\r\n", "\n").strip()
    if not text:
        return {}
    chunks = re.split(r"^###\s+", text, flags=re.MULTILINE)
    parsed: dict[str, str] = {}
    for chunk in chunks:
        if not chunk.strip():
            continue
        heading, _, rest = chunk.partition("\n")
        value = rest.strip()
        value = re.sub(r"^```[a-z]*\n", "", value)
        value = re.sub(r"\n```$", "", value)
        parsed[heading.strip()] = value.strip()
    return parsed


def map_fields(raw: dict[str, str], mapping: dict[str, str]) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for heading, key in mapping.items():
        if heading in raw:
            mapped[key] = raw[heading]
    return mapped


def _clean(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    if text.lower() in NO_RESPONSE:
        return None
    return text


def _as_bool(value: str | None, default: bool | None = None) -> bool | None:
    cleaned = _clean(value)
    if cleaned is None:
        return default
    normalized = cleaned.lower()
    if normalized in {"yes", "true", "active"}:
        return True
    if normalized in {"no", "false", "inactive"}:
        return False
    if "- [x]" in normalized and "not sure" not in normalized:
        return True
    if "- [ ]" in normalized:
        return False
    return default


def _first_checkbox_checked(value: str | None) -> bool:
    cleaned = _clean(value)
    if not cleaned:
        return False
    for line in cleaned.splitlines():
        if line.strip().lower().startswith("- [x]"):
            return True
    return False


def listing_from_new_issue(fields: dict[str, str], *, today: str | None = None) -> dict[str, Any]:
    today = today or utc_today()
    url = _clean(fields.get("url"))
    company = _clean(fields.get("company"))
    title = _clean(fields.get("title"))
    if not url or not company or not title:
        raise ContributionError("Company, role title, and posting URL are required.")

    level = DISPLAY_LEVEL.get(_clean(fields.get("level")) or "")
    category = DISPLAY_CATEGORY.get(_clean(fields.get("category")) or "")
    arrangement = DISPLAY_ARRANGEMENT.get(_clean(fields.get("work_arrangement")) or "")
    ats = DISPLAY_ATS.get(_clean(fields.get("ats")) or "")
    sponsorship = DISPLAY_SPONSORSHIP.get(_clean(fields.get("sponsorship")) or "", "unknown")
    locations = split_locations(_clean(fields.get("locations")) or "")
    active = _as_bool(fields.get("active"), True)
    if active is False:
        raise ContributionError("Only currently open roles can be added. Use the mark-inactive form to close a listing.")

    listing = {
        "id": listing_id_for_url(url),
        "company": company,
        "company_url": _clean(fields.get("company_url")),
        "title": title,
        "category": category,
        "level": level,
        "locations": locations,
        "work_arrangement": arrangement,
        "ats": ats,
        "url": canonical_url(url),
        "sponsorship": sponsorship,
        "tailor_recommended": _first_checkbox_checked(fields.get("tailor_recommended")),
        "active": True,
        "date_posted": _clean(fields.get("date_posted")),
        "date_added": today,
        "source": "community",
    }
    errors = validate_listing(listing)
    if errors:
        raise ContributionError("; ".join(errors))
    return listing


def apply_edits(existing: dict[str, Any], fields: dict[str, str]) -> dict[str, Any]:
    updated = dict(existing)
    new_url = _clean(fields.get("new_url"))
    if new_url:
        updated["url"] = canonical_url(new_url)
        updated["id"] = listing_id_for_url(new_url)

    replacements = {
        "company": _clean(fields.get("company")),
        "company_url": _clean(fields.get("company_url")),
        "title": _clean(fields.get("title")),
        "date_posted": _clean(fields.get("date_posted")),
    }
    for key, value in replacements.items():
        if value:
            updated[key] = value

    if _clean(fields.get("locations")):
        updated["locations"] = split_locations(fields["locations"])
    if _clean(fields.get("level")):
        updated["level"] = DISPLAY_LEVEL.get(fields["level"].strip(), existing.get("level"))
    if _clean(fields.get("category")):
        updated["category"] = DISPLAY_CATEGORY.get(fields["category"].strip(), existing.get("category"))
    if _clean(fields.get("work_arrangement")):
        updated["work_arrangement"] = DISPLAY_ARRANGEMENT.get(
            fields["work_arrangement"].strip(), existing.get("work_arrangement")
        )
    if _clean(fields.get("ats")):
        updated["ats"] = DISPLAY_ATS.get(fields["ats"].strip(), existing.get("ats"))
    if _clean(fields.get("sponsorship")):
        updated["sponsorship"] = DISPLAY_SPONSORSHIP.get(
            fields["sponsorship"].strip(), existing.get("sponsorship")
        )

    active = _as_bool(fields.get("active"), None)
    if active is False:
        updated["active"] = False
        updated["date_inactive"] = utc_today()
    elif active is True:
        updated["active"] = True
        updated.pop("date_inactive", None)

    tailor = fields.get("tailor_recommended")
    if _clean(tailor):
        updated["tailor_recommended"] = _first_checkbox_checked(tailor)

    errors = validate_listing(updated)
    if errors:
        raise ContributionError("; ".join(errors))
    return updated


def parse_inactive_urls(value: str | None) -> list[str]:
    cleaned = _clean(value)
    if not cleaned:
        return []
    urls: list[str] = []
    for line in re.split(r"[\s,]+", cleaned):
        item = line.strip().strip("<>")
        if item.startswith("http://") or item.startswith("https://"):
            urls.append(item)
    return urls


def process_event(
    event: dict[str, Any],
    listings: list[dict[str, Any]],
    *,
    today: str | None = None,
) -> dict[str, Any]:
    issue = event.get("issue") or {}
    labels = {str(label.get("name")) for label in issue.get("labels") or []}
    if "approved" not in labels:
        raise ContributionError("Issue is not labeled approved.")

    body = issue.get("body") or ""
    user = (issue.get("user") or {}).get("login") or "github-actions"
    today = today or utc_today()

    if "new_listing" in labels:
        fields = map_fields(parse_issue_body(body), NEW_LISTING_FIELDS)
        listing = listing_from_new_issue(fields, today=today)
        duplicate = find_by_url(listings, listing["url"])
        if duplicate:
            if duplicate.get("active"):
                raise ContributionError(f"This URL is already listed ({duplicate['company']} — {duplicate['title']}).")
            duplicate.update(listing)
            duplicate["id"] = listing["id"]
            action = "reactivated"
        else:
            listings.append(listing)
            action = "added"
        email = _clean(fields.get("email"))
        return _result(
            action=action,
            listing=listing,
            user=user,
            email=email,
            message=f"{action.capitalize()} listing: {listing['company']} – {listing['title']}",
        )

    if "edit_listing" in labels:
        fields = map_fields(parse_issue_body(body), EDIT_LISTING_FIELDS)
        url = _clean(fields.get("url"))
        if not url:
            raise ContributionError("Existing job URL is required.")
        existing = find_by_url(listings, url)
        if not existing:
            raise ContributionError("No listing matched that URL.")
        updated = apply_edits(existing, fields)
        existing.clear()
        existing.update(updated)
        email = _clean(fields.get("email"))
        return _result(
            action="updated",
            listing=updated,
            user=user,
            email=email,
            message=f"Updated listing: {updated['company']} – {updated['title']}",
        )

    if "mark_inactive" in labels:
        fields = map_fields(parse_issue_body(body), MARK_INACTIVE_FIELDS)
        urls = parse_inactive_urls(fields.get("urls"))
        if not urls:
            raise ContributionError("Provide at least one job URL to mark inactive.")
        changed: list[dict[str, Any]] = []
        missing: list[str] = []
        for url in urls:
            existing = find_by_url(listings, url)
            if not existing:
                missing.append(url)
                continue
            if existing.get("active"):
                existing["active"] = False
                existing["date_inactive"] = today
                changed.append(existing)
        if missing and not changed:
            raise ContributionError("No listed URLs matched: " + ", ".join(missing))
        email = _clean(fields.get("email"))
        names = ", ".join(f"{item['company']} – {item['title']}" for item in changed) or "no open matches"
        return _result(
            action="marked_inactive",
            listing=changed[0] if changed else None,
            user=user,
            email=email,
            message=f"Marked inactive: {names}",
            extra={"changed": len(changed), "missing": missing},
        )

    raise ContributionError(
        "Approved issues need one of: new_listing, edit_listing, mark_inactive."
    )


def _result(
    *,
    action: str,
    listing: dict[str, Any] | None,
    user: str,
    email: str | None,
    message: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    payload = {
        "action": action,
        "listing": listing,
        "commit_username": user,
        "commit_email": email or "41898282+github-actions[bot]@users.noreply.github.com",
        "commit_message": message,
        "summary_comment": _summary_comment(action, listing, extra),
    }
    if extra:
        payload.update(extra)
    return payload


def _summary_comment(action: str, listing: dict[str, Any] | None, extra: dict[str, Any] | None) -> str:
    if action == "marked_inactive":
        missing = extra.get("missing") if extra else []
        changed = extra.get("changed") if extra else 0
        lines = [f"Marked **{changed}** listing(s) inactive and regenerated the README."]
        if missing:
            lines.append("Could not find: " + ", ".join(f"`{url}`" for url in missing))
        return "\n".join(lines)
    if not listing:
        return "Contribution processed."
    return (
        f"Accepted **{listing['company']} – {listing['title']}** (`{action}`).\n\n"
        f"The listing is in the README under **{listing.get('category')}**."
    )


def write_github_output(result: dict[str, Any], path: str | None = None) -> None:
    output_path = path or os.environ.get("GITHUB_OUTPUT")
    if not output_path:
        return
    keys = ("commit_username", "commit_email", "commit_message", "summary_comment")
    with Path(output_path).open("a", encoding="utf-8") as handle:
        for key in keys:
            value = str(result.get(key) or "")
            if "\n" in value:
                handle.write(f"{key}<<EOF\n{value}\nEOF\n")
            else:
                handle.write(f"{key}={value}\n")


def load_event(path: str | Path) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))
