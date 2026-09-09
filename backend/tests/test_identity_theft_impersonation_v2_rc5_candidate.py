from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.services.identity_theft_impersonation_v2_rc5_fusion import (
    analyze_identity_theft_impersonation_v2_rc5_for_fusion,
    apply_identity_theft_impersonation_v2_rc5_guarded_fusion,
    get_identity_theft_impersonation_v2_rc5_readiness,
)

ROOT = Path(__file__).resolve().parents[2]
CDIR = ROOT / "backend/storage/candidates/identity-theft-impersonation-v2-rc5"


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def test_candidate_is_frozen_and_all_hashes_verify() -> None:
    manifest = json.loads((CDIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["candidate"] == "identity-theft-impersonation-v2-rc5"
    assert manifest["independent_holdout_created_before_freeze"] is False
    assert manifest["independent_holdout_used_before_freeze"] is False
    for artifact in manifest["artifacts"]:
        path = CDIR / artifact["relative_path"]
        assert path.is_file()
        assert sha(path) == artifact["sha256"]


def test_independent_gate_is_above_eighty_five_and_passed() -> None:
    manifest = json.loads((CDIR / "manifest.json").read_text(encoding="utf-8"))
    verdict = json.loads((CDIR / "independent_evaluation_verdict.json").read_text(encoding="utf-8"))
    gate = manifest["independent_gate_frozen_before_holdout"]
    for key in ("minimum_accuracy", "minimum_identity_precision", "minimum_identity_recall",
                "minimum_safe_specificity", "minimum_group_accuracy"):
        assert gate[key] > .85
    assert verdict["records"] == 1320
    assert verdict["passed_synthetic_independent_readiness_gate"] is True
    assert verdict["eligible_for_guarded_live_integration"] is True
    assert verdict["candidate_may_be_modified_using_this_holdout"] is False


def test_runtime_readiness_contracts() -> None:
    readiness = get_identity_theft_impersonation_v2_rc5_readiness()
    assert readiness["ready"] is True
    assert readiness["checks"]["frozen_live_and_dependency_hashes_verified"] is True
    assert readiness["checks"]["external_provider_disabled"] is True
    assert readiness["checks"]["biometric_and_appearance_inference_disabled"] is True
    assert readiness["automatic_account_suspension_allowed"] is False
    assert readiness["automatic_enforcement_allowed"] is False


def test_guarded_fusion_applies_review_only_identity_decision() -> None:
    analysis = analyze_identity_theft_impersonation_v2_rc5_for_fusion(
        "Someone is impersonating me using a cloned account.", ["text"])
    decision = apply_identity_theft_impersonation_v2_rc5_guarded_fusion(
        category="Normal/Ignore", severity="None", action="Allow", confidence=.70,
        human_review_required=False, reason="Baseline.", matched_signals=[], analysis=analysis)
    assert decision["category"] == "Identity Theft & Impersonation"
    assert decision["action"] == "Restrict account activity and send for identity review"
    assert decision["human_review_required"] is True
    assert decision["automatic_enforcement_allowed"] is False


def test_unsupported_input_cannot_override() -> None:
    analysis = analyze_identity_theft_impersonation_v2_rc5_for_fusion(
        "Someone is impersonating me using a cloned account.", ["image"])
    assert analysis["fusion_status"] == "unsupported_input_no_override"
    assert analysis["proposed_category"] == ""
    assert analysis["external_provider_used"] is False
