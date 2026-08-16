from __future__ import annotations

import re
from typing import Any


DEPICTION_PATTERNS = [
    r"\b(?:video|footage|film|scene|image|photo|photograph|documentary)\b",
    r"\b(?:depict|depicts|depicted|depicting|show|shows|showed|showing|portray|portrays|portrayed|portraying)\b",
]
THIRD_PERSON_PATTERNS = [
    r"\b(?:a|the|another) (?:person|individual|victim|character|man|woman|adult)\b",
    r"\b(?:someone|somebody)\b",
    r"\b(?:person|individual|victim|character|man|woman) being\b",
]
PHYSICAL_DEPICTION_PATTERNS = [
    r"\b(?:stabbed|stabbing|shot|shooting|beaten|beating|assaulted|assaulting|killed|killing|injured|injuring)\b",
    r"\b(?:graphic|graphically|bloody|bloodied|wounded)\b",
    r"\b(?:physical assault|physical violence|violent attack|dead body)\b",
]
DIRECT_TARGET_PATTERNS = [
    r"\b(?:i|we) (?:will|shall|am going to|are going to)\b.{0,55}\b(?:you|your)\b",
    r"\b(?:you|your)\b.{0,55}\b(?:will be|going to be|deserve to be)\b.{0,35}\b(?:hurt|hit|beaten|stabbed|shot|killed|injured)\b",
    r"\b(?:meet me|wait for me|watch your back)\b",
    r"@[a-z0-9_]{2,32}",
]
HARASSMENT_CONTEXT_PATTERNS = [
    r"\b(?:repeatedly|again and again|every day|keeps?|continued|persistent)\b.{0,60}\b(?:message|contact|target|follow|threaten|insult|harass)\b",
    r"\b(?:direct message|private message|dm|inbox|contacted the target)\b",
    r"\b(?:named|identified|specific) (?:target|person|user|victim)\b",
]


def _matches(patterns: list[str], text: str) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def analyze_cyberbullying_depiction_boundary(text: str) -> dict[str, Any]:
    value = " ".join((text or "").split())
    depiction = _matches(DEPICTION_PATTERNS, value)
    third_person = _matches(THIRD_PERSON_PATTERNS, value)
    physical_depiction = _matches(PHYSICAL_DEPICTION_PATTERNS, value)
    direct_target = _matches(DIRECT_TARGET_PATTERNS, value)
    harassment_context = _matches(HARASSMENT_CONTEXT_PATTERNS, value)
    confirmed = bool(
        depiction
        and third_person
        and physical_depiction
        and not direct_target
        and not harassment_context
    )
    return {
        "confirmed_third_person_depiction": confirmed,
        "depiction_signal_count": len(depiction),
        "third_person_signal_count": len(third_person),
        "physical_depiction_signal_count": len(physical_depiction),
        "direct_target_signal_count": len(direct_target),
        "harassment_context_signal_count": len(harassment_context),
        "cyberbullying_targeted_threat_veto_allowed": confirmed,
        "automatic_enforcement_allowed": False,
    }


def apply_graphic_depiction_review_boundary(
    *,
    category: str,
    severity: str,
    action: str,
    confidence: float,
    human_review_required: bool,
    reason: str,
    matched_signals: list[str],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    unchanged = {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "reason": reason,
        "matched_signals": list(matched_signals),
        "decision_applied": False,
        "boundary_status": "no_graphic_depiction_review_boundary",
        "automatic_enforcement_allowed": False,
    }
    if analysis.get("confirmed_third_person_depiction") is not True:
        return unchanged
    if category not in {"Normal/Ignore", "Uncertain"}:
        unchanged["boundary_status"] = "blocked_by_established_category_owner"
        return unchanged
    return {
        "category": "Uncertain",
        "severity": "Unknown",
        "action": "Refer to human review",
        "confidence": max(0.55, min(float(confidence), 0.69)),
        "human_review_required": True,
        "reason": (
            "A third-person graphic physical-harm depiction requires human "
            "review. The validated Violence component is not ready, so the "
            "system does not claim a Violent Content verdict or allow the item."
        ),
        "matched_signals": list(
            dict.fromkeys(matched_signals + ["graphic_depiction_review_boundary"])
        ),
        "decision_applied": True,
        "boundary_status": "graphic_depiction_referred_to_review",
        "automatic_enforcement_allowed": False,
    }
