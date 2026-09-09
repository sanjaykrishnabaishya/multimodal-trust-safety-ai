"""RC5 general unauthorized identity-material and impact evidence rule."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc4_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc4,
    apply_identity_theft_impersonation_v2_rc4_fusion,
)

POLICY_PATH = Path(__file__).resolve().parents[1] / "evidence/identity_theft_impersonation_v2_rc5_policy.json"
IDENTITY_MATERIAL_TERMS = (
    "another person's identity", "another persons identity", "personal information",
    "financial information", "medical identity", "stolen identity",
    "stolen credentials", "login credentials", "account credentials",
    "customer account", "victim's account", "victims account",
)
UNAUTHORIZED_TERMS = (
    "without permission", "without authorization", "without consent",
    "stolen credentials", "stolen identity", "against the victim's wishes",
    "against the victims wishes", "fraudulently",
)
CONCRETE_IMPACT_TERMS = (
    "accessed the account", "took over the account", "changed the account email",
    "sent messages to contacts", "opened a new account", "opened an account",
    "created an account", "made purchases", "ran up charges", "applied for a loan",
    "claimed benefits", "filed taxes", "obtained medical care", "collects payments",
    "requested account access", "requests account access",
)
ACTIVE_CASE_TERMS = (
    "this user", "this account", "this applicant", "this transaction",
    "someone is", "someone has", "the attacker", "the fraudster",
    "evidence indicates", "victim reports", "verified victim report",
    "documented account record", "currently",
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


def analyze_identity_theft_impersonation_v2_rc5(
    text: str, input_sources: list[str],
) -> dict[str, Any]:
    result = analyze_identity_theft_impersonation_v2_rc4(text, input_sources)
    result["version"] = "identity-theft-impersonation-v2-rc5"
    normalized = _normalize(text)
    identity_material = _any(normalized, IDENTITY_MATERIAL_TERMS)
    unauthorized = _any(normalized, UNAUTHORIZED_TERMS)
    concrete_impact = _any(normalized, CONCRETE_IMPACT_TERMS)
    active_case = _any(normalized, ACTIVE_CASE_TERMS)
    uncertainty = bool(
        result.get("uncertainty_signal") or result.get("incomplete_evidence")
        or result.get("rc2_uncertainty_signal")
        or result.get("rc3_incomplete_evidence_signal"))
    result.update({
        "rc5_identity_material_signal": identity_material,
        "rc5_unauthorized_use_signal": unauthorized,
        "rc5_concrete_impact_signal": concrete_impact,
        "rc5_active_case_signal": active_case,
        "rc4_dependency_used": True,
        "rc4_independent_examples_used_for_rc5": False,
        "rc4_individual_predictions_used_for_rc5": False,
    })
    if not _policy_available() or result.get("proposed_category") == IDENTITY_CATEGORY:
        return result
    if result.get("authorized_context") or result.get("fusion_status") in SAFE_STATUSES:
        return result
    plausible = identity_material
    if plausible and uncertainty:
        result.update({
            "fusion_status": "identity_or_authorization_evidence_incomplete_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High", "confidence": .76,
            "human_review_required": True,
        })
    elif identity_material and unauthorized and concrete_impact and active_case:
        result.update({
            "fusion_status": "unauthorized_identity_material_and_impact_review_candidate",
            "proposed_category": IDENTITY_CATEGORY, "proposed_action": IDENTITY_ACTION,
            "proposed_severity": "High", "confidence": .94,
            "human_review_required": True,
        })
    return result


def apply_identity_theft_impersonation_v2_rc5_fusion(**kwargs: Any) -> dict[str, Any]:
    return apply_identity_theft_impersonation_v2_rc4_fusion(**kwargs)


def get_identity_theft_impersonation_v2_rc5_status() -> dict[str, Any]:
    return {
        "version": "identity-theft-impersonation-v2-rc5",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [IDENTITY_CATEGORY, UNCERTAIN_CATEGORY],
        "required_identity_action": IDENTITY_ACTION, "human_review_required": True,
        "general_two_part_evidence_rule_enabled": True,
        "unauthorized_identity_material_rule_enabled": True,
        "incomplete_evidence_fails_closed": True,
        "rc4_independent_examples_used_for_rc5": False,
        "real_identity_documents_stored": False, "raw_credentials_stored": False,
        "complete_personal_identifiers_stored": False,
        "face_or_voice_recognition_allowed": False, "biometric_embeddings_allowed": False,
        "appearance_based_identity_inference_allowed": False,
        "external_provider_used": False, "external_transmission_allowed": False,
        "automatic_account_suspension_allowed": False,
        "automatic_enforcement_allowed": False,
    }
