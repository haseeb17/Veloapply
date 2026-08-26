# Contributing

This repository is the public, community-maintained **experienced tech job list** for VeloApply. The production app, Chrome extension, and AI systems stay in private repositories.

The list only works if it stays accurate. That means currently open roles, real career-site URLs, and no internships.

## What belongs here

Add a role when all of this is true:

- It is a **mid-level, senior, staff, principal, lead, or manager** role.
- Applications are **currently open**.
- The apply link is the **company career site or ATS** (Greenhouse, Lever, Ashby, Workday, iCIMS, SmartRecruiters, Taleo, BambooHR, or the company's own portal).
- You would actually apply there yourself.

## What does not belong here

- Internships, co-ops, new-grad, and university programs. Use [SimplifyJobs/Summer2027-Internships](https://github.com/SimplifyJobs/Summer2027-Internships) or [SimplifyJobs/New-Grad-Positions](https://github.com/SimplifyJobs/New-Grad-Positions).
- LinkedIn Easy Apply, Indeed, Glassdoor, ZipRecruiter, or other aggregators.
- Roles that are already in the README under the same apply URL.
- Closed, guessed, or "might open soon" postings.

This is intentional. Simplify already owns the internship/new-grad GitHub lists. Competing there is expensive and undifferentiated. This list is the quality-and-ATS angle: experienced roles on forms VeloApply can actually fill.

## How to add or change a listing

Do not edit `README.md` by hand. Open an issue:

| You want to | Open |
| --- | --- |
| Add a role | [New role](https://github.com/haseeb17/Veloapply/issues/new?template=new-listing.yml) |
| Fix details | [Edit role](https://github.com/haseeb17/Veloapply/issues/new?template=edit-listing.yml) |
| Close a role | [Mark inactive](https://github.com/haseeb17/Veloapply/issues/new?template=mark-inactive.yml) |
| Something else | [Misc](https://github.com/haseeb17/Veloapply/issues/new?template=misc.yml) |

A maintainer reviews the posting, then adds the `approved` label. GitHub Actions appends `data/listings.json`, regenerates the README, and closes the issue.

If you want commit attribution, include the email on your GitHub account in the form. Otherwise the change is committed as the Actions bot.

## Local preview (maintainers)

Python 3.12+, no third-party packages.

```bash
export PYTHONPATH=.
python3 -m unittest discover -s tests -v
python3 -m tools.cli validate
python3 -m tools.cli generate
```

Source of truth:

- `data/listings.json` — roles
- `data/companies.json` — ATS directory used by [ATS.md](ATS.md)
- `templates/` — README and ATS copy
- `tools/` — validation, issue parsing, markdown generation

## Maintainer notes

Labels (`approved`, `new_listing`, `edit_listing`, `mark_inactive`, `misc`) are created automatically on push to `main` by `.github/workflows/sync-labels.yml`. You can also run **Actions → Sync labels**.

Approve a submission only after you have opened the apply URL and confirmed it is still accepting applications. Prefer marking inactive over deleting history.

Never wrap employer apply links through VeloApply. Promotion stays in the README CTA.

### GitHub About (one-time, repo Settings)

The agent token cannot change GitHub UI settings. After this branch is on `main`, set these in **Settings → General**:

| Field | Value |
| --- | --- |
| Description | Community-maintained list of experienced tech jobs on real ATS career sites (Workday, Greenhouse, Lever, Ashby, iCIMS). Not internships. |
| Website | `https://veloapply.com` |
| Topics | `job-list` `remote-jobs` `software-engineer-jobs` `workday` `greenhouse` `lever` `ashby` `ats` `job-search` `chrome-extension` |
| Features | Issues on. Wiki off. Projects off. |

Pin this repository on https://github.com/haseeb17 so it is the first thing people see.

### Sister repo

[`awesome-ai-job-search-tools`](https://github.com/haseeb17/awesome-ai-job-search-tools) should link back here. Add a **Job lists** section:

```md
## Job lists

- [Experienced Tech Jobs (2026)](https://github.com/haseeb17/Veloapply) - Community list of mid/senior/staff roles on real ATS career sites. Not internships.
```

## Product documentation

Unrelated doc fixes for VeloApply itself can go in [docs/PRODUCT.md](docs/PRODUCT.md) via a pull request. For anything beyond a small text fix, open an issue first.

By contributing, you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).
