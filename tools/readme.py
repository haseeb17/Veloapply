"""Render README.md and ATS.md from listing data."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from tools.constants import (
    ARRANGEMENT_EMOJI,
    ATS_DISPLAY_ORDER,
    ATS_PATH,
    ATS_PLATFORMS,
    ATS_TEMPLATE_PATH,
    CATEGORIES,
    CITIZENSHIP_EMOJI,
    EXTENSION_UTM_URL,
    LEVELS,
    README_PATH,
    README_TEMPLATE_PATH,
    TAILOR_EMOJI,
    VELOAPPLY_SUPPORTED_ATS,
    WORK_ARRANGEMENTS,
)
from tools.listings import load_companies, load_listings

TABLE_COLUMNS = ["Company", "Role", "Level", "Location", "ATS", "Posted"]


def generate_readme(
    listings: list[dict[str, Any]] | None = None,
    *,
    generated_at: str | None = None,
) -> str:
    listings = listings if listings is not None else load_listings()
    generated_at = generated_at or datetime.now(timezone.utc).strftime("%Y-%m-%d")
    active = [item for item in listings if item.get("active")]
    inactive = [item for item in listings if not item.get("active")]

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in active:
        grouped[item["category"]].append(item)

    toc_lines = []
    section_parts = []
    for category_id, label in CATEGORIES.items():
        rows = grouped.get(category_id, [])
        if not rows:
            continue
        anchor = _anchor(label)
        toc_lines.append(f"- [{label}](#{anchor}) ({len(rows)})")
        sorted_rows = sorted(rows, key=_row_sort)
        section_parts.append(f"### {label}\n")
        section_parts.append(_table(sorted_rows))
        section_parts.append("")

    inactive_section = "_No inactive listings yet._"
    if inactive:
        closed = sorted(inactive, key=_row_sort, reverse=True)[:50]
        inactive_section = (
            "<details>\n"
            "<summary>Recently closed or filled roles</summary>\n\n"
            f"{_table(closed)}\n"
            "</details>"
        )

    supported = [
        ATS_PLATFORMS[key]
        for key in ATS_DISPLAY_ORDER
        if key in VELOAPPLY_SUPPORTED_ATS and key in ATS_PLATFORMS
    ]
    supported_text = ", ".join(supported[:-1]) + f", and {supported[-1]}" if len(supported) > 1 else (supported[0] if supported else "")
    template = Path(README_TEMPLATE_PATH).read_text(encoding="utf-8")
    return (
        template.replace("{{GENERATED_AT}}", generated_at)
        .replace("{{ACTIVE_COUNT}}", str(len(active)))
        .replace("{{COMPANY_COUNT}}", str(len({item["company"] for item in active})))
        .replace("{{CATEGORY_TOC}}", "\n".join(toc_lines) or "- _No active listings yet. Open an issue to add one._")
        .replace("{{CATEGORY_SECTIONS}}", "\n".join(section_parts).rstrip() or "_No active listings yet._")
        .replace("{{INACTIVE_SECTION}}", inactive_section)
        .replace("{{SUPPORTED_ATS}}", supported_text)
        .replace("{{LEGEND}}", _legend())
        .replace("{{EXTENSION_PLACEHOLDER}}", EXTENSION_UTM_URL)
    )


def generate_ats_guide(companies: list[dict[str, Any]] | None = None) -> str:
    companies = companies if companies is not None else load_companies()
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for company in companies:
        grouped[company["ats"]].append(company)

    parts: list[str] = []
    for ats_id in ATS_DISPLAY_ORDER:
        label = ATS_PLATFORMS.get(ats_id)
        rows = grouped.get(ats_id, [])
        if not label or not rows:
            continue
        parts.append(f"### {label}\n")
        parts.append("| Company | Careers | VeloApply autofill |")
        parts.append("| --- | --- | --- |")
        for company in sorted(rows, key=lambda item: item["name"].lower()):
            name = _md_link(company["name"], company.get("website"))
            careers = _md_link("Open jobs", company["careers_url"])
            supported = "Yes" if ats_id in VELOAPPLY_SUPPORTED_ATS else "—"
            parts.append(f"| {name} | {careers} | {supported} |")
        parts.append("")

    template = Path(ATS_TEMPLATE_PATH).read_text(encoding="utf-8")
    return template.replace("{{ATS_SECTIONS}}", "\n".join(parts).rstrip())


def write_generated_docs(
    listings: list[dict[str, Any]] | None = None,
    companies: list[dict[str, Any]] | None = None,
    *,
    generated_at: str | None = None,
) -> None:
    Path(README_PATH).write_text(generate_readme(listings, generated_at=generated_at), encoding="utf-8")
    Path(ATS_PATH).write_text(generate_ats_guide(companies), encoding="utf-8")


def _legend() -> str:
    arrangement = " · ".join(
        f"{ARRANGEMENT_EMOJI[key]} {label}" for key, label in WORK_ARRANGEMENTS.items()
    )
    return (
        f"{arrangement} · {TAILOR_EMOJI} tailored application recommended "
        f"(custom screening questions, cover letter, or long Workday form) · "
        f"{CITIZENSHIP_EMOJI} U.S. citizenship required"
    )


def _table(rows: list[dict[str, Any]]) -> str:
    lines = [
        "| " + " | ".join(TABLE_COLUMNS) + " |",
        "| " + " | ".join("---" for _ in TABLE_COLUMNS) + " |",
    ]
    for item in rows:
        lines.append("| " + " | ".join(_row_cells(item)) + " |")
    return "\n".join(lines)


def _row_cells(item: dict[str, Any]) -> list[str]:
    company = _escape(_md_link(item["company"], item.get("company_url")))
    title = _escape(item["title"])
    if item.get("tailor_recommended"):
        title = f"{title} {TAILOR_EMOJI}"
    if item.get("sponsorship") == "us-citizenship-required":
        title = f"{title} {CITIZENSHIP_EMOJI}"
    role = f"[{title}]({item['url']})"
    level = LEVELS.get(item.get("level"), item.get("level") or "")
    emoji = ARRANGEMENT_EMOJI.get(item.get("work_arrangement"), "")
    location = _escape(f"{emoji} {', '.join(item.get('locations') or [])}".strip())
    ats = ATS_PLATFORMS.get(item.get("ats"), item.get("ats") or "")
    posted = _posted_label(item)
    return [company, role, level, location, ats, posted]


def _posted_label(item: dict[str, Any]) -> str:
    raw = item.get("date_posted") or item.get("date_added")
    if not raw:
        return "—"
    try:
        parsed = date.fromisoformat(str(raw))
    except ValueError:
        return str(raw)
    return parsed.strftime("%b %d")


def _row_sort(item: dict[str, Any]) -> tuple:
    posted = item.get("date_posted") or item.get("date_added") or ""
    return (posted, (item.get("company") or "").lower(), (item.get("title") or "").lower())


def _md_link(label: str, url: str | None) -> str:
    if url:
        return f"[{_escape(label)}]({url})"
    return _escape(label)


def _escape(value: str) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _anchor(label: str) -> str:
    text = label.lower()
    text = "".join(ch if ch.isalnum() else "-" for ch in text)
    return "-".join(part for part in text.split("-") if part)
