from __future__ import annotations

import re
import unicodedata
from typing import Any


DANGEROUS_CATEGORY = "Dangerous Content"

HARM_FAMILY_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "dangerous_stunt_or_challenge": (
        re.compile(r"\b(?:dangerous|life[ -]?threatening)\s+(?:stunt|challenge)\b"),
        re.compile(r"\bjump\s+from\s+(?:the\s+)?roof\b"),
    ),
    "hazardous_experiment_or_explosion": (
        re.compile(r"\bdangerous\s+experiment\s+at\s+home\b"),
        re.compile(r"\b(?:make\s+an?\s+explosive|cause\s+an?\s+explosion)\b"),
        re.compile(r"\binstructions?\s+(?:to|for)\s+make\s+an?\s+explosive\b"),
        re.compile(r"\binstructions?\s+(?:to|for)\s+cause\s+bodily\s+harm\b"),
        re.compile(r"\b(?:do\s+not|don't)\s+use\s+safety\s+equipment\b"),
    ),
    "dangerous_self_other_or_property_action": (
        re.compile(r"\b(?:harm|hurt)\s+yourself\b"),
        re.compile(r"\bset\s+(?:yourself|oneself)\s+on\s+fire\b"),
        re.compile(r"\bdestroy\s+(?:their|your|one's)\s+property\s+dangerously\b"),
        re.compile(r"\bchallenge\s+can\s+kill\s+you\b"),
    ),
}

ADVOCACY_PATTERN = re.compile(
    r"\b(?:urge|urges|tell|tells|ask|asks|dare|dares|encourage|encourages|"
    r"promote|promotes|order|orders|advertise|advertises|offer|offers|"
    r"copy|try|perform|do|instruction|instructions|tutorial|challenge)\b"
)

SAFE_REPORTING_PATTERNS = (
    re.compile(r"\b(?:safety\s+video|news\s+report|school\s+lesson|public\s+notice)\b"),
    re.compile(r"\b(?:warn|warns|warning|condemn|condemns|discourage|discouraged)\b"),
    re.compile(r"\b(?:must\s+not|should\s+not|never|not\s+to)\b"),
    re.compile(r"\b(?:prevention|public\s+education|safety\s+advice)\b"),
    re.compile(r"\bno\s+encouragement\s+to\s+imitate\b"),
)

PROFESSIONAL_CONTROL_PATTERNS = (
    re.compile(r"\blicensed\s+stunt\s+team\b"),
    re.compile(r"\b(?:chemistry\s+instructor|firefighters?|engineering\s+class|workplace\s+trainer)\b"),
    re.compile(r"\b(?:certified\s+laboratory|secured\s+training\s+area)\b"),
    re.compile(r"\bqualified\s+professionals?\s+supervise\b"),
    re.compile(r"\b(?:protective\s+controls|emergency\s+procedures)\b"),
    re.compile(r"\bcontrolled\s+demonstration\s+with\s+protective\s+equipment\b"),
)

UNSAFE_ABSENCE_PATTERNS = (
    re.compile(r"\bwithout\s+(?:appropriate\s+)?professional\s+supervision\b"),
    re.compile(r"\bno\s+(?:protective\s+controls?|safety\s+equipment|warning|controlled\s+setting)\b"),
    re.compile(r"\b(?:untrained\s+viewers?|rather\s+than\s+trained\s+professionals?)\b"),
    re.compile(r"\bno\s+prevention(?:,\s*reporting)?(?:,?\s*or\s+condemnation)?\s+context\b"),
    re.compile(r"\brather\s+than\s+educational\b"),
    re.compile(r"\b(?:encourages?\s+imitation|asks?\s+the\s+audience\s+to\s+repeat)\b"),
    re.compile(r"\b(?:do\s+not|don't)\s+use\s+safety\s+equipment\b"),
    re.compile(r"\bpromotes?\s+it\s+anyway\b"),
)


def normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return re.sub(r"\s+", " ", normalized).strip()


def matching_families(normalized: str) -> list[str]:
    return [
        family
        for family, patterns in HARM_FAMILY_PATTERNS.items()
        if any(pattern.search(normalized) for pattern in patterns)
    ]


def any_match(patterns: tuple[re.Pattern[str], ...], text: str) -> bool:
    return any(pattern.search(text) for pattern in patterns)


def analyze_dangerous_content_v2(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    families = matching_families(normalized)
    unsafe_absence = any_match(UNSAFE_ABSENCE_PATTERNS, normalized)
    safe_reporting = any_match(SAFE_REPORTING_PATTERNS, normalized)
    professional_control = any_match(PROFESSIONAL_CONTROL_PATTERNS, normalized)
    direct_advocacy = bool(ADVOCACY_PATTERN.search(normalized))

    if unsafe_absence:
        safe_reporting = False
        professional_control = False

    safe_veto = safe_reporting or professional_control
    violation = bool(families) and direct_advocacy and not safe_veto

    if violation:
        confidence = min(0.94, 0.84 + (0.03 * len(families)))
        return {
            "available": True,
            "candidate": "dangerous-content-v2-boundary",
            "category": DANGEROUS_CATEGORY,
            "status": "dangerous_behavior_review_required",
            "confidence": round(confidence, 2),
            "action": "Remove and send for human review",
            "human_review_required": True,
            "harm_families": families,
            "direct_advocacy_detected": direct_advocacy,
            "safe_context_veto": False,
            "unsafe_absence_detected": unsafe_absence,
            "automatic_enforcement_allowed": False,
            "connected_to_live_moderation": False,
        }

    if safe_veto and families:
        status = (
            "professional_control_no_override"
            if professional_control
            else "safe_reporting_prevention_no_override"
        )
    elif families:
        status = "insufficient_advocacy_evidence_no_override"
    else:
        status = "no_dangerous_signal"

    return {
        "available": True,
        "candidate": "dangerous-content-v2-boundary",
        "category": None,
        "status": status,
        "confidence": 0.0,
        "action": "No boundary override",
        "human_review_required": False,
        "harm_families": families,
        "direct_advocacy_detected": direct_advocacy,
        "safe_context_veto": safe_veto,
        "unsafe_absence_detected": unsafe_absence,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }


def get_dangerous_content_v2_status() -> dict[str, Any]:
    return {
        "available": True,
        "candidate": "dangerous-content-v2-boundary",
        "permitted_active_category": DANGEROUS_CATEGORY,
        "preserves_other_category_owners": True,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "independently_validated": False,
    }
