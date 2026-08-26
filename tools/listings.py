"""Load, save, and mutate listing records."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

from tools.constants import (
    ATS_PLATFORMS,
    CATEGORIES,
    COMPANIES_PATH,
    LEVELS,
    LISTINGS_PATH,
    REQUIRED_LISTING_FIELDS,
    SPONSORSHIP,
    WORK_ARRANGEMENTS,
)

EMPTY_OPTIONAL = {"", "_no response_", "n/a", "na", "none", "-"}


def utc_today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def load_json(path: str | Path) -> Any:
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def save_json(path: str | Path, payload: Any) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    path.write_text(serialized, encoding="utf-8")


def load_listings(path: str | Path = LISTINGS_PATH) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError("listings.json must be a JSON array")
    return data


def save_listings(listings: list[dict[str, Any]], path: str | Path = LISTINGS_PATH) -> None:
    ordered = sorted(
        listings,
        key=lambda item: (
            0 if item.get("active") else 1,
            item.get("category") or "",
            (item.get("company") or "").lower(),
            (item.get("title") or "").lower(),
        ),
    )
    save_json(path, ordered)


def load_companies(path: str | Path = COMPANIES_PATH) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError("companies.json must be a JSON array")
    return data


def listing_id_for_url(url: str) -> str:
    return hashlib.sha1(normalize_url(url).encode("utf-8")).hexdigest()[:12]


def canonical_url(url: str) -> str:
    raw = (url or "").strip()
    if not raw.startswith("http://") and not raw.startswith("https://"):
        raw = "https://" + raw
    return raw


def normalize_url(url: str) -> str:
    parsed = urlparse(canonical_url(url))
    scheme = parsed.scheme.lower() if parsed.scheme else "https"
    netloc = parsed.netloc.lower().removeprefix("www.")
    path = parsed.path.rstrip("/")
    return urlunparse((scheme, netloc, path, "", parsed.query, ""))


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and value.strip().lower() in EMPTY_OPTIONAL:
        return True
    return False


def split_locations(value: Any) -> list[str]:
    if isinstance(value, list):
        parts = value
    else:
        text = str(value or "")
        parts = re.split(r"\s*\|\s*", text)
    cleaned = [re.sub(r"\s+", " ", part).strip() for part in parts]
    return [part for part in cleaned if part]


def listing_sort_key(item: dict[str, Any]) -> tuple:
    added = item.get("date_posted") or item.get("date_added") or ""
    return (0 if item.get("active") else 1, added, item.get("company") or "")


def find_by_url(listings: list[dict[str, Any]], url: str) -> dict[str, Any] | None:
    target = normalize_url(url)
    for listing in listings:
        if normalize_url(str(listing.get("url") or "")) == target:
            return listing
    return None


def validate_listing(listing: dict[str, Any], *, require_id: bool = True) -> list[str]:
    errors: list[str] = []
    fields = REQUIRED_LISTING_FIELDS if require_id else [f for f in REQUIRED_LISTING_FIELDS if f != "id"]
    for field in fields:
        if field not in listing or is_blank(listing.get(field)) and field != "active":
            if field == "active" and listing.get("active") in (True, False):
                continue
            errors.append(f"missing {field}")

    if listing.get("category") not in CATEGORIES:
        errors.append(f"invalid category: {listing.get('category')}")
    if listing.get("level") not in LEVELS:
        errors.append(f"invalid level: {listing.get('level')}")
    if listing.get("work_arrangement") not in WORK_ARRANGEMENTS:
        errors.append(f"invalid work_arrangement: {listing.get('work_arrangement')}")
    if listing.get("ats") not in ATS_PLATFORMS:
        errors.append(f"invalid ats: {listing.get('ats')}")
    sponsorship = listing.get("sponsorship", "unknown")
    if sponsorship not in SPONSORSHIP:
        errors.append(f"invalid sponsorship: {sponsorship}")
    if listing.get("active") not in (True, False):
        errors.append("active must be a boolean")
    locations = listing.get("locations")
    if not isinstance(locations, list) or not locations:
        errors.append("locations must be a non-empty list")
    url = str(listing.get("url") or "")
    parsed = urlparse(url if "://" in url else f"https://{url}")
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        errors.append("url must be an http(s) link")
    if _looks_like_aggregator(url):
        errors.append("url must point at the company career site or ATS board, not a job aggregator")
    if _looks_like_internship(listing):
        errors.append("internships, co-ops, and new-grad programs are out of scope")
    for date_field in ("date_added", "date_posted", "date_inactive"):
        value = listing.get(date_field)
        if not is_blank(value):
            try:
                date.fromisoformat(str(value))
            except ValueError:
                errors.append(f"{date_field} must be YYYY-MM-DD")
    return errors


def validate_listings(listings: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    for index, listing in enumerate(listings):
        prefix = f"listings[{index}]"
        for error in validate_listing(listing):
            errors.append(f"{prefix}: {error}")
        listing_id = listing.get("id")
        if listing_id in seen_ids:
            errors.append(f"{prefix}: duplicate id {listing_id}")
        seen_ids.add(listing_id)
        url_key = normalize_url(str(listing.get("url") or ""))
        if url_key in seen_urls:
            errors.append(f"{prefix}: duplicate url {listing.get('url')}")
        seen_urls.add(url_key)
    return errors


def validate_company(company: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if is_blank(company.get("name")):
        errors.append("missing name")
    if company.get("ats") not in ATS_PLATFORMS:
        errors.append(f"invalid ats: {company.get('ats')}")
    if is_blank(company.get("careers_url")):
        errors.append("missing careers_url")
    return errors


def _looks_like_aggregator(url: str) -> bool:
    host = urlparse(url if "://" in url else f"https://{url}").netloc.lower()
    blocked = (
        "linkedin.com",
        "indeed.com",
        "glassdoor.com",
        "ziprecruiter.com",
        "monster.com",
        "simplyhired.com",
        "wellfound.com",
        "angel.co",
        "levels.fyi",
        "builtin.com",
        "dice.com",
    )
    return any(host == item or host.endswith("." + item) for item in blocked)


def _looks_like_internship(listing: dict[str, Any]) -> bool:
    blob = " ".join(
        str(listing.get(field) or "")
        for field in ("title", "level", "notes")
    )
    return re.search(
        r"\b(interns?|internship|co-ops?|coops?|new[\s-]?grads?|university grads?|early career program)\b",
        blob,
        flags=re.IGNORECASE,
    ) is not None
