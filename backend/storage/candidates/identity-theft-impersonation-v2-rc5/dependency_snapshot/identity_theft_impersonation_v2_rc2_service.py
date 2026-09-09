"""RC2 natural-language expansion for the frozen Identity V2 policy."""

from __future__ import annotations

import json
import unicodedata
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc1_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc1,
    apply_identity_theft_impersonation_v2_rc1_fusion,
)

POLICY_PATH = Path(__file__).resolve().parents[1] / "evidence" / "identity_theft_impersonation_v2_rc2_policy.json"

NATURAL_IMPERSONATION_TERMS = (
    "impersonating me", "impersonating him", "impersonating her", "impersonating us",
    "impersonating our company", "impersonating my organization",
    "pretending to be me", "pretending to be him", "pretending to be her",
    "pretending to be us", "posing as me", "posing as him", "posing as her",
    "posing as our company", "copied my profile", "copied his profile",
    "copied her profile", "copied our profile", "cloned my account",
    "cloned his account", "cloned her account", "cloned our account",
    "fake account pretending", "fake support profile", "fake customer support profile",
)
NATURAL_MISUSE_ACT_TERMS = (
    "using a cloned account", "using the cloned account", "created a cloned account",
    "created a fake account", "created a fake profile", "made a fake profile",
    "using my photograph", "using his photograph", "using her photograph",
    "using my photo", "using his photo", "using her photo", "using my name",
    "using his name", "using her name", "copied my identity documents",
    "copied his identity documents", "copied her identity documents",
    "opened a fake account", "opened an account in my name", "opened an account in his name",
    "opened an account in her name", "ran up charges in my name",
    "made purchases in my name", "filed taxes in my name", "claimed benefits in my name",
)
NATURAL_ACTIVE_TERMS = (
    "someone is", "someone has", "this person", "this account", "this profile",
    "the account", "the profile", "they are", "they created", "they copied",
    "the attacker", "the fraudster", "victim reports", "evidence indicates",
)
IDENTITY_THEFT_TERMS = (
    "identity theft", "identity fraud", "stole my identity", "stole his identity",
    "stole her identity", "stolen my identity", "stolen his identity",
    "stolen her identity", "stolen identity", "account takeover", "account hijacking",
)
RC2_UNCERTAINTY_TERMS = (
    "may be impersonating", "might be impersonating", "possibly impersonating",
    "authenticity is uncertain", "cannot confirm who owns", "could be a parody",
    "could be authorized", "not enough evidence to verify", "identity remains unverified",
)


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


def analyze_identity_theft_impersonation_v2_rc2(text: str, input_sources: list[str]) -> dict[str, Any]:
    result = analyze_identity_theft_impersonation_v2_rc1(text, input_sources)
    result["version"] = "identity-theft-impersonation-v2-rc2"
    normalized = _normalize(text)
    natural_impersonation = _any(normalized, NATURAL_IMPERSONATION_TERMS)
    natural_misuse = _any(normalized, NATURAL_MISUSE_ACT_TERMS)
    natural_active = _any(normalized, NATURAL_ACTIVE_TERMS)
    identity_theft = _any(normalized, IDENTITY_THEFT_TERMS)
    rc2_uncertainty = _any(normalized, RC2_UNCERTAINTY_TERMS)
    result.update({
        "natural_language_impersonation_signal": natural_impersonation,
        "natural_language_misuse_act_signal": natural_misuse,
        "natural_language_active_case": natural_active,
        "identity_theft_statement_signal": identity_theft,
        "rc2_uncertainty_signal": rc2_uncertainty,
        "rc1_dependency_used": True,
        "rc1_independent_examples_used_for_rc2": False,
        "rc1_individual_predictions_used_for_rc2": False,
    })
    if not _policy_available() or result.get("proposed_category"):
        return result
    if result.get("authorized_context") or result.get("fusion_status") in {
        "safe_reporting_parody_or_education_no_override",
        "weak_name_face_logo_or_claim_no_override",
        "ordinary_identity_context_no_override",
    }:
        return result
    plausible = natural_impersonation or identity_theft
    if plausible and (result.get("uncertainty_signal") or result.get("incomplete_evidence") or rc2_uncertainty):
        result.update({
            "fusion_status": "identity_authorization_or_evidence_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High", "confidence": 0.76,
            "human_review_required": True,
        })
        return result
    if plausible and natural_misuse and natural_active:
        result.update({
            "fusion_status": "identity_natural_language_review_candidate",
            "proposed_category": IDENTITY_CATEGORY, "proposed_action": IDENTITY_ACTION,
            "proposed_severity": "High", "confidence": 0.94,
            "human_review_required": True,
        })
        return result
    if plausible and natural_active:
        result.update({
            "fusion_status": "possible_identity_misuse_uncertain_review",
            "proposed_category": UNCERTAIN_CATEGORY, "proposed_action": UNCERTAIN_ACTION,
            "proposed_severity": "High", "confidence": 0.68,
            "human_review_required": True,
        })
    return result


def apply_identity_theft_impersonation_v2_rc2_fusion(**kwargs: Any) -> dict[str, Any]:
    return apply_identity_theft_impersonation_v2_rc1_fusion(**kwargs)


def get_identity_theft_impersonation_v2_rc2_status() -> dict[str, Any]:
    return {
        "version": "identity-theft-impersonation-v2-rc2",
        "policy_evidence_available": _policy_available(),
        "permitted_outputs": [IDENTITY_CATEGORY, UNCERTAIN_CATEGORY],
        "required_identity_action": IDENTITY_ACTION, "human_review_required": True,
        "natural_language_expansion_enabled": True,
        "rc1_independent_examples_used_for_rc2": False,
        "real_identity_documents_stored": False, "raw_credentials_stored": False,
        "complete_personal_identifiers_stored": False,
        "face_or_voice_recognition_allowed": False, "biometric_embeddings_allowed": False,
        "appearance_based_identity_inference_allowed": False,
        "external_provider_used": False, "external_transmission_allowed": False,
        "automatic_account_suspension_allowed": False,
        "automatic_enforcement_allowed": False,
    }
