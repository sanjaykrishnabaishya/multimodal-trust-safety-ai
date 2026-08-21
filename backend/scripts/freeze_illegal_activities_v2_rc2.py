"""Freeze the development-passing Illegal Activities V2 RC2 candidate."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "illegal-activities-v2-rc2"
CANDIDATE_DIRECTORY = BACKEND / "storage" / "candidates" / CANDIDATE
DEVELOPMENT_DATASET_PATH = (
    ROOT / "datasets" / "development" / "illegal_activities_v2_rc2" / "development.csv"
)
DEVELOPMENT_REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v2_rc2_policy_generalization_development"
    / "report.json"
)
RC1_VERDICT_PATH = (
    BACKEND
    / "storage"
    / "candidates"
    / "illegal-activities-v1-rc1"
    / "independent_evaluation_verdict.json"
)

ILLEGAL_CATEGORY = "Illegal Activities"
UNCERTAIN_CATEGORY = "Uncertain"

SOURCE_ARTIFACTS = {
    "source_snapshot/illegal_activities_v2_rc2_service.py": (
        BACKEND / "app" / "services" / "illegal_activities_v2_rc2_service.py"
    ),
    "source_snapshot/openrouter_advisory_service.py": (
        BACKEND / "app" / "services" / "openrouter_advisory_service.py"
    ),
    "policy_snapshot/illegal_activities_v2_rc2_policy.json": (
        BACKEND / "app" / "evidence" / "illegal_activities_v2_rc2_policy.json"
    ),
    "source_snapshot/evaluate_illegal_activities_v2_rc2_development.py": (
        BACKEND / "scripts" / "evaluate_illegal_activities_v2_rc2_development.py"
    ),
    "source_snapshot/freeze_illegal_activities_v2_rc2.py": Path(__file__).resolve(),
    "development/development.csv": DEVELOPMENT_DATASET_PATH,
    "development_evidence/report.json": DEVELOPMENT_REPORT_PATH,
}

INDEPENDENT_GATE = {
    "minimum_accuracy": 0.92,
    "minimum_illegal_precision": 0.95,
    "minimum_illegal_recall": 0.90,
    "minimum_safe_specificity": 0.97,
    "minimum_f1": 0.92,
    "minimum_group_accuracy": 0.90,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_authority_contract_failures": 0,
    "maximum_processing_errors": 0,
    "require_zero_development_overlap": True,
    "require_frozen_source_hashes": True,
    "require_no_raw_holdout_storage": True,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def verify_development(report: dict[str, Any]) -> None:
    required = {
        "passed_development_gate": True,
        "prior_development_overlap": 0,
        "action_contract_failures": 0,
        "category_mix_failures": 0,
        "processing_errors": 0,
        "rc1_holdout_cases_predictions_or_mismatches_read": False,
        "openrouter_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    for key, expected in required.items():
        if report.get(key) != expected:
            raise RuntimeError(f"Development report failed freeze requirement: {key}")
    if int(report.get("records", 0)) != 480:
        raise RuntimeError("Unexpected RC2 development record count.")
    if int(report.get("unique_texts", 0)) != 480:
        raise RuntimeError("RC2 development records are not unique.")
    if sha256_file(DEVELOPMENT_DATASET_PATH) != report.get("dataset_sha256"):
        raise RuntimeError("RC2 development dataset hash mismatch.")
    with DEVELOPMENT_DATASET_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 480 or len({row["text"] for row in rows}) != 480:
        raise RuntimeError("RC2 development CSV uniqueness verification failed.")


def main() -> None:
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            f"Frozen candidate already exists and will not be overwritten: {CANDIDATE_DIRECTORY}"
        )
    if not RC1_VERDICT_PATH.is_file():
        raise FileNotFoundError("RC1 aggregate verdict is required as provenance.")
    rc1_verdict = read_json(RC1_VERDICT_PATH)
    if rc1_verdict.get("candidate") != "illegal-activities-v1-rc1":
        raise RuntimeError("Unexpected RC1 provenance identity.")
    if rc1_verdict.get("candidate_may_be_modified_using_this_holdout") is not False:
        raise RuntimeError("RC1 holdout immutability contract is missing.")

    report = read_json(DEVELOPMENT_REPORT_PATH)
    verify_development(report)
    for source in SOURCE_ARTIFACTS.values():
        if not source.is_file():
            raise FileNotFoundError(source)

    temporary = CANDIDATE_DIRECTORY.with_name(CANDIDATE_DIRECTORY.name + ".tmp")
    if temporary.exists():
        raise FileExistsError(f"Temporary candidate path already exists: {temporary}")
    temporary.mkdir(parents=True)
    try:
        artifacts: list[dict[str, Any]] = []
        for relative_path, source in SOURCE_ARTIFACTS.items():
            destination = temporary / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            artifacts.append(
                {
                    "relative_path": relative_path,
                    "size_bytes": destination.stat().st_size,
                    "sha256": sha256_file(destination),
                }
            )

        manifest = {
            "candidate": CANDIDATE,
            "component": "Illegal Activities",
            "candidate_type": "review-only deterministic policy plus non-authoritative AI advisory",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                key: report[key]
                for key in (
                    "records",
                    "unique_texts",
                    "accuracy",
                    "illegal_precision",
                    "illegal_recall",
                    "safe_specificity",
                    "f1",
                    "minimum_group_accuracy",
                    "action_contract_failures",
                    "category_mix_failures",
                    "processing_errors",
                )
            },
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "rc1_aggregate_failure_signals_used": True,
            "rc1_holdout_cases_predictions_or_mismatches_used": False,
            "rc1_candidate_modified": False,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc2": False,
            "openrouter_bulk_evaluation_used": False,
            "openrouter_model_identifier": "openai/gpt-oss-20b",
            "external_model_weights_frozen": False,
            "external_advisory_has_category_authority": False,
            "external_advisory_has_enforcement_authority": False,
            "private_identifiers_sent_to_external_provider": False,
            "child_risk_sent_to_external_provider": False,
            "external_or_restricted_data_used": False,
            "actionable_harm_instructions_stored": False,
            "permitted_active_outputs": [ILLEGAL_CATEGORY, UNCERTAIN_CATEGORY],
            "required_action": "Restrict and send for human review",
            "established_category_ownership_preserved": True,
            "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_enforcement_allowed": False,
            "evaluation_reporting_contract": {
                "store_raw_holdout_text": False,
                "store_individual_predictions": False,
                "print_individual_predictions": False,
                "report_aggregate_metrics_only": True,
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(CANDIDATE_DIRECTORY)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    print("ILLEGAL ACTIVITIES V2 RC2 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("RC1 aggregate failure signals used: True")
    print("RC1 holdout cases, predictions, or mismatches used: False")
    print("Local service, policy, evaluator, advisory, and dataset hashes locked: True")
    print("External model weights frozen: False")
    print("External advisory category or enforcement authority: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC2 is frozen for one new aggregate-only independent challenge.")


if __name__ == "__main__":
    main()
