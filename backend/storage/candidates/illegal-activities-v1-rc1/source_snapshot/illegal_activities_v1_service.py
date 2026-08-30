"""Review-only Illegal Activities evidence and guarded fusion."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from app.services.openrouter_advisory_service import (
    analyze_illegal_activities_with_openrouter,
)


ILLEGAL_CATEGORY = "Illegal Activities"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
ILLEGAL_ACTION = "Restrict and send for human review"
UNCERTAIN_ACTION = "Refer to human review"

POLICY_PATH = (
    Path(__file__).resolve().parents[1]
    / "evidence"
    / "illegal_activities_v1_policy.json"
)

ESTABLISHED_CATEGORY_OWNERS = {
    "Religiously Offensive Content",
    "Hate Speech & Discrimination",
    "Terrorism & Extremism",
    "Violent Content",
    "Dangerous Content",
    "Graphic, Obscene & Sexual Content",
    "Sexual Harassment",
    "Cyberbullying & Harassment",
    "Invasion of Privacy",
    "Publishing Private Information",
    "Identity Theft & Impersonation",
    "Misinformation & Fake News",
    "Spam, Scam & Phishing",
    "Intellectual Property Infringement",
    "Malicious Programs",
    "Abusive Words",
    "Child Exploitation",
}

FAMILY_TERMS = {
    "controlled_substances": (
        "illegal drugs",
        "controlled pills",
        "unapproved medicine",
        "unapproved drug",
        "psychotropic substances",
        "illegal narcotics",
    ),
    "weapons": (
        "unlicensed gun",
        "gun without a license",
        "weapon without a license",
        "illegal firearm",
        "prohibited weapon",
    ),
    "gambling": (
        "illegal gambling",
        "illegal betting",
        "unlicensed betting",
        "unlicensed gambling",
        "online betting service",
    ),
    "sexual_services": (
        "prostitution services",
        "sexual services for money",
        "paid sexual service",
        "commercial sexual service",
    ),
    "forgery_financial": (
        "fake identity document",
        "forged certificate",
        "counterfeit currency",
        "money laundering service",
        "fake government document",
    ),
    "protected_symbols": (
        "fake government emblem",
        "misuse national emblem",
        "misuse the national flag",
        "protected government name",
    ),
}

DIRECT_FACILITATION_TERMS = (
    "for sale",
    "buy now",
    "order now",
    "contact me",
    "message me to order",
    "delivery available",
    "book now",
    "pay to receive",
    "available tonight",
    "join this betting",
    "use this in your advertisement",
)

SAFE_CONTEXT_TERMS = (
    "news report",
    "documentary",
    "educational",
    "education",
    "research",
    "warning",
    "prevention",
    "condemns",
    "condemn",
    "historical",
    "academic discussion",
    "fictional example",
    "do not buy",
    "do not sell",
    "avoid",
    "reported to authorities",
)

LEGITIMATE_CONTEXT_TERMS = (
    "microsoft job recruitment",
    "licensed pharmacy",
    "licensed sporting event",
    "museum exhibition",
    "film prop",
    "lawful training range",
    "regulated legal service",
    "ordinary ecommerce listing",
)

CHILD_TERMS = ("child", "minor", "underage", "schoolgirl", "schoolboy")
CHILD_RISK_TERMS = (
    "sexual",
    "groom",
    "nude",
    "private image",
    "meet secretly",
)


def _normalize(text: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", text).casefold().split()
    )


def _policy_evidence() -> list[dict[str, Any]]:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    evidence = payload.get("policy_evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("Illegal Activities policy evidence is invalid.")
    return [dict(item) for item in evidence]


def _matching_families(normalized_text: str) -> list[str]:
    return [
        family
        for family, terms in FAMILY_TERMS.items()
        if any(term in normalized_text for term in terms)
    ]


def _has_child_safety_boundary(normalized_text: str) -> bool:
    return any(term in normalized_text for term in CHILD_TERMS) and any(
        term in normalized_text for term in CHILD_RISK_TERMS
    )


def _empty_advisory(status: str) -> dict[str, Any]:
    return {
        "available": False,
        "used": False,
        "status": status,
        "verdict": "uncertain",
        "confidence": 0.0,
        "policy_ids": [],
        "automatic_enforcement_allowed": False,
        "llm_can_create_allow": False,
        "raw_output_stored": False,
    }


def analyze_illegal_activities_v1(
    text: str,
    input_sources: list[str],
    *,
    use_openrouter: bool = True,
) -> dict[str, Any]:
    normalized = _normalize(text)
    families = _matching_families(normalized)
    direct_facilitation = any(
        term in normalized for term in DIRECT_FACILITATION_TERMS
    )
    safe_context = any(term in normalized for term in SAFE_CONTEXT_TERMS)
    legitimate_context = any(
        term in normalized for term in LEGITIMATE_CONTEXT_TERMS
    )
    text_only = input_sources == ["text"]

    result: dict[str, Any] = {
        "available": True,
        "version": "illegal-activities-v1-ai-advisory",
        "fusion_status": "no_illegal_activities_boundary_override",
        "proposed_category": "",
        "proposed_action": "",
        "proposed_severity": "",
        "confidence": 0.0,
        "human_review_required": False,
        "families": families,
        "direct_facilitation": direct_facilitation,
        "safe_context": safe_context,
        "legitimate_context": legitimate_context,
        "automatic_enforcement_allowed": False,
        "openrouter": _empty_advisory("not_routed"),
        "warnings": [],
    }

    if not normalized:
        result["fusion_status"] = "empty_input_no_override"
        return result

    if _has_child_safety_boundary(normalized):
        result["fusion_status"] = "blocked_by_child_safety_boundary"
        result["human_review_required"] = True
        return result

    if not families:
        return result

    if legitimate_context and not direct_facilitation:
        result["fusion_status"] = "legitimate_context_no_override"
        return result

    if safe_context and not direct_facilitation:
        result["fusion_status"] = "safe_reporting_or_prevention_no_override"
        return result

    if use_openrouter and text_only:
        result["openrouter"] = analyze_illegal_activities_with_openrouter(
            text,
            _policy_evidence(),
        )

    if direct_facilitation:
        result.update(
            {
                "fusion_status": "illegal_activities_review_candidate",
                "proposed_category": ILLEGAL_CATEGORY,
                "proposed_action": ILLEGAL_ACTION,
                "proposed_severity": "High",
                "confidence": 0.84,
                "human_review_required": True,
            }
        )
        if result["openrouter"].get("used"):
            result["confidence"] = min(
                0.88,
                max(
                    result["confidence"],
                    float(result["openrouter"].get("confidence", 0.0)),
                ),
            )
        return result

    result.update(
        {
            "fusion_status": "jurisdiction_or_facilitation_uncertain",
            "proposed_category": UNCERTAIN_CATEGORY,
            "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "Unknown",
            "confidence": 0.62,
            "human_review_required": True,
        }
    )
    return result


def apply_illegal_activities_v1_fusion(
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
    updated = {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "reason": reason,
        "matched_signals": list(matched_signals),
        "decision_applied": False,
        "fusion_status": str(analysis.get("fusion_status", "unavailable")),
        "automatic_enforcement_allowed": False,
    }

    proposal = str(analysis.get("proposed_category", ""))
    if not proposal:
        return updated

    if category == ILLEGAL_CATEGORY:
        updated["fusion_status"] = "illegal_activities_owner_already_applied"
        updated["human_review_required"] = True
        return updated

    if category in ESTABLISHED_CATEGORY_OWNERS:
        updated["fusion_status"] = "blocked_by_established_category_owner"
        if analysis.get("human_review_required"):
            updated["human_review_required"] = True
        return updated

    if category not in {NORMAL_CATEGORY, UNCERTAIN_CATEGORY}:
        updated["fusion_status"] = "blocked_by_unknown_category_owner"
        return updated

    updated.update(
        {
            "category": proposal,
            "severity": str(analysis.get("proposed_severity", "Unknown")),
            "action": str(analysis.get("proposed_action", UNCERTAIN_ACTION)),
            "confidence": min(
                0.88,
                max(confidence, float(analysis.get("confidence", 0.0))),
            ),
            "human_review_required": True,
            "decision_applied": True,
            "fusion_status": str(analysis.get("fusion_status")),
        }
    )
    if proposal == ILLEGAL_CATEGORY:
        updated["reason"] = (
            "Local policy evidence found a current transaction or facilitation "
            "signal for a potentially illegal activity. This is a review-only "
            "product-policy classification, not a legal determination."
        )
        updated["matched_signals"].append(
            "illegal_activities_v1:review_only_candidate"
        )
    else:
        updated["reason"] = (
            "Potential illegal-activity subject matter was detected, but "
            "facilitation, licensing, or jurisdiction could not be established."
        )
        updated["matched_signals"].append(
            "illegal_activities_v1:jurisdiction_uncertain"
        )

    return updated


def get_illegal_activities_v1_status() -> dict[str, Any]:
    return {
        "version": "illegal-activities-v1-ai-advisory",
        "policy_evidence_available": POLICY_PATH.is_file(),
        "permitted_outputs": [ILLEGAL_CATEGORY, UNCERTAIN_CATEGORY],
        "human_review_required": True,
        "automatic_enforcement_allowed": False,
        "legal_determination_authority": False,
        "external_restricted_data_used": False,
    }
