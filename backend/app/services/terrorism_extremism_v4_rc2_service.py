from __future__ import annotations

import re

from app.services.terrorism_extremism_service import (
    NORMAL_CATEGORY,
    TERRORISM_CATEGORY,
    UNCERTAIN_CATEGORY,
    analyze_terrorism_extremism,
    normalize_text,
)


CLAIMED_DESIGNATION_PATTERNS = (
    r"\b(?:designated|banned|proscribed|listed|sanctioned)\b.{0,45}"
    r"\b(?:terrorist|extremist)\b.{0,25}"
    r"\b(?:cell|faction|group|movement|network|organisation|organization|outfit)\b",
    r"\b(?:cell|faction|group|movement|network|organisation|organization|outfit)\b"
    r".{0,45}\b(?:is|was|were|has been|have been|remains?)\b.{0,30}"
    r"\b(?:designated|banned|proscribed|listed|sanctioned)\b"
    r"(?:.{0,30}\b(?:terrorist|extremist)\b)?",
    r"\b(?:terrorist|extremist)\s+designation\b.{0,45}"
    r"\b(?:applies|confirmed|recorded|stated)\b",
)

UNVERIFIED_STATUS_PATTERNS = (
    r"\b(?:designation|identity|legal status|classification|affiliation)\b"
    r".{0,35}\b(?:unknown|uncertain|unverified|unconfirmed|not confirmed|not verified)\b",
    r"\b(?:unknown|uncertain|unverified|unconfirmed)\b.{0,35}"
    r"\b(?:designation|identity|legal status|classification|affiliation)\b",
    r"\b(?:has|have|had)\s+not\s+been\s+(?:authenticated|confirmed|verified)\b",
    r"\bno\s+(?:official|reliable|verified)\s+(?:record|source)\b.{0,30}"
    r"\b(?:confirms?|verifies?|supports?)\b",
    r"\b(?:alleged|purported|suspected|possible)\s+(?:terrorist|extremist)\s+"
    r"(?:cell|faction|group|movement|network|organisation|organization|outfit)\b",
)

SUPPLEMENTARY_BEHAVIOR_PATTERNS = {
    "recruitment_or_membership": (
        r"\b(?:membership applications?|new members? wanted|enlistment drive)\b",
        r"\b(?:encourage|encourages|encouraged|invite|invites|invited|urge|urges|urged)\b"
        r".{0,35}\b(?:enlist|enlistment|join|register|sign up)\b",
    ),
    "funding_or_operational_support": (
        r"\b(?:collect|collects|collected|solicit|solicits|solicited)\b"
        r".{0,30}\b(?:contributions?|money|payments?)\b",
        r"\b(?:arrange|arranges|arranged|arranging|provide|provides|provided|providing)\b"
        r".{0,35}\b(?:logistics|safe houses?|supplies|transport|weapons?)\b",
    ),
    "praise_or_glorification": (
        r"\b(?:admire|admires|admired|salute|salutes|saluted)\b.{0,35}"
        r"\b(?:actions?|campaign|fighters?|members?)\b",
    ),
    "propaganda_distribution": (
        r"\b(?:circulate|circulates|circulated|circulating|forward|forwards|forwarded|forwarding)\b"
        r".{0,40}\b(?:propaganda|recruitment clips?|recruitment posts?|manifestos?)\b",
    ),
}


def has_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def supplementary_behaviors(text: str) -> list[str]:
    return [
        family
        for family, patterns in SUPPLEMENTARY_BEHAVIOR_PATTERNS.items()
        if has_any(text, patterns)
    ]


def reviewed_decision(
    *,
    category: str,
    status: str,
    confidence: float,
    action: str,
    behavior_families: list[str],
    designation_evidence: str,
    reason: str,
) -> dict[str, object]:
    return {
        "available": True,
        "candidate": "terrorism-extremism-v4-rc2-policy-parser",
        "category": category,
        "status": status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": True,
        "behavior_families": behavior_families,
        "designation_evidence": designation_evidence,
        "safe_context_detected": False,
        "organization_registry_used": False,
        "official_source_data_used": False,
        "permission_restricted_source_used": False,
        "supporting_evidence_only": True,
        "automatic_enforcement_allowed": False,
        "neutral_mention_is_violation": False,
        "connected_to_live_moderation": False,
        "reason": reason,
    }


def analyze_terrorism_extremism_v4_rc2(text: str) -> dict[str, object]:
    base = dict(analyze_terrorism_extremism(text))
    base["candidate"] = "terrorism-extremism-v4-rc2-policy-parser"
    base["connected_to_live_moderation"] = False
    base["permission_restricted_source_used"] = False

    normalized = normalize_text(text)
    if not normalized:
        return base

    # Safe and ordinary organizational contexts always retain veto priority.
    if base.get("category") == NORMAL_CATEGORY or base.get("status") in {
        "safe_reporting_education_history_or_condemnation",
        "legitimate_recruitment_or_operational_context",
        "conflicting_legitimate_and_extremist_context",
        "conflicting_context_requires_review",
    }:
        return base

    families = list(dict.fromkeys(
        list(base.get("behavior_families", []))
        + supplementary_behaviors(normalized)
    ))
    # The community-name guard consumes these behavior families even when the
    # policy parser itself has no designation/status evidence.
    base["behavior_families"] = families
    claimed_designation = has_any(normalized, CLAIMED_DESIGNATION_PATTERNS)
    unverified_status = has_any(normalized, UNVERIFIED_STATUS_PATTERNS)

    if families and claimed_designation:
        return reviewed_decision(
            category=TERRORISM_CATEGORY,
            status="claimed_designation_and_behavior_review_only",
            confidence=min(0.92, 0.86 + 0.02 * (len(families) - 1)),
            action="Block and escalate",
            behavior_families=families,
            designation_evidence="explicit_claim_in_user_content_requires_verification",
            reason=(
                "The text explicitly claims a terrorist or extremist designation "
                "and includes recruitment, praise, funding, propaganda, or "
                "operational support. Enforcement remains review-only."
            ),
        )

    if families and unverified_status:
        return reviewed_decision(
            category=UNCERTAIN_CATEGORY,
            status="unverified_organization_status_requires_review",
            confidence=0.58,
            action="Refer to human review",
            behavior_families=families,
            designation_evidence="unverified",
            reason=(
                "Relevant behavior is present, but identity, affiliation, or "
                "designation language remains unverified."
            ),
        )

    return base


def get_terrorism_extremism_v4_rc2_status() -> dict[str, object]:
    return {
        "available": True,
        "candidate": "terrorism-extremism-v4-rc2-policy-parser",
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "community_candidate_confirmation_allowed": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
