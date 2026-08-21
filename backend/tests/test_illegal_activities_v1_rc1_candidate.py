from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    ROOT / "backend" / "storage" / "candidates" / "illegal-activities-v1-rc1"
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


def test_candidate_is_frozen_and_hashes_verify() -> None:
    manifest = read_json(MANIFEST_PATH)
    assert manifest["candidate"] == "illegal-activities-v1-rc1"
    assert manifest["development_gate_passed"] is True
    assert manifest["independent_holdout_created_before_freeze"] is False
    assert manifest["independent_holdout_used_before_freeze"] is False
    for artifact in manifest["artifacts"]:
        frozen_path = CANDIDATE_DIRECTORY / artifact["relative_path"]
        assert frozen_path.is_file()
        assert sha256_file(frozen_path) == artifact["sha256"]


def test_locked_gate_exceeds_eighty_five_percent_accuracy_floor() -> None:
    gate = read_json(MANIFEST_PATH)["independent_gate_frozen_before_holdout"]
    assert gate["minimum_accuracy"] > 0.85
    assert gate["minimum_illegal_precision"] > 0.85
    assert gate["minimum_illegal_recall"] > 0.85
    assert gate["minimum_safe_specificity"] > 0.85
    assert gate["minimum_group_accuracy"] > 0.85


def test_independent_failure_is_preserved_without_enforcement_authority() -> None:
    verdict = read_json(VERDICT_PATH)
    assert verdict["candidate"] == "illegal-activities-v1-rc1"
    assert verdict["passed_synthetic_independent_readiness_gate"] is False
    assert verdict["eligible_for_guarded_live_integration"] is False
    assert verdict["automatic_enforcement_allowed"] is False
    assert verdict["candidate_may_be_modified_using_this_holdout"] is False
    assert verdict["raw_challenge_text_stored"] is False
    assert verdict["individual_predictions_stored"] is False


def test_external_advisory_never_has_decision_authority() -> None:
    manifest = read_json(MANIFEST_PATH)
    assert manifest["external_model_weights_frozen"] is False
    assert manifest["external_advisory_has_category_authority"] is False
    assert manifest["external_advisory_has_enforcement_authority"] is False
    assert manifest["private_identifiers_sent_to_external_provider"] is False
    assert manifest["child_risk_sent_to_external_provider"] is False
