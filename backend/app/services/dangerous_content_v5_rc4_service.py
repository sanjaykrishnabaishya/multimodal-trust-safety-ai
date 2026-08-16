from __future__ import annotations

import re
from typing import Any

from app.services.dangerous_content_v4_rc3_service import (
    analyze_dangerous_content_v4_rc3,
)


DANGEROUS_CATEGORY = "Dangerous Content"
DANGEROUS_ACTION = "Remove and send for human review"

ADVOCACY_PATTERNS = [
    r"\burg(?:e|es|ed|ing)\b",
    r"\bpressur(?:e|es|ed|ing)\b",
    r"\bdar(?:e|es|ed|ing)\b",
    r"\bchalleng(?:e|es|ed|ing)\b",
    r"\bencourag(?:e|es|ed|ing)\b",
    r"\binvit(?:e|es|ed|ing)\b",
    r"\btells?\b",
    r"\basks?\b.{0,50}\b(?:try|attempt|copy|imitate|repeat|reproduce|recreate|perform)\b",
    r"\b(?:should|must)\b.{0,35}\b(?:try|attempt|copy|imitate|repeat|reproduce|recreate|perform)\b",
    r"\b(?:try|attempt|copy|imitate|repeat|reproduce|recreate) (?:this|it|the act|the stunt|the challenge)\b",
    r"\b(?:trying|attempting|copying|imitating|repeating|reproducing|recreating|performing)\b.{0,120}\b(?:is|are) (?:presented|promoted|framed|described)\b.{0,100}\b(?:audience|viewers?|followers?|people|public|participants?)\b.{0,45}\bshould (?:do|try|copy|attempt|participate)\b",
]

ACTION_PATTERNS = [
    r"\btr(?:y|ies|ied|ying)\b",
    r"\battempt(?:s|ed|ing)?\b",
    r"\bcopy(?:ing|ied|ies)?\b",
    r"\bimitat(?:e|es|ed|ing)\b",
    r"\brepeat\b",
    r"\breproduc(?:e|es|ed|ing)\b",
    r"\brecreat(?:e|es|ed|ing)\b",
    r"\bperform\b",
    r"\bcarry out\b",
    r"\btake part\b",
    r"\bparticipat(?:e|es|ed|ing)\b",
]

AUDIENCE_PATTERNS = [
    r"\bviewer(?:s)?\b",
    r"\baudience\b",
    r"\bfollower(?:s)?\b",
    r"\bpublic\b",
    r"\bpeople\b",
    r"\bperson\b",
    r"\bsomeone\b",
    r"\bparticipant(?:s)?\b",
    r"\bamateur(?:s)?\b",
    r"\buntrained\b",
    r"\bbeginner(?:s)?\b",
    r"\bordinary (?:person|people|user|users)\b",
]

HARM_PATTERNS = [
    r"\bdanger(?:ous)?\b",
    r"\bhazard(?:ous)?\b",
    r"\bunsafe\b",
    r"\breckless\b",
    r"\bperilous\b",
    r"\bserious (?:injury|harm|damage)\b",
    r"\bbodily harm\b",
    r"\bphysical harm\b",
    r"\binjur(?:y|ies|e|ed)\b",
    r"\bdeath\b",
    r"\bdestroy(?:s|ed|ing)?\b",
    r"\bproperty (?:damage|destruction)\b",
    r"\bharm (?:a |another |other )?(?:person|people|bystander)\b",
]

HAZARD_DOMAIN_PATTERNS = [
    r"\bunprotected (?:drop|height|edge|barrier)\b",
    r"\belevated (?:gap|surface|structure|platform)\b",
    r"\bcliff\b",
    r"\brooftop\b",
    r"\bfragile (?:ice|frozen water|surface)\b",
    r"\benergized\b",
    r"\blive (?:wire|wiring|electric|electrical|equipment)\b",
    r"\belectrical (?:equipment|hardware|panel|hazard)\b",
    r"\bmoving (?:machine|machinery|equipment|vehicle|platform)\b",
    r"\bpowered (?:machine|machinery|equipment|tool)\b",
    r"\bprotective (?:guard|interlock|barrier)\b",
    r"\bfire\b",
    r"\bflammable\b",
    r"\bfume(?:s)?\b",
    r"\bvapor\b",
    r"\bpressuriz(?:ed|ation)\b",
    r"\bcorrosive\b",
    r"\bexplosi(?:on|ve)\b",
    r"\bflood water\b",
    r"\bdeep water\b",
    r"\bfast-moving water\b",
    r"\bunstable (?:load|object|structure|surface|debris)\b",
    r"\bfalling (?:object|debris)\b",
    r"\bbystander(?:s)?\b",
    r"\boccupied (?:building|property|structure)\b",
]

UNSAFE_FRAMING_PATTERNS = [
    r"\bwithout (?:safety|supervision|professional|protective|controls?|safeguards?)\b",
    r"\boutside (?:professional|controlled|supervised)\b",
    r"\bignore(?:s|d|ing)? (?:the )?(?:risk|warning|safety|safeguard)\b",
    r"\bdismiss(?:es|ed|ing)? (?:the )?(?:risk|warning|safety|safeguard)\b",
    r"\bdespite (?:the )?(?:risk|danger|warning)\b",
    r"\bfor (?:fun|entertainment|views|likes)\b",
]

