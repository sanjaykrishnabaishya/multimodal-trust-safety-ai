from __future__ import annotations

import pytest

from app.services.intellectual_property_v1_rc1_service import (
    IP_ACTION, IP_CATEGORY, analyze_intellectual_property_v1_rc1,
    apply_intellectual_property_v1_rc1_fusion,
)


def apply(category: str, action: str, analysis: dict) -> dict:
    return apply_intellectual_property_v1_rc1_fusion(
        category=category, severity="None", action=action, confidence=0.70,
        human_review_required=category != "Normal/Ignore", reason="Existing.",
        matched_signals=[], analysis=analysis,
    )


@pytest.mark.parametrize("text", [
    "This account uploads the full copyrighted movie without permission.",
    "Evidence indicates this post publishes the source code from commercial software without authorization.",
    "This seller lists counterfeit branded goods and falsely presents them as genuine.",
    "This site provides unauthorized downloads of a copyrighted book; no distribution licence exists.",
])
def test_strong_ip_evidence_routes_to_qualified_review(text: str) -> None:
    analysis = analyze_intellectual_property_v1_rc1(text, ["text"])
    decision = apply("Normal/Ignore", "Allow", analysis)
    assert decision["category"] == IP_CATEGORY
    assert decision["action"] == IP_ACTION
    assert decision["human_review_required"] is True
    assert decision["automatic_enforcement_allowed"] is False
    assert analysis["legal_determination_made"] is False


def test_uncertain_licence_fails_closed_to_review() -> None:
    analysis = analyze_intellectual_property_v1_rc1(
        "This upload shares full copies of an ebook, but permission cannot be verified.",
        ["visual_description"],
    )
    decision = apply("Normal/Ignore", "Allow", analysis)
    assert decision["category"] == "Uncertain"
    assert decision["action"] == "Refer to human review"
    assert analysis["licence_validity_determined"] is False


def test_documented_licence_is_no_override() -> None:
    analysis = analyze_intellectual_property_v1_rc1(
        "A valid distribution licence covers this official publisher upload of a copyrighted film.",
        ["text"],
    )
    assert apply("Normal/Ignore", "Allow", analysis)["category"] == "Normal/Ignore"
    assert analysis["fusion_status"] == "authorized_licensed_or_public_domain_no_override"


def test_bounded_criticism_is_no_override() -> None:
    analysis = analyze_intellectual_property_v1_rc1(
        "A critical review uses a brief clip for review from a copyrighted movie and does not substitute for the original.",
        ["text"],
    )
    assert apply("Normal/Ignore", "Allow", analysis)["category"] == "Normal/Ignore"
    assert analysis["fusion_status"] == "bounded_exception_context_no_override"


def test_logo_or_similarity_alone_is_not_proof() -> None:
    analysis = analyze_intellectual_property_v1_rc1(
        "A self-reported owner alleges infringement because the picture contains a logo.", ["text"])
    assert apply("Normal/Ignore", "Allow", analysis)["category"] == "Normal/Ignore"
    assert analysis["fusion_status"] == "weak_similarity_or_claim_evidence_no_override"


def test_established_safety_owner_is_preserved() -> None:
    analysis = analyze_intellectual_property_v1_rc1(
        "This account uploads the full copyrighted movie without permission.", ["text"])
    decision = apply("Child Exploitation", "Block and immediately escalate", analysis)
    assert decision["category"] == "Child Exploitation"
    assert decision["fusion_status"] == "blocked_by_established_category_owner"


def test_storage_external_and_legal_authority_are_disabled() -> None:
    analysis = analyze_intellectual_property_v1_rc1("A copyright registration guide.", ["text"])
    for key in (
        "raw_copyrighted_works_stored", "pirated_material_stored",
        "complainant_private_identifiers_stored", "ownership_inferred_from_appearance",
        "licence_validity_determined", "legal_exception_determined",
        "legal_determination_made", "external_provider_used",
        "external_transmission_allowed", "automatic_takedown_allowed",
    ):
        assert analysis[key] is False
