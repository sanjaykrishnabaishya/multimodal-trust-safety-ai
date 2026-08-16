from __future__ import annotations

import re
from typing import Any

from app.services.dangerous_content_v5_rc4_service import (
    analyze_dangerous_content_v5_rc4,
)


DANGEROUS_CATEGORY = "Dangerous Content"
DANGEROUS_ACTION = "Remove and send for human review"
ALLOWED_BOUNDARY_OWNERS = {None, "Normal/Ignore", "Uncertain", "Abusive Words"}

ADVOCACY_PATTERNS = [
    r"\bpromot(?:e|es|ed|ing|ion)\b",
    r"\bendors(?:e|es|ed|ing|ement)\b",
    r"\brecommend(?:s|ed|ing|ation)?\b",
    r"\bglorif(?:y|ies|ied|ying|ication)\b",
    r"\bcelebrat(?:e|es|ed|ing|ion)\b",
    r"\bcall(?:s|ed|ing)? on\b",
    r"\bappeal(?:s|ed|ing)? to\b",
    r"\bpush(?:es|ed|ing)?\b.{0,45}\b(?:audience|viewers?|followers?|people|public|participants?)\b",
    r"\bfram(?:e|es|ed|ing)\b.{0,60}\b(?:challenge|dare|example to copy|worthy of imitation)\b",
    r"\bpresent(?:s|ed|ing)?\b.{0,60}\b(?:challenge|dare|something to copy|worthy of imitation)\b",
    r"\b(?:audience|viewers?|followers?|people|public|participants?)\b.{0,70}\b(?:are|is) (?:urged|pressed|dared|challenged|encouraged|invited|told)\b",
    r"\b(?:should|ought to|must)\b.{0,60}\b(?:undertake|attempt|imitate|replicate|recreate|perform|participate)\b",
]

PARTICIPATION_PATTERNS = [
    r"\b(?:try|attempt|imitate|replicate|recreate|repeat|copy|perform|undertake|participate)(?:s|d|ing)?\b",
    r"\b(?:trying|attempting|imitation|replication|recreation|participation|performance|undertaking)\b",
    r"\btake part\b",
    r"\bcarry out\b",
    r"\bfollow (?:the )?example\b",
]

AUDIENCE_PATTERNS = [
    r"\b(?:audience|viewers?|followers?|people|public|participants?|users?|amateurs?|beginners?|bystanders?)\b",
    r"\b(?:someone|anyone|others|ordinary persons?)\b",
]

PHYSICAL_HAZARD_PATTERNS = [
    r"\b(?:dangerous|hazardous|unsafe|reckless|perilous|high-risk)\b",
    r"\b(?:injur(?:y|ies)|bodily harm|physical harm|death|fatal|property damage|property destruction)\b",
    r"\b(?:expos(?:e|es|ed|ing)|endanger(?:s|ed|ing)?)\b.{0,55}\b(?:bystanders?|people|another person|property|occupied structure)\b",
    r"\b(?:live|energized) (?:wire|wiring|equipment|panel)\b",
    r"\b(?:moving|powered|unguarded) (?:machine|machinery|equipment|vehicle|tool)\b",
    r"\b(?:unstable|unprotected|elevated) (?:edge|platform|structure|surface|load|debris)\b",
    r"\b(?:flammable|corrosive|pressurized|explosive) (?:material|container|equipment|substance|environment)\b",
    r"\b(?:uncontrolled|open) (?:fire|flame|heat source)\b",
    r"\b(?:deep|fast-moving|flood) water\b",
    r"\b(?:toxic|hazardous) (?:fume|fumes|vapor|vapors)\b",
]

UNSAFE_FRAMING_PATTERNS = [
    r"\bwithout (?:safeguards?|supervision|protective controls?|professional control|training)\b",
    r"\boutside (?:a )?(?:controlled|professional|supervised) (?:setting|site|environment)\b",
    r"\bdespite (?:the )?(?:danger|risk|warning|hazard)\b",
    r"\bignore(?:s|d|ing)? (?:the )?(?:danger|risk|warning|safety rules?)\b",
    r"\bfor (?:views|likes|attention|entertainment)\b",
]

SAFE_CONTEXT_PATTERNS = [
    r"\b(?:warn|warns|warned|warning|discourage|discourages|discouraged|condemn|condemns|condemned)\b",
    r"\b(?:prevent|prevents|prevented|prevention|avoid|avoids|avoided)\b",
    r"\b(?:do not|does not|did not|never|must not|should not)\b.{0,45}\b(?:try|attempt|copy|imitate|replicate|recreate|perform|undertake|participate|endorse|encourage)\b",
    r"\bno (?:endorsement|encouragement|invitation|advocacy)\b",
    r"\b(?:news report|incident report|safety bulletin|historical account|academic analysis|research summary|fictional scene|documentary)\b",
    r"\b(?:qualified|licensed|certified|trained) (?:team|staff|professionals?|operators?|technicians?)\b",
    r"\b(?:controlled|authorized|supervised) (?:facility|site|setting|test|exercise|demonstration|operation)\b",
    r"\b(?:protective barriers?|formal safeguards?|safety procedures?|protective equipment)\b",
]

