"""Local, review-only Intellectual Property V1 RC1 policy router."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any


IP_CATEGORY = "Intellectual Property Infringement"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
IP_ACTION = "Restrict distribution and send for qualified human review"
UNCERTAIN_ACTION = "Refer to human review"
POLICY_PATH = Path(__file__).resolve().parents[1] / "evidence" / "intellectual_property_v1_rc1_policy.json"

PROTECTED_ITEM_TERMS = (
    "copyrighted film", "copyrighted movie", "television episode", "full episode",
    "copyrighted song", "music album", "copyrighted book", "ebook", "audiobook",
    "copyrighted photograph", "copyrighted artwork", "stock photograph",
    "commercial software", "source code", "video game", "paid course",
    "paywalled article", "subscription publication", "trademarked product",
    "branded goods", "registered trademark", "protected design",
)
UNAUTHORIZED_TERMS = (
    "without permission", "without authorization", "not authorized by the rights holder",
    "rights holder did not authorize", "no distribution licence", "unlicensed copy",
    "unauthorized copy", "pirated copy", "bootleg copy", "stolen copy",
    "counterfeit", "counterfeit product", "counterfeit goods", "fake branded goods",
    "falsely presented as genuine", "licence expressly forbids redistribution",
)
RIGHTS_IMPACTING_ACT_TERMS = (
    "uploads the full", "distributes full copies", "shares full copies", "sells copies",
    "offers copies for sale", "streams the full", "rebroadcasts the full",
    "mirrors the download", "reproduces the entire", "redistributes the package",
    "publishes the source code", "resells access", "bypasses the paywall and republishes",
    "lists counterfeit", "listing of counterfeit", "sells counterfeit", "imports counterfeit", "applies a fake logo",
    "removes the watermark and sells", "provides unauthorized downloads",
)
ACTIVE_CASE_TERMS = (
    "this account", "this user", "this upload", "this post", "this listing",
    "this seller", "this site", "this stream", "evidence indicates",
    "credible rights-holder report", "verified rights-holder notice", "currently",
)
AUTHORIZED_TERMS = (
    "written permission", "rights holder authorized", "licensed distribution",
    "valid distribution licence", "licence permits redistribution", "user-created original",
    "creator-owned original", "user-owned work", "official publisher upload",
    "official store link", "public domain", "cc0", "compatible creative commons licence",
    "open-source licence permits", "permission is documented",
)
EXCEPTION_CONTEXT_TERMS = (
    "criticism", "critical review", "commentary", "news reporting", "teaching",
    "scholarship", "academic research", "quotation", "parody", "pastiche",
    "library preservation", "archival preservation", "accessibility format",
)
BOUNDED_USE_TERMS = (
    "short attributed excerpt", "small attributed quotation", "brief clip for review",
    "thumbnail used for identification", "only what is needed for commentary",
    "does not substitute for the original", "links to the official source",
)
UNCERTAINTY_TERMS = (
    "ownership is disputed", "owner is unknown", "authorization is unclear",
    "permission cannot be verified", "licence is unknown", "licence scope is unclear",
    "licence validity is disputed", "jurisdiction is unknown", "applicable law is unclear",
    "fair use is unclear", "fair dealing is unclear", "exception scope is unresolved",
    "provenance is unknown", "rights-holder claim is unverified",
)
INCOMPLETE_EVIDENCE_TERMS = (
    "media could not be decoded", "unsupported media format", "metadata is incomplete",
    "only a thumbnail is available", "source page is unavailable", "evidence is incomplete",
)
WEAK_ONLY_TERMS = (
    "same title", "similar title", "contains a logo", "shows a watermark",
    "similar visual style", "inspired by the style", "looks similar", "shares a theme",
    "copyright notice", "trademark symbol", "self-reported owner", "alleges infringement",
)
ORDINARY_BENIGN_TERMS = (
    "copyright registration guide", "trademark application guide", "licence settings",
    "brand style guide", "software licence documentation", "official trailer",
    "official preview", "product review page", "library catalogue entry",
)
ESTABLISHED_OWNERS = {
    "Religiously Offensive Content", "Hate Speech & Discrimination",
    "Terrorism & Extremism", "Violent Content", "Dangerous Content",
    "Graphic, Obscene & Sexual Content", "Sexual Harassment",
    "Cyberbullying & Harassment", "Publishing Private Information",
    "Identity Theft & Impersonation", "Illegal Activities",
    "Misinformation & Fake News", "Spam, Scam & Phishing",
    "Invasion of Privacy", "Malicious Programs", "Abusive Words",
    "Child Exploitation",
}


def _normalize(text: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", text).casefold().split())


def _any(text: str, terms: tuple[str, ...]) -> bool:
    return any(term in text for term in terms)


def _policy_available() -> bool:
    try:
        payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("component") == IP_CATEGORY


def analyze_intellectual_property_v1_rc1(text: str, input_sources: list[str]) -> dict[str, Any]:
    normalized = _normalize(text)
    protected_item = _any(normalized, PROTECTED_ITEM_TERMS)
    unauthorized = _any(normalized, UNAUTHORIZED_TERMS)
    rights_act = _any(normalized, RIGHTS_IMPACTING_ACT_TERMS)
    active_case = _any(normalized, ACTIVE_CASE_TERMS)
    authorized = _any(normalized, AUTHORIZED_TERMS)
    exception_context = _any(normalized, EXCEPTION_CONTEXT_TERMS)
    bounded_use = _any(normalized, BOUNDED_USE_TERMS)
    uncertainty = _any(normalized, UNCERTAINTY_TERMS)
    incomplete = _any(normalized, INCOMPLETE_EVIDENCE_TERMS)
    weak_only = _any(normalized, WEAK_ONLY_TERMS)
    benign = _any(normalized, ORDINARY_BENIGN_TERMS)
    plausible_act = protected_item and (rights_act or unauthorized)

    result: dict[str, Any] = {
        "available": _policy_available(),
        "version": "intellectual-property-v1-rc1",
        "fusion_status": "no_intellectual_property_boundary_override",
        "proposed_category": "", "proposed_action": "", "proposed_severity": "",
        "confidence": 0.0, "human_review_required": False,
        "protected_item_signal": protected_item, "unauthorized_signal": unauthorized,
        "rights_impacting_act_signal": rights_act, "active_case": active_case,
        "authorized_or_licensed_context": authorized,
        "legal_exception_context": exception_context, "bounded_use_context": bounded_use,
        "uncertainty_signal": uncertainty, "incomplete_evidence": incomplete,
        "weak_evidence_only": weak_only,
        "raw_copyrighted_works_stored": False, "pirated_material_stored": False,
        "complainant_private_identifiers_stored": False,
        "ownership_inferred_from_appearance": False,
        "licence_validity_determined": False, "legal_exception_determined": False,
        "legal_determination_made": False, "external_provider_used": False,
        "external_transmission_allowed": False, "automatic_takedown_allowed": False,
        "automatic_enforcement_allowed": False, "warnings": [],
    }
    if not result["available"]:
        result["fusion_status"] = "policy_evidence_unavailable"
        return result
    if not normalized:
        result["fusion_status"] = "empty_input_no_override"
        return result
    if benign and not plausible_act:
        result["fusion_status"] = "ordinary_ip_context_no_override"
        return result
    if authorized and not unauthorized:
        result["fusion_status"] = "authorized_licensed_or_public_domain_no_override"
        return result
    if weak_only and not plausible_act:
        result["fusion_status"] = "weak_similarity_or_claim_evidence_no_override"
        return result
    if exception_context and bounded_use and not unauthorized:
        result["fusion_status"] = "bounded_exception_context_no_override"
        return result
    if plausible_act and (uncertainty or incomplete or (authorized and unauthorized)):
        result.update({
            "fusion_status": "ip_rights_or_legal_scope_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "Medium", "confidence": 0.76,
            "human_review_required": True,
        })
        return result
    if exception_context and plausible_act:
        result.update({
            "fusion_status": "ip_legal_exception_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "Medium", "confidence": 0.72,
            "human_review_required": True,
        })
        return result
    if protected_item and unauthorized and rights_act and active_case:
        result.update({
            "fusion_status": "intellectual_property_review_candidate",
            "proposed_category": IP_CATEGORY, "proposed_action": IP_ACTION,
            "proposed_severity": "High", "confidence": 0.94,
            "human_review_required": True,
        })
        return result
    if plausible_act and active_case:
        result.update({
            "fusion_status": "possible_ip_rights_impact_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "Medium", "confidence": 0.68,
            "human_review_required": True,
        })
    return result


def apply_intellectual_property_v1_rc1_fusion(
    *, category: str, severity: str, action: str, confidence: float,
    human_review_required: bool, reason: str, matched_signals: list[str],
    analysis: dict[str, Any],
) -> dict[str, Any]:
    updated = {
        "category": category, "severity": severity, "action": action,
        "confidence": confidence, "human_review_required": human_review_required,
        "reason": reason, "matched_signals": list(matched_signals),
        "decision_applied": False,
        "fusion_status": str(analysis.get("fusion_status", "unavailable")),
        "automatic_enforcement_allowed": False,
    }
    proposal = str(analysis.get("proposed_category", ""))
    if not proposal:
        return updated
    if category == IP_CATEGORY:
        updated["fusion_status"] = "intellectual_property_owner_already_applied"
        updated["human_review_required"] = True
        return updated
    if category in ESTABLISHED_OWNERS:
        updated["fusion_status"] = "blocked_by_established_category_owner"
        return updated
    if category not in {NORMAL_CATEGORY, UNCERTAIN_CATEGORY}:
        updated["fusion_status"] = "blocked_by_unknown_category_owner"
        return updated
    if category == UNCERTAIN_CATEGORY and proposal == UNCERTAIN_CATEGORY:
        updated["fusion_status"] = "uncertain_owner_already_applied"
        updated["human_review_required"] = True
        return updated
    updated.update({
        "category": proposal,
        "severity": str(analysis.get("proposed_severity", "Medium")),
        "action": str(analysis.get("proposed_action", UNCERTAIN_ACTION)),
        "confidence": min(0.98, max(confidence, float(analysis.get("confidence", 0.0)))),
        "human_review_required": True, "decision_applied": True,
        "fusion_status": str(analysis.get("fusion_status")),
    })
    if proposal == IP_CATEGORY:
        updated["reason"] = (
            "Local evidence pairs a protected item with a current unauthorized copying, "
            "distribution, performance, access, or counterfeit act. A qualified reviewer "
            "must verify rights, licence, jurisdiction, and exceptions."
        )
        updated["matched_signals"].append("intellectual_property_v1_rc1:review_only")
    else:
        updated["reason"] = (
            "Ownership, authorization, licence, provenance, jurisdiction, evidence, or a "
            "legal exception is unresolved; the tool made no legal determination."
        )
        updated["matched_signals"].append("intellectual_property_v1_rc1:uncertain_review")
    return updated


def get_intellectual_property_v1_rc1_status() -> dict[str, Any]:
    return {
        "version": "intellectual-property-v1-rc1",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [IP_CATEGORY, UNCERTAIN_CATEGORY],
        "required_ip_action": IP_ACTION, "human_review_required": True,
        "raw_copyrighted_works_stored": False, "pirated_material_stored": False,
        "ownership_or_licence_inference_allowed": False,
        "legal_determination_allowed": False,
        "external_provider_used": False, "external_transmission_allowed": False,
        "automatic_takedown_allowed": False, "automatic_enforcement_allowed": False,
    }
