"""RC4 general two-part evidence rule for Identity Theft & Impersonation."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc3_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc3,
    apply_identity_theft_impersonation_v2_rc3_fusion,
)

POLICY_PATH = Path(__file__).resolve().parents[1] / "evidence" / "identity_theft_impersonation_v2_rc4_policy.json"
DECEPTIVE_IDENTITY_TERMS = (
    "impersonating", "impersonates", "pretending to be", "pretends to be",
    "posing as", "poses as", "falsely posing as", "falsely represents",
    "deceptively claims to represent", "fake account", "fake profile",
    "cloned account", "cloned profile", "duplicate profile",
)
ACTIVE_MISUSE_TERMS = (
    "sends messages", "sent messages", "messages contacts", "contacts friends",
    "contacts customers", "contacts colleagues", "solicits customers",
    "solicits users", "collects payments", "collects money", "requests payment",
    "requests payments", "request payments", "asks for payment", "requested account access",
    "requests account access", "request account access", "asks for account access",
    "asks for credentials", "requests credentials", "publishes posts as",
    "opened an account", "created an account", "changed the account email",
)
ACTIVE_CASE_TERMS = (
    "this account", "the account", "this profile", "the profile", "this caller",
    "the caller", "this message", "the message", "this person", "someone is",
    "someone has", "they are", "evidence indicates", "victim reports",
    "verified victim report", "currently",
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


def analyze_identity_theft_impersonation_v2_rc4(
    text: str, input_sources: list[str],
) -> dict[str, Any]:
    result = analyze_identity_theft_impersonation_v2_rc3(text, input_sources)
    result["version"] = "identity-theft-impersonation-v2-rc4"
    normalized = _normalize(text)
    deceptive_identity = _any(normalized, DECEPTIVE_IDENTITY_TERMS)
    active_misuse = _any(normalized, ACTIVE_MISUSE_TERMS)
    active_case = _any(normalized, ACTIVE_CASE_TERMS)
    uncertainty = bool(
        result.get("uncertainty_signal")
        or result.get("incomplete_evidence")
        or result.get("rc2_uncertainty_signal")
        or result.get("rc3_incomplete_evidence_signal")
    )
    result.update({
        "rc4_deceptive_identity_signal": deceptive_identity,
        "rc4_active_misuse_signal": active_misuse,
        "rc4_active_case_signal": active_case,
        "rc3_dependency_used": True,
        "rc3_independent_examples_used_for_rc4": False,
        "rc3_individual_predictions_used_for_rc4": False,
    })
    if not _policy_available() or result.get("proposed_category") == IDENTITY_CATEGORY:
        return result
    if result.get("authorized_context") or result.get("fusion_status") in SAFE_STATUSES:
        return result
    if deceptive_identity and uncertainty:
        result.update({
            "fusion_status": "identity_or_authorization_evidence_incomplete_review",
            "proposed_category": UNCERTAIN_CATEGORY,
            "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High",
            "confidence": 0.76,
            "human_review_required": True,
        })
    elif deceptive_identity and active_misuse and active_case:
        result.update({
            "fusion_status": "general_identity_deception_and_misuse_review_candidate",
            "proposed_category": IDENTITY_CATEGORY,
            "proposed_action": IDENTITY_ACTION,
            "proposed_severity": "High",
            "confidence": 0.94,
            "human_review_required": True,
        })
    return result


def apply_identity_theft_impersonation_v2_rc4_fusion(**kwargs: Any) -> dict[str, Any]:
    return apply_identity_theft_impersonation_v2_rc3_fusion(**kwargs)


def get_identity_theft_impersonation_v2_rc4_status() -> dict[str, Any]:
    return {
        "version": "identity-theft-impersonation-v2-rc4",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [IDENTITY_CATEGORY, UNCERTAIN_CATEGORY],
        "required_identity_action": IDENTITY_ACTION,
        "human_review_required": True,
        "general_two_part_evidence_rule_enabled": True,
        "incomplete_evidence_fails_closed": True,
        "rc3_independent_examples_used_for_rc4": False,
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
