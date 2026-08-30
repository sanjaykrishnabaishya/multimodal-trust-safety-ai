"""Guarded Illegal Activities V2 RC2 policy evidence and fusion.

This candidate uses deterministic, high-level policy signals.  It does not
make legal determinations and never authorizes automatic enforcement.
"""

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
    / "illegal_activities_v2_rc2_policy.json"
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
        "illegal drug",
        "controlled substance",
        "controlled pill",
        "unapproved medicine",
        "unapproved drug",
        "illegal narcotic",
        "prohibited narcotic",
    ),
    "weapons_and_counterfeit": (
        "unlicensed gun",
        "unlicensed firearm",
        "gun without a license",
        "weapon without a license",
        "illegal firearm",
        "prohibited weapon",
        "forged passport",
        "forged identity document",
        "fake identity document",
        "counterfeit currency",
        "counterfeit banknote",
        "fake government document",
    ),
    "gambling_and_financial": (
        "illegal gambling",
        "illegal betting",
        "unlicensed betting",
        "unlicensed gambling",
        "unlawful wagering",
        "online betting service",
        "money laundering service",
    ),
    "prohibited_services_and_symbols": (
        "prostitution service",
        "sexual services for money",
        "paid sexual service",
        "commercial sexual service",
        "fake government emblem",
        "counterfeit government seal",
        "misuse national emblem",
        "misuse the national flag",
        "protected government name",
    ),
}

TRANSACTION_TERMS = (
    "for sale",
    "selling",
    "seller offers",
    "supplier offers",
    "supply available",
    "available to buyers",
    "available tonight",
    "buy now",
    "order now",
    "place an order",
    "contact the seller",
    "contact me",
    "direct message",
    "message to order",
    "delivery available",
    "courier delivery",
    "shipment available",
    "pay to receive",
    "payment required",
    "price per item",
    "book now",
    "reserve a slot",
    "join the betting",
    "sign up to wager",
    "arranges access",
    "provides access",
    "commercial listing",
    "marketplace listing",
    "advertises",
    "markets",
    "promotes the sale",
    "sale being promoted",
    "shipment is available",
)

CURRENT_OFFER_TERMS = (
    "this post",
    "this listing",
    "the account",
    "the seller",
    "the supplier",
    "current offer",
    "marketplace",
    "buyers",
    "customers",
)

SAFE_CONTEXT_TERMS = (
    "news report",
    "news coverage",
    "journalistic report",
    "documentary",
    "educational lesson",
    "education material",
    "research paper",
    "academic research",
    "academic discussion",
    "historical archive",
    "historical account",
    "museum exhibit",
    "fictional story",
    "fictional scene",
    "novel excerpt",
    "screenplay",
    "dramatic reenactment",
    "case study",
    "safety warning",
    "prevention campaign",
    "public awareness",
    "law-enforcement notice",
    "policy debate",
    "condemns",
    "condemnation",
    "critique",
)

EXPLICIT_SAFE_BOUNDARY_TERMS = (
    "not a live offer",
    "no live transaction",
    "contains no transaction",
    "does not facilitate",
    "without facilitating",
    "quoted for analysis",
    "quoted dialogue",
    "quoted advertisement",
    "warning viewers not to buy",
    "tells readers not to buy",
    "reported to authorities",
    "for prevention",
    "for research only",
    "fictional and not real",
)

LEGITIMATE_CONTEXT_TERMS = (
    "microsoft job recruitment",
    "legitimate job recruitment",
    "licensed pharmacy",
    "authorized retailer",
    "regulated legal service",
    "licensed sporting event",
    "museum exhibition",
    "stage prop",
    "film prop",
    "lawful training range",
    "ordinary ecommerce listing",
    "legal compliance training",
    "professional compliance review",
)

UNCERTAINTY_TERMS = (
    "licensing is unclear",
    "license status is unclear",
    "jurisdiction is unknown",
    "jurisdiction remains unknown",
    "legal status is unresolved",
    "location is unknown",
    "context is incomplete",
    "cannot establish a transaction",
    "no transaction is established",
    "purpose is unclear",
    "status is unverified",
)

CHILD_TERMS = (
    "child",
    "minor",
    "underage",
    "schoolgirl",
    "schoolboy",
    "teen under 18",
)
CHILD_RISK_TERMS = (
    "sexual",
    "groom",
    "nude",
    "explicit image",
    "private image",
    "meet secretly",
    "do not tell your parents",
)


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _policy_evidence() -> list[dict[str, Any]]:
    with POLICY_PATH.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    evidence = payload.get("policy_evidence", [])
    if not isinstance(evidence, list):
        raise ValueError("Illegal Activities RC2 policy evidence is invalid.")
    return [dict(item) for item in evidence]


def _matching_families(normalized_text: str) -> list[str]:
    return [
        family
        for family, terms in FAMILY_TERMS.items()
        if _contains_any(normalized_text, terms)
    ]