SAFE_OR_REPORTED_CONTEXT_PATTERNS = [
    r"\bwarn(?:s|ed|ing)?\b",
    r"\bdiscourag(?:e|es|ed|ing)\b",
    r"\bcondemn(?:s|ed|ing)?\b",
    r"\bprevent(?:s|ed|ing|ion)?\b",
    r"\bavoid(?:s|ed|ing)?\b",
    r"\bnot to (?:try|copy|repeat|imitate|attempt|perform)\b",
    r"\bnever (?:try|copy|repeat|imitate|attempt|perform)\b",
    r"\bdoes not (?:encourage|endorse|support|invite)\b",
    r"\bno (?:invitation|encouragement|endorsement)\b",
    r"\bqualified (?:team|staff|professional|operator|technician)\b",
    r"\blicensed (?:team|staff|professional|operator|technician)\b",
    r"\bcertified (?:team|staff|professional|operator|technician)\b",
    r"\bcontrolled (?:facility|site|setting|test|exercise|demonstration)\b",
    r"\bauthorized (?:facility|test|exercise|operation|demonstration)\b",
    r"\bprotective (?:procedures?|equipment|barriers?|controls?)\b",
    r"\bnews (?:report|summary|article)\b",
    r"\bhistorical (?:account|record|discussion)\b",
    r"\bfiction(?:al)?\b",
    r"\bfilm (?:scene|review|critic)\b",
    r"\bdocumentary\b",
    r"\bincident (?:review|report)\b",
    r"\bencyclopedia\b",
    r"\bacademic (?:discussion|study|analysis)\b",
    r"\bresearch(?:er| summary| study)?\b",
    r"\bmuseum exhibit\b",
    r"\bclassroom lesson\b",
]

BENIGN_ACTIVITY_PATTERNS = [
    r"\b(?:harmless|ordinary|normal|routine|basic|beginner|introductory|friendly)\b.{0,60}\b(?:lesson|exercise|hobby|skill|game|puzzle|task|technique|rehearsal|practice|activity)\b",
    r"\b(?:lesson|exercise|hobby|skill|game|puzzle|task|technique|rehearsal|practice|activity)\b.{0,60}\b(?:harmless|ordinary|normal|routine|beginner|learning|class)\b",
    r"\bskill development\b",
    r"\bnormal learning pace\b",
    r"\bordinary hobby\b",
]


def _matches(patterns: list[str], text: str) -> list[str]:
    return [
        pattern
        for pattern in patterns
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]


def _policy_evidence(text: str) -> dict[str, Any]:
    advocacy = _matches(ADVOCACY_PATTERNS, text)
    action = _matches(ACTION_PATTERNS, text)
    audience = _matches(AUDIENCE_PATTERNS, text)
    harm = _matches(HARM_PATTERNS, text)
    hazard_domain = _matches(HAZARD_DOMAIN_PATTERNS, text)
    unsafe_framing = _matches(UNSAFE_FRAMING_PATTERNS, text)
    safe_context = _matches(SAFE_OR_REPORTED_CONTEXT_PATTERNS, text)
    benign_activity = _matches(BENIGN_ACTIVITY_PATTERNS, text)
    safe_context_veto = bool(safe_context and not unsafe_framing)
    benign_activity_veto = bool(
        benign_activity and not harm and not hazard_domain
    )
    direct_advocacy = bool(
        advocacy
        and action
        and (harm or hazard_domain)
        and (audience or unsafe_framing)
        and not safe_context_veto
        and not benign_activity_veto
    )
    return {
        "direct_advocacy": direct_advocacy,
        "advocacy_signal_count": len(advocacy),
        "action_signal_count": len(action),
        "audience_signal_count": len(audience),
        "harm_signal_count": len(harm),
        "hazard_domain_signal_count": len(hazard_domain),
        "unsafe_framing_signal_count": len(unsafe_framing),
        "safe_context_signal_count": len(safe_context),
        "benign_activity_signal_count": len(benign_activity),
        "safe_context_veto": safe_context_veto,
        "benign_activity_veto": benign_activity_veto,
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
            "dangerous_content_v5_rc4_used": False,
            "dangerous_content_v5_rc4_status": status,
            "direct_advocacy_recovery_used": False,
            "development_candidate_only": True,
            "connected_to_live_moderation": False,
        }
    )
    if evidence is not None:
        result["direct_policy_evidence"] = evidence
    return result


def analyze_dangerous_content_v5_rc4(
    text: str,
    *,
    existing_category: str | None = None,
) -> dict[str, Any]:
    normalized_text = " ".join((text or "").split())
    base_result = analyze_dangerous_content_v4_rc3(
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
    if base_result.get("status") == "blocked_by_established_category_owner":
        return _no_override(
            base_result,
            status=str(base_result.get("status")),
        )

    evidence = _policy_evidence(normalized_text)
    if base_result.get("status") == "policy_safe_context_veto" or evidence[
        "safe_context_veto"
    ]:
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
                "dangerous_content_v5_rc4_used": True,
                "dangerous_content_v5_rc4_status": "rc3_semantic_path_applied",
                "direct_advocacy_recovery_used": False,
                "direct_policy_evidence": evidence,
                "automatic_enforcement_allowed": False,
                "development_candidate_only": True,
                "connected_to_live_moderation": False,
            }
        )
        return result

    hazard_probability = float(base_result.get("hazard_probability", 0.0))
    recovered = bool(
        evidence["direct_advocacy"] and hazard_probability >= 0.12
    )
    if not recovered:
        return _no_override(
            base_result,
            status="no_direct_advocacy_recovery",
            evidence=evidence,
        )

    confidence = min(0.88, max(0.72, 0.65 + 0.25 * hazard_probability))
    return {
        **base_result,
        "category": DANGEROUS_CATEGORY,
        "action": DANGEROUS_ACTION,
        "human_review_required": True,
        "automatic_enforcement_allowed": False,
        "dangerous_content_v5_rc4_used": True,
        "dangerous_content_v5_rc4_status": "direct_advocacy_recovery_applied",
        "direct_advocacy_recovery_used": True,
        "direct_policy_evidence": evidence,
        "confidence": round(confidence, 4),
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
    }