BENIGN_ACTIVITY_PATTERNS = [
    r"\b(?:harmless|ordinary|routine|beginner|introductory|friendly|age-appropriate)\b.{0,65}\b(?:lesson|exercise|hobby|skill|game|puzzle|task|rehearsal|practice|activity)\b",
    r"\b(?:lesson|exercise|hobby|skill|game|puzzle|task|rehearsal|practice|activity)\b.{0,65}\b(?:harmless|ordinary|routine|beginner|learning|classroom)\b",
    r"\b(?:normal learning|skill development|creative practice|classroom activity)\b",
]


def _matches(patterns: list[str], text: str) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def _policy_evidence(text: str) -> dict[str, Any]:
    advocacy = _matches(ADVOCACY_PATTERNS, text)
    participation = _matches(PARTICIPATION_PATTERNS, text)
    audience = _matches(AUDIENCE_PATTERNS, text)
    hazard = _matches(PHYSICAL_HAZARD_PATTERNS, text)
    unsafe_framing = _matches(UNSAFE_FRAMING_PATTERNS, text)
    safe_context = _matches(SAFE_CONTEXT_PATTERNS, text)
    benign_activity = _matches(BENIGN_ACTIVITY_PATTERNS, text)
    safe_veto = bool(safe_context and not unsafe_framing)
    benign_veto = bool(benign_activity and not hazard)
    recovery = bool(
        advocacy
        and participation
        and hazard
        and (audience or unsafe_framing)
        and not safe_veto
        and not benign_veto
    )
    return {
        "recovery": recovery,
        "advocacy_signal_count": len(advocacy),
        "participation_signal_count": len(participation),
        "audience_signal_count": len(audience),
        "physical_hazard_signal_count": len(hazard),
        "unsafe_framing_signal_count": len(unsafe_framing),
        "safe_context_signal_count": len(safe_context),
        "benign_activity_signal_count": len(benign_activity),
        "safe_context_veto": safe_veto,
        "benign_activity_veto": benign_veto,
    }


def _no_override(
    base_result: dict[str, Any],
    *,
    status: str,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = dict(base_result)
    result.update(
        {
            "category": None,
            "action": None,
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "dangerous_content_v6_rc5_used": False,
            "dangerous_content_v6_rc5_status": status,
            "rc5_policy_recovery_used": False,
            "development_candidate_only": True,
            "connected_to_live_moderation": False,
        }
    )
    if evidence is not None:
        result["rc5_policy_evidence"] = evidence
    return result


def analyze_dangerous_content_v6_rc5(
    text: str,
    *,
    existing_category: str | None = None,
) -> dict[str, Any]:
    normalized_text = " ".join((text or "").split())
    base_result = analyze_dangerous_content_v5_rc4(
        normalized_text,
        existing_category=existing_category,
    )
    if not normalized_text:
        return _no_override(base_result, status="empty_text_no_override")
    if base_result.get("available") is not True:
        return _no_override(
            base_result,
            status="semantic_dependency_unavailable_no_override",
        )
    if existing_category not in ALLOWED_BOUNDARY_OWNERS:
        return _no_override(
            base_result,
            status="blocked_by_established_category_owner",
        )

    evidence = _policy_evidence(normalized_text)
    if evidence["safe_context_veto"]:
        return _no_override(
            base_result,
            status="safe_reporting_warning_or_professional_veto",
            evidence=evidence,
        )
    if evidence["benign_activity_veto"]:
        return _no_override(
            base_result,
            status="benign_activity_without_physical_hazard_veto",
            evidence=evidence,
        )

    if base_result.get("category") == DANGEROUS_CATEGORY:
        result = dict(base_result)
        result.update(
            {
                "dangerous_content_v6_rc5_used": True,
                "dangerous_content_v6_rc5_status": "frozen_rc4_path_applied",
                "rc5_policy_recovery_used": False,
                "rc5_policy_evidence": evidence,
                "automatic_enforcement_allowed": False,
                "development_candidate_only": True,
                "connected_to_live_moderation": False,
            }
        )
        return result

    if not evidence["recovery"]:
        return _no_override(
            base_result,
            status="insufficient_advocacy_and_hazard_evidence",
            evidence=evidence,
        )

    hazard_probability = float(base_result.get("hazard_probability", 0.0))
    confidence = min(0.88, max(0.72, 0.70 + 0.18 * hazard_probability))
    return {
        **base_result,
        "category": DANGEROUS_CATEGORY,
        "action": DANGEROUS_ACTION,
        "human_review_required": True,
        "automatic_enforcement_allowed": False,
        "dangerous_content_v6_rc5_used": True,
        "dangerous_content_v6_rc5_status": "broader_policy_recovery_applied",
        "rc5_policy_recovery_used": True,
        "rc5_policy_evidence": evidence,
        "confidence": round(confidence, 4),
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
    }

