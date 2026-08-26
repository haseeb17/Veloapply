"""Shared vocabulary for the community job list."""

from __future__ import annotations

CATEGORIES: dict[str, str] = {
    "software-engineering": "Software Engineering",
    "data-ml": "Data, AI & Machine Learning",
    "infrastructure": "Infrastructure & Platform",
    "security": "Security Engineering",
    "product": "Product Management",
    "design": "Design",
    "hardware": "Hardware & Systems",
}

LEVELS: dict[str, str] = {
    "mid": "Mid",
    "senior": "Senior",
    "staff": "Staff",
    "principal": "Principal",
    "lead": "Lead",
    "manager": "Manager",
}

WORK_ARRANGEMENTS: dict[str, str] = {
    "remote": "Remote",
    "hybrid": "Hybrid",
    "onsite": "Onsite",
}

ATS_PLATFORMS: dict[str, str] = {
    "greenhouse": "Greenhouse",
    "lever": "Lever",
    "ashby": "Ashby",
    "workday": "Workday",
    "icims": "iCIMS",
    "smartrecruiters": "SmartRecruiters",
    "taleo": "Taleo",
    "bamboohr": "BambooHR",
    "other": "Other",
}

SPONSORSHIP: dict[str, str] = {
    "offers": "Offers sponsorship",
    "does-not-offer": "No sponsorship",
    "us-citizenship-required": "U.S. citizenship required",
    "unknown": "Unknown",
}

VELOAPPLY_SUPPORTED_ATS = {
    "greenhouse",
    "lever",
    "ashby",
    "workday",
    "icims",
    "smartrecruiters",
    "taleo",
    "bamboohr",
}

ATS_DISPLAY_ORDER = (
    "workday",
    "greenhouse",
    "lever",
    "ashby",
    "icims",
    "smartrecruiters",
    "taleo",
    "bamboohr",
    "other",
)

ARRANGEMENT_EMOJI = {
    "remote": "🏠",
    "hybrid": "🏢",
    "onsite": "📍",
}

TAILOR_EMOJI = "🎯"
CITIZENSHIP_EMOJI = "🇺🇸"

LISTINGS_PATH = "data/listings.json"
COMPANIES_PATH = "data/companies.json"
README_PATH = "README.md"
ATS_PATH = "ATS.md"
README_TEMPLATE_PATH = "templates/README.template.md"
ATS_TEMPLATE_PATH = "templates/ATS.template.md"

REQUIRED_LISTING_FIELDS = (
    "id",
    "company",
    "title",
    "category",
    "level",
    "locations",
    "work_arrangement",
    "ats",
    "url",
    "active",
    "date_added",
)

# Issue form heading -> listing field
NEW_LISTING_FIELDS = {
    "Link to Job Posting": "url",
    "Company Name": "company",
    "Company Website": "company_url",
    "Role Title": "title",
    "Location": "locations",
    "Experience Level": "level",
    "Category": "category",
    "Work Arrangement": "work_arrangement",
    "ATS / Application Platform": "ats",
    "Visa Sponsorship": "sponsorship",
    "Is this role currently accepting applications?": "active",
    "Custom screening or tailored application?": "tailor_recommended",
    "Date Posted": "date_posted",
    "Email associated with your GitHub account (Optional)": "email",
    "Extra Notes (Optional)": "notes",
}

EDIT_LISTING_FIELDS = {
    "Existing Job URL": "url",
    "Updated Job URL": "new_url",
    "Company Name": "company",
    "Company Website": "company_url",
    "Role Title": "title",
    "Location": "locations",
    "Experience Level": "level",
    "Category": "category",
    "Work Arrangement": "work_arrangement",
    "ATS / Application Platform": "ats",
    "Visa Sponsorship": "sponsorship",
    "Is this role currently accepting applications?": "active",
    "Custom screening or tailored application?": "tailor_recommended",
    "Date Posted": "date_posted",
    "Email associated with your GitHub account (Optional)": "email",
    "What should we change?": "notes",
}

MARK_INACTIVE_FIELDS = {
    "Job URL(s) to mark inactive": "urls",
    "Why is it inactive?": "reason",
    "Email associated with your GitHub account (Optional)": "email",
}

DISPLAY_LEVEL = {
    "Mid-level": "mid",
    "Senior": "senior",
    "Staff": "staff",
    "Principal": "principal",
    "Lead": "lead",
    "Engineering Manager": "manager",
}

DISPLAY_CATEGORY = {
    "Software Engineering": "software-engineering",
    "Data, AI & Machine Learning": "data-ml",
    "Infrastructure & Platform": "infrastructure",
    "Security Engineering": "security",
    "Product Management": "product",
    "Design": "design",
    "Hardware & Systems": "hardware",
}

DISPLAY_ARRANGEMENT = {
    "Remote": "remote",
    "Hybrid": "hybrid",
    "Onsite": "onsite",
}

DISPLAY_ATS = {
    "Greenhouse": "greenhouse",
    "Lever": "lever",
    "Ashby": "ashby",
    "Workday": "workday",
    "iCIMS": "icims",
    "SmartRecruiters": "smartrecruiters",
    "Taleo": "taleo",
    "BambooHR": "bamboohr",
    "Other / company site": "other",
}

DISPLAY_SPONSORSHIP = {
    "Offers sponsorship": "offers",
    "Does not offer sponsorship": "does-not-offer",
    "U.S. citizenship is required": "us-citizenship-required",
    "Unknown / not listed": "unknown",
}

EXTENSION_URL = (
    "https://chromewebstore.google.com/detail/agpginkiklnhcigiecpfemiflebnhnfj"
)
SITE_URL = "https://veloapply.com/?utm_source=github&utm_medium=community_list&utm_campaign=readme"
EXTENSION_UTM_URL = (
    "https://chromewebstore.google.com/detail/agpginkiklnhcigiecpfemiflebnhnfj"
    "?utm_source=github&utm_medium=community_list&utm_campaign=readme"
)
