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

Create these labels if they do not exist yet: `approved`, `new_listing`, `edit_listing`, `mark_inactive`, `misc`.

Approve a submission only after you have opened the apply URL and confirmed it is still accepting applications. Prefer marking inactive over deleting history.

Never wrap employer apply links through VeloApply. Promotion stays in the README CTA.

## Product documentation

Unrelated doc fixes for VeloApply itself can go in [docs/PRODUCT.md](docs/PRODUCT.md) via a pull request. For anything beyond a small text fix, open an issue first.
