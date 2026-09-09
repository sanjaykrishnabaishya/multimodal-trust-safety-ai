"""RC3 incomplete-evidence boundary for Identity Theft & Impersonation V2."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc2_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc2,
    apply_identity_theft_impersonation_v2_rc2_fusion,
)

POLICY_PATH = Path(__file__).resolve().parents[1] / "evidence" / "identity_theft_impersonation_v2_rc3_policy.json"

PLAUSIBLE_IDENTITY_RISK_TERMS = (
    "impersonating", "pretending to be", "posing as", "fake profile",
    "fake account", "cloned account", "cloned profile", "cloned social media account",
    "duplicate profile", "identity theft", "identity fraud", "stolen identity",
    "stolen my identity", "account takeover", "account hijacking",
    "uses another person's identity", "uses personal information",
)
INCOMPLETE_EVIDENCE_TERMS = (
    "evidence is incomplete", "identity evidence is incomplete",
    "authorization cannot be verified", "authorization is unknown",
    "consent is unknown", "authenticity is unclear", "authenticity is uncertain",
    "account provenance is unknown", "profile provenance is unknown",
    "source account is unavailable", "source profile is unavailable",
    "only a screenshot is available", "only a profile photograph is available",
    "identity cannot be verified", "identity remains unverified",
    "not enough evidence", "intent cannot be established",
)
SAFE_STATUSES = {
    "safe_reporting_parody_or_education_no_override",
    "weak_name_face_logo_or_claim_no_override",
    "ordinary_identity_context_no_override",
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
    return payload.get("component") == IDENTITY_CATEGORY


def analyze_identity_theft_impersonation_v2_rc3(
    text: str, input_sources: list[str],
) -> dict[str, Any]:
    result = analyze_identity_theft_impersonation_v2_rc2(text, input_sources)
    result["version"] = "identity-theft-impersonation-v2-rc3"
    normalized = _normalize(text)
    plausible_risk = _any(normalized, PLAUSIBLE_IDENTITY_RISK_TERMS)
    incomplete_evidence = _any(normalized, INCOMPLETE_EVIDENCE_TERMS)
    result.update({
        "rc3_plausible_identity_risk_signal": plausible_risk,
        "rc3_incomplete_evidence_signal": incomplete_evidence,
        "rc2_dependency_used": True,
        "rc2_independent_examples_used_for_rc3": False,
        "rc2_individual_predictions_used_for_rc3": False,
    })
    if not _policy_available() or result.get("proposed_category"):
        return result
    if result.get("authorized_context") or result.get("fusion_status") in SAFE_STATUSES:
        return result
    if plausible_risk and incomplete_evidence:
        result.update({
            "fusion_status": "identity_or_authorization_evidence_incomplete_review",
            "proposed_category": UNCERTAIN_CATEGORY,
            "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High",
            "confidence": 0.76,
            "human_review_required": True,
        })
    return result


def apply_identity_theft_impersonation_v2_rc3_fusion(**kwargs: Any) -> dict[str, Any]:
    return apply_identity_theft_impersonation_v2_rc2_fusion(**kwargs)


def get_identity_theft_impersonation_v2_rc3_status() -> dict[str, Any]:
    return {
        "version": "identity-theft-impersonation-v2-rc3",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [IDENTITY_CATEGORY, UNCERTAIN_CATEGORY],
        "required_identity_action": IDENTITY_ACTION,
        "human_review_required": True,
        "natural_language_expansion_enabled": True,
        "incomplete_evidence_fails_closed": True,
        "rc2_independent_examples_used_for_rc3": False,
        "real_identity_documents_stored": False,
        "raw_credentials_stored": False,
        "complete_personal_identifiers_stored": False,
        "face_or_voice_recognition_allowed": False,
        "biometric_embeddings_allowed": False,
        "appearance_based_identity_inference_allowed": False,
        "external_provider_used": False,
        "external_transmission_allowed": False,
        "automatic_account_suspension_allowed": False,
        "automatic_enforcement_allowed": False,
    }
