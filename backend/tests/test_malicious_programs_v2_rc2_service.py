from __future__ import annotations

import pytest

from app.services.malicious_programs_v1_rc1_service import (
    MALICIOUS_ACTION,
    MALICIOUS_CATEGORY,
    NORMAL_CATEGORY,
    UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
)
from app.services.malicious_programs_v2_rc2_service import (
    analyze_malicious_programs_v2_rc2,
    apply_malicious_programs_v2_rc2_fusion,
)


def _apply(text: str, category: str = NORMAL_CATEGORY) -> tuple[dict, dict]:
    analysis = analyze_malicious_programs_v2_rc2(text, ["text"])
    decision = apply_malicious_programs_v2_rc2_fusion(
        category=category,
        severity="None" if category == NORMAL_CATEGORY else "High",
        action="Allow" if category == NORMAL_CATEGORY else "Existing action",
        confidence=0.70,
        human_review_required=category != NORMAL_CATEGORY,
        reason="Existing decision.",
        matched_signals=[],
        analysis=analysis,
    )
    return analysis, decision


@pytest.mark.parametrize(
    "text",
    (
        "This upload distributes the malware to victim devices.",
        "Ransomware was published by the account for victim systems.",
        "A credential stealer is hosted for download by unrelated users.",
        "A destructive wiper is delivered for installation on endpoints.",
    ),
)
def test_operational_malicious_evidence_routes_to_security_review(
    text: str,
) -> None:
    analysis, decision = _apply(text)
    assert analysis["proposed_category"] == MALICIOUS_CATEGORY
    assert decision["category"] == MALICIOUS_CATEGORY
    assert decision["action"] == MALICIOUS_ACTION
    assert decision["human_review_required"] is True
    assert decision["automatic_enforcement_allowed"] is False


def test_uncertain_attachment_is_not_opened_and_routes_to_review() -> None:
    analysis, decision = _apply(
        "This attachment is an unknown executable attachment and its "
        "purpose is unknown."
    )
    assert decision["category"] == UNCERTAIN_CATEGORY
    assert decision["action"] == UNCERTAIN_ACTION
    assert analysis["code_executed"] is False
    assert analysis["archive_unpacked"] is False
    assert analysis["payload_stored"] is False


@pytest.mark.parametrize(
    "text",
    (
        "A defensive malware analysis says ransomware was installed; "
        "it contains no executable payload.",
        "An incident response report says spyware was distributed; "
        "indicators are redacted.",
        "A legitimate remote administration tool supports approved users.",
        "A glossary contains the term ransomware without any attachment.",
    ),
)
def test_safe_and_lexical_contexts_do_not_create_override(text: str) -> None:
    analysis, decision = _apply(text)
    assert analysis["proposed_category"] == ""
    assert decision["category"] == NORMAL_CATEGORY
    assert decision["action"] == "Allow"
    assert decision["decision_applied"] is False


@pytest.mark.parametrize(
    "owner",
    (
        "Child Exploitation",
        "Illegal Activities",
        "Spam, Scam & Phishing",
        "Identity Theft & Impersonation",
        "Publishing Private Information",
        "Invasion of Privacy",
        "Terrorism & Extremism",
    ),
)
def test_established_category_owners_are_preserved(owner: str) -> None:
    _, decision = _apply(
        "Ransomware was distributed by the account to victim devices.",
        owner,
    )
    assert decision["category"] == owner
    assert decision["action"] == "Existing action"
    assert decision["decision_applied"] is False
    assert decision["fusion_status"] == "blocked_by_established_category_owner"


def test_analysis_never_claims_execution_storage_or_external_authority() -> None:
    analysis, _ = _apply(
        "This attachment deploys the malicious payload to victim devices."
    )
    for key in (
        "code_executed",
        "archive_unpacked",
        "payload_stored",
        "credentials_stored",
        "live_infrastructure_stored",
        "external_provider_used",
        "external_transmission_allowed",
        "automatic_enforcement_allowed",
        "rc1_holdout_cases_read",
        "rc1_individual_predictions_read",
        "rc1_mismatches_read",
    ):
        assert analysis[key] is False
