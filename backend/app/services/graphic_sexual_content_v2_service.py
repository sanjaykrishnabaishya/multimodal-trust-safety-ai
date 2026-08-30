from __future__ import annotations

import re
from typing import Any


SEXUAL_CATEGORY = "Graphic, Obscene & Sexual Content"
SEXUAL_HARASSMENT_CATEGORY = "Sexual Harassment"
SEXUAL_ACTION = "Block or age-restrict"
HARASSMENT_ACTION = "Remove and escalate"
ALLOWED_BOUNDARIES = {None, "Normal/Ignore", "Uncertain", "Abusive Words"}

CHILD_SAFETY_PATTERNS = [
    r"\b(?:child|children|minor|minors|underage)\b.{0,70}\b(?:sexual exploitation|sexual abuse|grooming|abuse material)\b",
    r"\b(?:child-safety|child safety)\b.{0,70}\b(?:exploitation|grooming|abuse)\b",
]

SAFE_CONTEXT_PATTERNS = [
    r"\b(?:hospital|medical|clinical|clinician|public-health|public health|sexual-health|sexual health|reproductive anatomy|anatomy diagram|health education)\b",
    r"\b(?:medical textbook|university course|licensed clinician|health organization)\b",
    r"\b(?:museum|art-history|art history|classical sculpture|renaissance painting|gallery|recognized artwork|historical art)\b",
    r"\b(?:non-explicit|nonexplicit|nonsexual|non-sexual)\b",
    r"\b(?:ordinary swimwear|fitness lesson|standard exercise pose|parent feeding an infant|hold hands|romantic dinner|affection without sexual detail)\b",
    r"\b(?:legitimate educational purpose|clinical and is not presented for arousal|cultural education)\b",
]

NEGATED_SAFE_CONTEXT_PATTERNS = [
    r"\bno (?:medical|health|educational|artistic|documentary)(?:,? (?:artistic|documentary|educational|health))*(?:,? or (?:artistic|documentary|educational|health))? context\b",
    r"\bwithout (?:a |any )?(?:medical|health|educational|artistic|documentary) context\b",
    r"\bnot (?:medical|educational|artistic|documentary) material\b",
]

HARASSMENT_PATTERNS = [
    r"\b(?:unwanted|unwelcome|persistent|repeated|repeatedly|continues?|keeps?)\b.{0,75}\b(?:sexual remarks?|sexual comments?|sexual messages?|explicit messages?|sexual favors?|sexual activity|sexual conduct)\b",
    r"\b(?:requesting|requests?|demanding|demands?|pressures?|pressuring)\b.{0,45}\b(?:sexual favors?|sexual activity|sexual discussion)\b",
    r"\b(?:sexual remarks?|sexual comments?|sexual messages?|explicit messages?)\b.{0,75}\b(?:recipient|target|coworker|person|individual|employee)\b",
]

TARGET_OR_UNWELCOME_PATTERNS = [
    r"\b(?:one person|named recipient|recipient|target|coworker|supervisor|employee|individual)\b",
    r"\b(?:after being refused|told .* stop|must stop|clearly unwelcome|unwelcome|unwanted)\b",
    r"\b(?:directed at|sends? to|pressures? a|requests? from)\b",
]

EXPLICIT_ADULT_PATTERNS = [
    r"\b(?:uncensored|explicit|pornographic|pornography)\b.{0,70}\b(?:adult|adults|sexual|material|content|viewing)\b",
    r"\b(?:adult|adult-only|adults)\b.{0,60}\b(?:explicit|sexual activity|pornography|sexual material|nudity presented sexually)\b",
    r"\b(?:explicit sexual activity|explicit adult content|adult sexual imagery|adult sexual material)\b",
    r"\b(?:morphed|synthetic|animated)\b.{0,60}\b(?:explicit sexual|adult sexual|sexual imagery)\b",
    r"\b(?:paid access|sale|view|viewing|collection|distributes?|advertises?|promotes?)\b.{0,80}\b(?:explicit adult|uncensored pornography|pornography|adult-content|adult content)\b",
]


def _matches(patterns: list[str], text: str) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def _base(status: str, *, available: bool = True) -> dict[str, Any]:
    return {
        "available": available,
        "category": None,
        "severity": "None",
        "action": None,
        "confidence": 0.0,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "decision_applied": False,
        "status": status,
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
    }


def analyze_graphic_sexual_content_v2(
    text: str,
    *,
    existing_category: str | None = None,
) -> dict[str, Any]:
    value = " ".join((text or "").split())
    if not value:
        return _base("empty_text_no_override")
    if existing_category not in ALLOWED_BOUNDARIES:
        result = _base("blocked_by_established_category_owner")
        result["existing_category"] = existing_category
        return result

    child_safety = _matches(CHILD_SAFETY_PATTERNS, value)
    safe_context = _matches(SAFE_CONTEXT_PATTERNS, value)
    negated_safe_context = _matches(NEGATED_SAFE_CONTEXT_PATTERNS, value)
    harassment = _matches(HARASSMENT_PATTERNS, value)
    target_or_unwelcome = _matches(TARGET_OR_UNWELCOME_PATTERNS, value)
    explicit_adult = _matches(EXPLICIT_ADULT_PATTERNS, value)
    evidence = {
        "child_safety_signal_count": len(child_safety),
        "safe_context_signal_count": len(safe_context),
        "negated_safe_context_signal_count": len(negated_safe_context),
        "harassment_signal_count": len(harassment),
        "target_or_unwelcome_signal_count": len(target_or_unwelcome),
        "explicit_adult_signal_count": len(explicit_adult),
    }

    if child_safety:
        result = _base("child_exploitation_boundary_no_override")
        result["evidence"] = evidence
        return result
    if safe_context and not negated_safe_context:
        result = _base("legitimate_or_nonsexual_context_no_override")
        result["evidence"] = evidence
        return result
    if harassment and target_or_unwelcome:
        return {
            **_base("sexual_harassment_review_only_candidate"),
            "category": SEXUAL_HARASSMENT_CATEGORY,
            "severity": "High",
            "action": HARASSMENT_ACTION,
            "confidence": 0.86,
            "human_review_required": True,
            "decision_applied": True,
            "evidence": evidence,
        }
    if explicit_adult:
        return {
            **_base("graphic_sexual_content_review_only_candidate"),
            "category": SEXUAL_CATEGORY,
            "severity": "High",
            "action": SEXUAL_ACTION,
            "confidence": 0.84,
            "human_review_required": True,
            "decision_applied": True,
            "evidence": evidence,
        }

    result = _base("no_sexual_boundary_override")
    result["evidence"] = evidence
    return result
