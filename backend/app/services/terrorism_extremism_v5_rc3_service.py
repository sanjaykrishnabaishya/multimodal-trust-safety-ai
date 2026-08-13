from __future__ import annotations

import re

from app.services.terrorism_extremism_service import (
    NORMAL_CATEGORY,
    TERRORISM_CATEGORY,
    UNCERTAIN_CATEGORY,
    normalize_text,
)
from app.services.terrorism_extremism_v4_rc2_service import (
    CLAIMED_DESIGNATION_PATTERNS,
    UNVERIFIED_STATUS_PATTERNS,
    analyze_terrorism_extremism_v4_rc2,
    has_any,
    supplementary_behaviors,
)


SOURCE_CONTEXT_PATTERNS = (
    r"\b(?:news|newspaper|journalistic|media|court|police)\s+"
    r"(?:account|article|coverage|report|reporting|summary)\b",
    r"\b(?:academic|scholarly|research)\s+"
    r"(?:analysis|paper|project|report|study)\b",
    r"\b(?:documentary|museum|archive|archival|historical|history)\b",
    r"\b(?:classroom|curriculum|education|educational|lesson|textbook)\b",
    r"\bpublic[- ]safety\s+(?:advisory|campaign|message|notice|warning)\b",
)

SAFE_STANCE_PATTERNS = (
    r"\b(?:condemn|condemns|condemned|condemning|condemnation)\b",
    r"\b(?:criticise|criticises|criticised|criticising|criticize|criticizes|"
    r"criticized|criticizing|critical|critically)\b",
    r"\b(?:oppose|opposes|opposed|opposing|opposition)\b",
    r"\bwithout\s+(?:advocating|endorsing|funding|glorifying|praising|"
    r"promoting|recruiting|supporting)\b",
    r"\b(?:does not|doesn't|did not|didn't|never)\s+"
    r"(?:advocate|endorse|fund|glorify|praise|promote|recruit|support)\b",
    r"\b(?:discourage|discourages|discouraged|discouraging|prevent|prevents|"
    r"prevented|preventing)\b",
    r"\b(?:warn|warns|warned|warning|tell|tells|told|urge|urges|urged)\b"
    r".{0,45}\b(?:do not|don't|never|not to|avoid|against)\b",
    r"\b(?:reject|rejects|rejected|rejecting|denounce|denounces|denounced|"
    r"denouncing)\b",
)

DIRECT_ADVOCACY_PATTERNS = (
    r"^(?:please\s+)?(?:join|enlist|register|donate|fund|finance|share|"
    r"circulate|forward|support|praise|glorify)\b",
    r"\b(?:you|readers?|followers?|everyone|people|members?)\s+"
    r"(?:must|should|need to|have to)\s+"
    r"(?:join|enlist|register|donate|fund|share|support|praise)\b",
    r"\b(?:i|we)\s+(?:praise|support|endorse|fund|finance|will join|want to join)\b",
)

RC3_SUPPLEMENTARY_BEHAVIOR_PATTERNS = {
    "recruitment_or_membership": (
        r"\b(?:membership registration|registration by new members?)\b",
    ),
    "propaganda_distribution": (
        r"\b(?:circulate|circulates|circulated|circulating|forward|forwards|"
        r"forwarded|forwarding)\b.{0,40}\brecruitment material\b",
    ),
}

DESIGNATION_TERMS = re.compile(
    r"\b(?:banned|designated|listed|proscribed|sanctioned)\b",
    flags=re.IGNORECASE,
)
TERROR_STATUS_TERMS = re.compile(
    r"\b(?:terrorist|terrorism|extremist|extremism)\b",
    flags=re.IGNORECASE,
)
ORGANIZATION_TERMS = re.compile(
    r"\b(?:cell|faction|group|movement|network|organisation|organization|outfit)\b",
    flags=re.IGNORECASE,
)
DESIGNATION_NEGATION = re.compile(
    r"\b(?:not|never|no longer)\b.{0,20}\b(?:banned|designated|listed|"
    r"proscribed|sanctioned)\b|\bno\s+(?:official\s+)?designation\b",
    flags=re.IGNORECASE,
)


def safe_policy_context(text: str) -> bool:
    return (
        has_any(text, SOURCE_CONTEXT_PATTERNS)
        and has_any(text, SAFE_STANCE_PATTERNS)
        and not has_any(text, DIRECT_ADVOCACY_PATTERNS)
    )


