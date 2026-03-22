from __future__ import annotations

import re
from typing import Optional, Set

from .models import Scholarship


_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def _norm(s: str) -> str:
    return _NON_ALNUM_RE.sub(" ", (s or "").lower()).strip()


def infer_categories_from_text(text: str) -> Set[str]:
    """
    Map common search terms like "engineering", "medical", "law" to Scholarship.category values.
    This allows keyword search to behave like category search.
    """
    t = _norm(text)
    if not t:
        return set()

    categories: Set[str] = set()
    words = set(t.split())

    def has_any(*needles: str) -> bool:
        return any(n in words for n in needles)

    if has_any("engineering", "engineer", "tech", "technology", "stem", "software", "computer", "computing", "it"):
        categories.add(Scholarship.CATEGORY_STEM)

    if has_any("medical", "medicine", "health", "nursing", "pharmacy", "clinical", "hospital"):
        categories.add(Scholarship.CATEGORY_MEDICINE)

    if has_any("law", "legal", "lawyer", "attorney", "jurisprudence"):
        categories.add(Scholarship.CATEGORY_LAW)

    if has_any("business", "finance", "accounting", "economics", "entrepreneurship", "mba"):
        categories.add(Scholarship.CATEGORY_BUSINESS)

    if has_any("education", "teaching", "teacher", "school", "pedagogy"):
        categories.add(Scholarship.CATEGORY_EDUCATION)

    if has_any("arts", "art", "humanities", "history", "literature", "philosophy"):
        categories.add(Scholarship.CATEGORY_ARTS)

    if has_any("social", "society", "sociology", "politics", "policy", "governance", "development", "community"):
        categories.add(Scholarship.CATEGORY_SOCIAL)

    # Handle a few common phrases.
    if "computer science" in t or "information technology" in t:
        categories.add(Scholarship.CATEGORY_STEM)

    return categories


def infer_levels_from_text(text: str) -> Set[str]:
    """
    Map free-text terms like "degree", "diploma", "masters", "phd" to Scholarship.level values.
    """
    t = _norm(text)
    if not t:
        return set()

    levels: Set[str] = set()
    words = set(t.split())

    def has_any(*needles: str) -> bool:
        return any(n in words for n in needles)

    if has_any("degree", "undergraduate", "bachelor", "bachelors", "bsc", "ba", "beng"):
        levels.add(Scholarship.LEVEL_UNDERGRADUATE)

    if has_any("diploma", "dip"):
        levels.add(Scholarship.LEVEL_DIPLOMA)

    if has_any("certificate", "cert"):
        levels.add(Scholarship.LEVEL_CERTIFICATE)

    if has_any("masters", "master", "msc", "ma", "mba", "meng"):
        levels.add(Scholarship.LEVEL_MASTERS)

    if has_any("phd", "ph", "doctorate", "doctoral"):
        levels.add(Scholarship.LEVEL_PHD)

    if has_any("postdoc", "postdoctoral"):
        levels.add(Scholarship.LEVEL_POSTDOC)

    return levels


def infer_level_for_scholarship(*, title: str, description: str, requirements: str) -> Optional[str]:
    """
    Best-effort level assignment for demo data. If no signal is present, return None.
    """
    text = " ".join([title or "", description or "", requirements or ""])
    inferred = infer_levels_from_text(text)
    if not inferred:
        return None

    # Pick the most specific level when multiple are present.
    priority = [
        Scholarship.LEVEL_POSTDOC,
        Scholarship.LEVEL_PHD,
        Scholarship.LEVEL_MASTERS,
        Scholarship.LEVEL_DIPLOMA,
        Scholarship.LEVEL_CERTIFICATE,
        Scholarship.LEVEL_UNDERGRADUATE,
    ]
    for lvl in priority:
        if lvl in inferred:
            return lvl
    return next(iter(inferred))


def infer_category_for_scholarship(*, title: str, organization: str) -> Optional[str]:
    """
    Best-effort category assignment for seeded/demo data.
    Prefer title keywords, fall back to organization-based heuristics.
    """
    t = _norm(title)
    o = (organization or "").strip()
    o_norm = _norm(organization)
    words = set(t.split())

    # Title-based signals (highest priority).
    if "law" in words or "legal" in words:
        return Scholarship.CATEGORY_LAW
    if {"medical", "medicine", "health", "nursing", "pharmacy", "clinical"} & words:
        return Scholarship.CATEGORY_MEDICINE
    if {"education", "teacher", "teaching", "school", "pedagogy"} & words:
        return Scholarship.CATEGORY_EDUCATION
    if {"business", "finance", "mba", "accounting", "economics", "entrepreneurship"} & words:
        return Scholarship.CATEGORY_BUSINESS
    if {"arts", "art", "humanities", "literature", "history", "philosophy"} & words:
        return Scholarship.CATEGORY_ARTS
    if {"tech", "technology", "stem", "engineering", "innovator", "innovators", "software", "computer", "computing"} & words:
        return Scholarship.CATEGORY_STEM
    if {"community", "development", "leadership", "impact", "policy", "governance"} & words:
        return Scholarship.CATEGORY_SOCIAL

    # Organization-based signals (fallback for synthetic data).
    org_map = {
        "Microsoft": Scholarship.CATEGORY_STEM,
        "Google": Scholarship.CATEGORY_STEM,
        "Facebook": Scholarship.CATEGORY_STEM,
        "MIT": Scholarship.CATEGORY_STEM,
        "UNICEF": Scholarship.CATEGORY_MEDICINE,
        "Bill & Melinda Gates Foundation": Scholarship.CATEGORY_MEDICINE,
        "World Bank": Scholarship.CATEGORY_BUSINESS,
        "Mastercard Foundation": Scholarship.CATEGORY_BUSINESS,
        "Kenya Government": Scholarship.CATEGORY_EDUCATION,
        "Government of Kenya": Scholarship.CATEGORY_EDUCATION,
        "Oxford University": Scholarship.CATEGORY_EDUCATION,
        "Harvard University": Scholarship.CATEGORY_EDUCATION,
        "African Union": Scholarship.CATEGORY_LAW,
        "United Nations": Scholarship.CATEGORY_LAW,
        "Commonwealth Scholarship Commission": Scholarship.CATEGORY_EDUCATION,
    }
    if o in org_map:
        return org_map[o]

    # Gentle substring fallbacks (handles slight org naming differences).
    if "unicef" in o_norm or "gates" in o_norm:
        return Scholarship.CATEGORY_MEDICINE
    if "government" in o_norm:
        return Scholarship.CATEGORY_EDUCATION
    if "united nations" in o_norm or "african union" in o_norm:
        return Scholarship.CATEGORY_LAW

    return None
