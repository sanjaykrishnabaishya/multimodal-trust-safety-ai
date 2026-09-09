from __future__ import annotations

import pytest

from app.services.identity_theft_impersonation_v2_rc5_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, analyze_identity_theft_impersonation_v2_rc5,
    apply_identity_theft_impersonation_v2_rc5_fusion,
)


def apply(category: str, action: str, analysis: dict) -> dict:
    return apply_identity_theft_impersonation_v2_rc5_fusion(
        category=category, severity="None", action=action, confidence=.70,
        human_review_required=category != "Normal/Ignore", reason="Existing.",
        matched_signals=[], analysis=analysis)


@pytest.mark.parametrize("text", [
    "Someone is impersonating me using a cloned account.",
    "This caller is pretending to be official support and requested account access.",
    "This account uses financial information without authorization and applied for a loan.",
    "This user uses stolen credentials and accessed the account.",
])
def test_strong_identity_evidence_routes_to_review(text: str) -> None:
    analysis = analyze_identity_theft_impersonation_v2_rc5(text, ["text"])
    decision = apply("Normal/Ignore", "Allow", analysis)
    assert decision["category"] == IDENTITY_CATEGORY
    assert decision["action"] == IDENTITY_ACTION
    assert decision["human_review_required"] is True
    assert decision["automatic_enforcement_allowed"] is False
    assert analysis["identity_verified"] is False
    assert analysis["authorization_verified"] is False


def test_incomplete_identity_evidence_fails_closed_to_review() -> None:
    analysis = analyze_identity_theft_impersonation_v2_rc5(
        "A possible account using login credentials is described while authorization is unknown.",
        ["visual_description"])
    decision = apply("Normal/Ignore", "Allow", analysis)
    assert decision["category"] == "Uncertain"
    assert decision["action"] == "Refer to human review"
    assert analysis["rc5_identity_material_signal"] is True


def test_authorized_account_is_no_override() -> None:
    analysis = analyze_identity_theft_impersonation_v2_rc5(
        "Written authorization confirms the owner-approved representative.", ["text"])
    assert apply("Normal/Ignore", "Allow", analysis)["category"] == "Normal/Ignore"


def test_parody_and_reporting_are_no_override() -> None:
    for text in (
        "A clearly labelled parody account claims no official affiliation.",
        "A documentary reports on identity theft and no active account is described.",
    ):
        analysis = analyze_identity_theft_impersonation_v2_rc5(text, ["text"])
        assert apply("Normal/Ignore", "Allow", analysis)["category"] == "Normal/Ignore"


def test_established_safety_owner_is_preserved() -> None:
    analysis = analyze_identity_theft_impersonation_v2_rc5(
        "This user uses stolen credentials and accessed the account.", ["text"])
    decision = apply("Child Exploitation", "Block and immediately escalate", analysis)
    assert decision["category"] == "Child Exploitation"
    assert decision["fusion_status"] == "blocked_by_established_category_owner"


def test_sensitive_storage_biometrics_external_and_enforcement_are_disabled() -> None:
    analysis = analyze_identity_theft_impersonation_v2_rc5("An identity settings guide.", ["text"])
    for key in (
        "real_identity_documents_stored", "raw_credentials_stored",
        "complete_personal_identifiers_stored", "biometric_embeddings_stored",
        "face_recognition_used", "voice_identity_matching_used",
        "identity_inferred_from_appearance", "identity_verified",
        "authorization_verified", "deceptive_intent_determined",
        "external_provider_used", "external_transmission_allowed",
        "automatic_account_suspension_allowed", "automatic_enforcement_allowed",
    ):
        assert analysis[key] is False