def _has_child_safety_boundary(normalized_text: str) -> bool:
    return _contains_any(normalized_text, CHILD_TERMS) and _contains_any(
        normalized_text,
        CHILD_RISK_TERMS,
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


def analyze_illegal_activities_v2_rc2(
    text: str,
    input_sources: list[str],
    *,
    use_openrouter: bool = True,
) -> dict[str, Any]:
    normalized = _normalize(text)
    families = _matching_families(normalized)
    transaction_evidence = _contains_any(normalized, TRANSACTION_TERMS)
    current_offer_context = _contains_any(normalized, CURRENT_OFFER_TERMS)
    safe_context = _contains_any(normalized, SAFE_CONTEXT_TERMS)
    explicit_safe_boundary = _contains_any(
        normalized,
        EXPLICIT_SAFE_BOUNDARY_TERMS,
    )
    legitimate_context = _contains_any(normalized, LEGITIMATE_CONTEXT_TERMS)
    uncertain_context = _contains_any(normalized, UNCERTAINTY_TERMS)
    text_only = input_sources == ["text"]

    result: dict[str, Any] = {
        "available": True,
        "version": "illegal-activities-v2-rc2",
        "fusion_status": "no_illegal_activities_boundary_override",
        "proposed_category": "",
        "proposed_action": "",
        "proposed_severity": "",
        "confidence": 0.0,
        "human_review_required": False,
        "families": families,
        "transaction_evidence": transaction_evidence,
        "current_offer_context": current_offer_context,
        "safe_context": safe_context,
        "explicit_safe_boundary": explicit_safe_boundary,
        "legitimate_context": legitimate_context,
        "uncertain_context": uncertain_context,
        "automatic_enforcement_allowed": False,
        "legal_determination_authority": False,
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

    if legitimate_context:
        result["fusion_status"] = "legitimate_context_no_override"
        return result

    if safe_context and (explicit_safe_boundary or not current_offer_context):
        result["fusion_status"] = "safe_context_no_override"
        return result

    if uncertain_context and not transaction_evidence:
        result.update(
            {
                "fusion_status": "jurisdiction_or_status_uncertain",
                "proposed_category": UNCERTAIN_CATEGORY,
                "proposed_action": UNCERTAIN_ACTION,
                "proposed_severity": "Unknown",
                "confidence": 0.64,
                "human_review_required": True,
            }
        )
        return result

    if use_openrouter and text_only:
        result["openrouter"] = analyze_illegal_activities_with_openrouter(
            text,
            _policy_evidence(),
        )

    if transaction_evidence:
        result.update(
            {
                "fusion_status": "illegal_activities_review_candidate",
                "proposed_category": ILLEGAL_CATEGORY,
                "proposed_action": ILLEGAL_ACTION,
                "proposed_severity": "High",
                "confidence": 0.86,
                "human_review_required": True,
            }
        )
        if result["openrouter"].get("used"):
            result["confidence"] = min(
                0.90,
                max(
                    result["confidence"],
                    float(result["openrouter"].get("confidence", 0.0)),
                ),
            )
        return result

    result.update(
        {
            "fusion_status": "subject_without_transaction_uncertain",
            "proposed_category": UNCERTAIN_CATEGORY,
            "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "Unknown",
            "confidence": 0.61,
            "human_review_required": True,
        }
    )
    return result


def apply_illegal_activities_v2_rc2_fusion(
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
        return updated

    if category in ESTABLISHED_CATEGORY_OWNERS:
        updated["fusion_status"] = "blocked_by_established_category_owner"
        return updated

    if category not in {NORMAL_CATEGORY, UNCERTAIN_CATEGORY}:
        updated["fusion_status"] = "blocked_by_unknown_category_owner"
        return updated

    if category == UNCERTAIN_CATEGORY and proposal == UNCERTAIN_CATEGORY:
        updated["fusion_status"] = "uncertain_owner_already_applied"
        updated["human_review_required"] = True
        return updated

    updated.update(
        {
            "category": proposal,
            "severity": str(analysis.get("proposed_severity", "Unknown")),
            "action": str(analysis.get("proposed_action", UNCERTAIN_ACTION)),
            "confidence": min(
                0.90,
                max(confidence, float(analysis.get("confidence", 0.0))),
            ),
            "human_review_required": True,
            "decision_applied": True,
            "fusion_status": str(analysis.get("fusion_status")),
        }
    )
    if proposal == ILLEGAL_CATEGORY:
        updated["reason"] = (
            "Local policy evidence found both a covered subject and a current "
            "transaction or facilitation signal. This is a review-only product "
            "policy classification, not a legal determination."
        )
        updated["matched_signals"].append(
            "illegal_activities_v2_rc2:review_only_candidate"
        )
    else:
        updated["reason"] = (
            "Potential illegal-activity subject matter was detected, but "
            "transaction, licensing, location, or jurisdiction remains unclear."
        )
        updated["matched_signals"].append(
            "illegal_activities_v2_rc2:uncertain_review"
        )
    return updated


def get_illegal_activities_v2_rc2_status() -> dict[str, Any]:
    return {
        "version": "illegal-activities-v2-rc2",
        "policy_evidence_available": POLICY_PATH.is_file(),
        "permitted_outputs": [ILLEGAL_CATEGORY, UNCERTAIN_CATEGORY],
        "human_review_required": True,
        "automatic_enforcement_allowed": False,
        "legal_determination_authority": False,
        "external_advisory_category_authority": False,
        "external_advisory_enforcement_authority": False,
        "external_restricted_data_used": False,
    }
