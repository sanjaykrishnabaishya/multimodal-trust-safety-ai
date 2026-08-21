from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.illegal_activities_v2_rc2_fusion import (
    analyze_illegal_activities_v2_rc2_for_fusion,
    apply_illegal_activities_v2_rc2_guarded_fusion,
    get_illegal_activities_v2_rc2_readiness,
)


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    ROOT / "backend" / "storage" / "candidates" / "illegal-activities-v2-rc2"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_candidate_is_frozen_and_all_hashes_verify() -> None:
    manifest = read_json(MANIFEST_PATH)
    assert manifest["candidate"] == "illegal-activities-v2-rc2"
    assert manifest["development_gate_passed"] is True
    assert manifest["independent_holdout_created_before_freeze"] is False
    assert manifest["independent_holdout_used_before_freeze"] is False
    assert manifest["rc1_holdout_cases_predictions_or_mismatches_used"] is False
    for artifact in manifest["artifacts"]:
        path = CANDIDATE_DIRECTORY / artifact["relative_path"]
        assert path.is_file()
        assert sha256_file(path) == artifact["sha256"]


def test_independent_gate_passed_above_eighty_five_percent() -> None:
    manifest = read_json(MANIFEST_PATH)
    verdict = read_json(VERDICT_PATH)
    gate = manifest["independent_gate_frozen_before_holdout"]
    assert gate["minimum_accuracy"] > 0.85
    assert gate["minimum_illegal_precision"] > 0.85
    assert gate["minimum_illegal_recall"] > 0.85
    assert gate["minimum_safe_specificity"] > 0.85
    assert gate["minimum_group_accuracy"] > 0.85
    assert verdict["passed_synthetic_independent_readiness_gate"] is True
    assert verdict["eligible_for_guarded_live_integration"] is True
    assert verdict["candidate_may_be_modified_using_this_holdout"] is False


def test_runtime_readiness_verifies_frozen_live_hashes() -> None:
    readiness = get_illegal_activities_v2_rc2_readiness()
    assert readiness["ready"] is True
    assert readiness["checks"]["frozen_live_hashes_verified"] is True
    assert readiness["automatic_enforcement_allowed"] is False


def test_guarded_fusion_applies_review_only_illegal_output() -> None:
    analysis = analyze_illegal_activities_v2_rc2_for_fusion(
        "A supplier offers controlled substances with delivery available.",
        ["text"],
    )
    decision = apply_illegal_activities_v2_rc2_guarded_fusion(
        category="Normal/Ignore",
        severity="None",
        action="Allow",
        confidence=0.70,
        human_review_required=False,
        reason="Baseline.",
        matched_signals=[],
        analysis=analysis,
    )
    assert decision["category"] == "Illegal Activities"
    assert decision["action"] == "Restrict and send for human review"
    assert decision["human_review_required"] is True
    assert decision["automatic_enforcement_allowed"] is False


def test_guarded_fusion_preserves_established_owner() -> None:
    analysis = analyze_illegal_activities_v2_rc2_for_fusion(
        "A supplier offers controlled substances with delivery available.",
        ["text"],
    )
    decision = apply_illegal_activities_v2_rc2_guarded_fusion(
        category="Spam, Scam & Phishing",
        severity="High",
        action="Block, warn, or limit distribution",
        confidence=0.91,
        human_review_required=True,
        reason="Existing owner.",
        matched_signals=["spam"],
        analysis=analysis,
    )
    assert decision["category"] == "Spam, Scam & Phishing"
    assert decision["action"] == "Block, warn, or limit distribution"
    assert decision["decision_applied"] is False
    assert decision["fusion_status"] == "blocked_by_established_category_owner"


def test_child_boundary_is_local_and_review_only() -> None:
    analysis = analyze_illegal_activities_v2_rc2_for_fusion(
        "A minor child is linked to a sexual private image.",
        ["text"],
    )
    assert analysis["fusion_status"] == "blocked_by_child_safety_boundary"
    assert analysis["proposed_category"] == ""
    assert analysis["openrouter"]["used"] is False
    assert analysis["automatic_enforcement_allowed"] is False


def test_non_textual_input_cannot_create_override() -> None:
    analysis = analyze_illegal_activities_v2_rc2_for_fusion(
        "A supplier offers controlled substances with delivery available.",
        ["image"],
    )
    assert analysis["fusion_status"] == "non_textual_input_no_override"
    assert analysis["proposed_category"] == ""
    assert analysis["openrouter"]["used"] is False
