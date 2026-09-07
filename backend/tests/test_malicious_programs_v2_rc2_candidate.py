from __future__ import annotations

import json

from app.services.malicious_programs_v2_rc2_fusion import (
    CANDIDATE_DIRECTORY,
    get_malicious_programs_v2_rc2_readiness,
    analyze_malicious_programs_v2_rc2_for_fusion,
)


def test_frozen_candidate_has_passing_independent_verdict() -> None:
    manifest = json.loads(
        (CANDIDATE_DIRECTORY / "manifest.json").read_text(
            encoding="utf-8"
        )
    )
    verdict = json.loads(
        (
            CANDIDATE_DIRECTORY
            / "independent_evaluation_verdict.json"
        ).read_text(encoding="utf-8")
    )
    assert manifest["development_gate_passed"] is True
    assert manifest["rc1_holdout_cases_or_predictions_used"] is False
    assert manifest["code_execution_allowed"] is False
    assert manifest["payload_storage_allowed"] is False
    assert verdict["passed_synthetic_independent_readiness_gate"] is True
    assert verdict["eligible_for_guarded_live_integration"] is True
    assert verdict["raw_challenge_text_stored"] is False
    assert verdict["individual_predictions_stored"] is False


def test_candidate_readiness_verifies_frozen_sources_and_dependencies() -> None:
    readiness = get_malicious_programs_v2_rc2_readiness()
    assert readiness["ready"] is True
    assert all(readiness["checks"].values())
    assert readiness["automatic_enforcement_allowed"] is False


def test_unsupported_binary_source_is_not_opened_or_overridden() -> None:
    analysis = analyze_malicious_programs_v2_rc2_for_fusion(
        "An attachment is present.",
        ["binary_attachment"],
    )
    assert analysis["fusion_status"] == "unsupported_input_no_override"
    assert analysis["proposed_category"] == ""
    assert analysis["code_executed"] is False
    assert analysis["archive_unpacked"] is False
    assert analysis["payload_stored"] is False
    assert analysis["automatic_enforcement_allowed"] is False
