from __future__ import annotations

import re

from app.services.terrorism_extremism_service import (
    NORMAL_CATEGORY,
    TERRORISM_CATEGORY,
    UNCERTAIN_CATEGORY,
    normalize_text,
)
from app.services.terrorism_extremism_v4_rc2_service import has_any
from app.services.terrorism_extremism_v5_rc3_service import (
    DESIGNATION_NEGATION,
    ORGANIZATION_TERMS,
    SAFE_STANCE_PATTERNS,
    SOURCE_CONTEXT_PATTERNS,
    TERROR_STATUS_TERMS,
    analyze_terrorism_extremism_v5_rc3,
    broad_claimed_designation,
)


RC4_SOURCE_CONTEXT_PATTERNS = SOURCE_CONTEXT_PATTERNS + (
    r"\b(?:college|institute|institution|university)\s+"
    r"(?:analysis|paper|project|publication|report|research|study)\b",
    r"\b(?:civil society|human rights|policy)\s+"
    r"(?:analysis|brief|paper|report|review|study)\b",
)

RC4_BEHAVIOR_PATTERNS = {
    "recruitment_or_membership": (
        r"\b(?:encourage|encourages|encouraged|encouraging|invite|invites|"
        r"invited|inviting|open|opens|opened|opening)\b.{0,40}"
        r"\b(?:membership|registration)\b",
        r"\bregistration\s+(?:by|for|of|with)\s+(?:new\s+)?(?:members?|people|users?)\b",
    ),
    "funding_or_operational_support": (
        r"\b(?:ask|asks|asked|asking|request|requests|requested|requesting|"
        r"collect|collects|collected|collecting|solicit|solicits|solicited|"
        r"soliciting)\b.{0,35}\b(?:contributions?|donations?|funds?|money|payments?)\b",
        r"\b(?:arrange|arranges|arranged|arranging|provide|provides|provided|"
        r"providing)\b.{0,35}\b(?:logistical assistance|logistics|safe houses?|"
        r"supplies|transport)\b",
    ),
    "propaganda_distribution": (
        r"\b(?:circulate|circulates|circulated|circulating|forward|forwards|"
        r"forwarded|forwarding)\b.{0,45}\b(?:propaganda|recruitment content|"
        r"recruitment material|recruitment messages?|recruitment posts?)\b",
    ),
}

UNCERTAINTY_TERMS = re.compile(
    r"\b(?:alleged|possible|purported|suspected|uncertain|unconfirmed|"
    r"unknown|unverified|not authenticated|not confirmed|not verified)\b",
    flags=re.IGNORECASE,
)
STATUS_TERMS = re.compile(
    r"\b(?:affiliation|classification|designation|identity|legal status|status)\b",
    flags=re.IGNORECASE,
)
NO_CONFIRMING_SOURCE = re.compile(
    r"\bno\s+(?:official|reliable|verified)\s+(?:record|source)\b.{0,45}"
    r"\b(?:authenticates?|confirms?|establishes?|verifies?)\b",
    flags=re.IGNORECASE,
)


def rc4_behaviors(text: str) -> list[str]:
    return [
        family
        for family, patterns in RC4_BEHAVIOR_PATTERNS.items()
        if has_any(text, patterns)
    ]


def rc4_safe_context(text: str) -> bool:
    return has_any(text, RC4_SOURCE_CONTEXT_PATTERNS) and has_any(
        text, SAFE_STANCE_PATTERNS
    )


def rc4_unverified_status(text: str) -> bool:
    return bool(
        ORGANIZATION_TERMS.search(text)
        and (
            (STATUS_TERMS.search(text) and UNCERTAINTY_TERMS.search(text))
            or NO_CONFIRMING_SOURCE.search(text)
            or (
                UNCERTAINTY_TERMS.search(text)
                and TERROR_STATUS_TERMS.search(text)
            )
            or DESIGNATION_NEGATION.search(text)
        )
    )


def result(
    *,
    category: str,
    status: str,
    confidence: float,
    action: str,
    review: bool,
    families: list[str],
    safe: bool,
) -> dict[str, object]:
    return {
        "available": True,
        "candidate": "terrorism-extremism-v6-rc4-policy-parser",
        "category": category,
        "status": status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": review,
        "behavior_families": families,
        "safe_context_detected": safe,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "supporting_evidence_only": True,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }


def analyze_terrorism_extremism_v6_rc4(text: str) -> dict[str, object]:
    normalized = normalize_text(text)
    base = dict(analyze_terrorism_extremism_v5_rc3(text))
    base["candidate"] = "terrorism-extremism-v6-rc4-policy-parser"
    base["connected_to_live_moderation"] = False
    if not normalized:
        return base

    families = list(
        dict.fromkeys(list(base.get("behavior_families", [])) + rc4_behaviors(normalized))
    )
    base["behavior_families"] = families

    # Reporting/education/prevention continues to own the safe boundary.
    if rc4_safe_context(normalized):
        return result(
            category=NORMAL_CATEGORY,
            status="safe_reporting_education_or_prevention",
            confidence=0.92,
            action="Allow",
            review=False,
            families=families,
            safe=True,
        )
    if base.get("status") in {
        "legitimate_recruitment_or_operational_context",
        "conflicting_legitimate_and_extremist_context",
    }:
        return base
    if families and broad_claimed_designation(normalized):
        return result(
            category=TERRORISM_CATEGORY,
            status="claimed_designation_and_behavior_review_only",
            confidence=min(0.92, 0.86 + 0.02 * (len(families) - 1)),
            action="Block and escalate",
            review=True,
            families=families,
            safe=False,
        )
    if families and rc4_unverified_status(normalized):
        return result(
            category=UNCERTAIN_CATEGORY,
            status="unverified_status_and_behavior_requires_review",
            confidence=0.58,
            action="Refer to human review",
            review=True,
            families=families,
            safe=False,
        )
    return base


def get_terrorism_extremism_v6_rc4_status() -> dict[str, object]:
    return {
        "available": True,
        "candidate": "terrorism-extremism-v6-rc4-policy-parser",
        "noun_form_behavior_parser": True,
        "institutional_safe_context_veto": True,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