def rc3_supplementary_behaviors(text: str) -> list[str]:
    return [
        family
        for family, patterns in RC3_SUPPLEMENTARY_BEHAVIOR_PATTERNS.items()
        if has_any(text, patterns)
    ]


def broad_claimed_designation(text: str) -> bool:
    return bool(
        DESIGNATION_TERMS.search(text)
        and TERROR_STATUS_TERMS.search(text)
        and ORGANIZATION_TERMS.search(text)
        and not DESIGNATION_NEGATION.search(text)
    ) or has_any(text, CLAIMED_DESIGNATION_PATTERNS)


def review_output(
    *,
    category: str,
    status: str,
    confidence: float,
    action: str,
    families: list[str],
    designation: str,
    reason: str,
) -> dict[str, object]:
    return {
        "available": True,
        "candidate": "terrorism-extremism-v5-rc3-context-parser",
        "category": category,
        "status": status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": True,
        "behavior_families": families,
        "designation_evidence": designation,
        "safe_context_detected": False,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "supporting_evidence_only": True,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "reason": reason,
    }


def analyze_terrorism_extremism_v5_rc3(text: str) -> dict[str, object]:
    normalized = normalize_text(text)
    base = dict(analyze_terrorism_extremism_v4_rc2(text))
    base["candidate"] = "terrorism-extremism-v5-rc3-context-parser"
    base["connected_to_live_moderation"] = False
    base["permission_restricted_source_used"] = False
    if not normalized:
        return base

    families = list(
        dict.fromkeys(
            list(base.get("behavior_families", []))
            + supplementary_behaviors(normalized)
            + rc3_supplementary_behaviors(normalized)
        )
    )
    base["behavior_families"] = families

    # Safe reporting, education, history, or prevention owns the boundary and
    # is evaluated before any designation or community-name evidence.
    if safe_policy_context(normalized):
        return {
            "available": True,
            "candidate": "terrorism-extremism-v5-rc3-context-parser",
            "category": NORMAL_CATEGORY,
            "status": "safe_reporting_education_history_or_prevention",
            "confidence": 0.92,
            "action": "Allow",
            "human_review_required": False,
            "behavior_families": families,
            "designation_evidence": "not_used_for_enforcement",
            "safe_context_detected": True,
            "official_registry_used": False,
            "permission_restricted_source_used": False,
            "supporting_evidence_only": True,
            "automatic_enforcement_allowed": False,
            "connected_to_live_moderation": False,
            "reason": (
                "A reporting, educational, historical, academic, or public-"
                "safety context explicitly condemns, criticizes, opposes, or "
                "discourages the behavior."
            ),
        }

    # Existing legitimate jobs/business/charity vetoes keep priority.
    if base.get("status") in {
        "legitimate_recruitment_or_operational_context",
        "conflicting_legitimate_and_extremist_context",
    }:
        return base

    if families and broad_claimed_designation(normalized):
        return review_output(
            category=TERRORISM_CATEGORY,
            status="claimed_designation_and_behavior_review_only",
            confidence=min(0.92, 0.86 + 0.02 * (len(families) - 1)),
            action="Block and escalate",
            families=families,
            designation="explicit_claim_in_user_content_requires_verification",
            reason=(
                "Designation, terrorism/extremism, organization, and relevant "
                "behavior signals occur together. This is a review-only policy "
                "classification, not confirmation of legal status."
            ),
        )

    if families and (
        has_any(normalized, UNVERIFIED_STATUS_PATTERNS)
        or DESIGNATION_NEGATION.search(normalized)
    ):
        return review_output(
            category=UNCERTAIN_CATEGORY,
            status="unverified_or_negated_status_requires_review",
            confidence=0.58,
            action="Refer to human review",
            families=families,
            designation="unverified",
            reason=(
                "Relevant behavior appears with uncertain, unverified, or "
                "negated designation language."
            ),
        )
    return base


def get_terrorism_extremism_v5_rc3_status() -> dict[str, object]:
    return {
        "available": True,
        "candidate": "terrorism-extremism-v5-rc3-context-parser",
        "safe_context_veto_priority": True,
        "word_order_independent_designation_parser": True,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
