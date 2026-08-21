"""Freeze the review-only Illegal Activities V1 candidate before holdout use."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "illegal-activities-v1-rc1"
CANDIDATE_PARENT = BACKEND / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE

SERVICE_PATH = BACKEND / "app" / "services" / "illegal_activities_v1_service.py"
OPENROUTER_PATH = (
    BACKEND / "app" / "services" / "openrouter_advisory_service.py"
)
POLICY_PATH = BACKEND / "app" / "evidence" / "illegal_activities_v1_policy.json"
DEVELOPMENT_EVALUATOR_PATH = (
    BACKEND / "scripts" / "evaluate_illegal_activities_v1_development.py"
)
FREEZE_SCRIPT_PATH = Path(__file__).resolve()
DEVELOPMENT_DATASET_PATH = (
    ROOT / "datasets" / "development" / "illegal_activities_v1" / "development.csv"
)
DEVELOPMENT_REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v1_ai_advisory_development"
    / "report.json"
)
INDEPENDENT_REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v1_rc1_independent"
)

INDEPENDENT_GATE = {
    "minimum_accuracy": 0.90,
    "minimum_illegal_precision": 0.92,
    "minimum_illegal_recall": 0.90,
    "minimum_safe_specificity": 0.95,
    "minimum_f1": 0.90,
    "minimum_group_accuracy": 0.86,
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


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required freeze input is missing: {path}")


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def copy_artifact(
    source: Path,
    destination: Path,
    relative_path: str,
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "relative_path": relative_path,
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def validate_development(report: dict[str, Any]) -> None:
    failures: list[str] = []
    if report.get("version") != (
        "2026.08-illegal-activities-v1-ai-advisory-development"
    ):
        failures.append("Unexpected development candidate identity.")
    if report.get("passed_development_gate") is not True:
        failures.append("The development gate did not pass.")
    if int(report.get("records", 0)) != 320:
        failures.append("The development record count is not 320.")
    if int(report.get("unique_texts", 0)) != 320:
        failures.append("Development texts are not unique.")
    minimums = {
        "accuracy": 0.90,
        "illegal_precision": 0.90,
        "illegal_recall": 0.85,
        "safe_specificity": 0.95,
        "minimum_group_accuracy": 0.85,
    }
    for key, minimum in minimums.items():
        if float(report.get(key, 0.0)) < minimum:
            failures.append(f"Development metric below gate: {key}.")
    for key in ("action_contract_failures", "processing_errors"):
        if int(report.get(key, -1)) != 0:
            failures.append(f"Development contract is nonzero: {key}.")
    for key in (
        "openrouter_used",
        "external_or_restricted_data_used",
        "actionable_harm_instructions_stored",
        "automatic_enforcement_allowed",
    ):
        if report.get(key) is not False:
            failures.append(f"Unsafe development contract: {key}.")
    if failures:
        raise RuntimeError(
            "Illegal Activities V1 RC1 freeze validation failed:\n- "
            + "\n- ".join(failures)
        )


def validate_dataset(report: dict[str, Any]) -> None:
    if sha256_file(DEVELOPMENT_DATASET_PATH) != report.get("dataset_sha256"):
        raise RuntimeError("Development dataset hash differs from the report.")
    with DEVELOPMENT_DATASET_PATH.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    texts = [str(row.get("text", "")) for row in rows]
    if len(rows) != 320 or len(set(texts)) != 320 or not all(texts):
        raise RuntimeError("Development dataset uniqueness contract failed.")


def main() -> None:
    required = (
        SERVICE_PATH,
        OPENROUTER_PATH,
        POLICY_PATH,
        DEVELOPMENT_EVALUATOR_PATH,
        FREEZE_SCRIPT_PATH,
        DEVELOPMENT_DATASET_PATH,
        DEVELOPMENT_REPORT_PATH,
    )
    for path in required:
        require_file(path)
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "The Illegal Activities RC1 candidate already exists and will not "
            f"be overwritten: {CANDIDATE_DIRECTORY}"
        )
    if INDEPENDENT_REPORT_DIRECTORY.exists():
        raise RuntimeError("Independent material exists before candidate freeze.")

    report = read_json(DEVELOPMENT_REPORT_PATH)
    validate_development(report)
    validate_dataset(report)

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="illegal-activities-v1-rc1-freeze-",
        dir=CANDIDATE_PARENT,
    ) as temporary_name:
        temporary = Path(temporary_name)
        artifacts = [
            copy_artifact(
                SERVICE_PATH,
                temporary / "source_snapshot" / SERVICE_PATH.name,
                f"source_snapshot/{SERVICE_PATH.name}",
            ),
            copy_artifact(
                OPENROUTER_PATH,
                temporary / "source_snapshot" / OPENROUTER_PATH.name,
                f"source_snapshot/{OPENROUTER_PATH.name}",
            ),
            copy_artifact(
                POLICY_PATH,
                temporary / "policy_snapshot" / POLICY_PATH.name,
                f"policy_snapshot/{POLICY_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_EVALUATOR_PATH,
                temporary / "source_snapshot" / DEVELOPMENT_EVALUATOR_PATH.name,
                f"source_snapshot/{DEVELOPMENT_EVALUATOR_PATH.name}",
            ),
            copy_artifact(
                FREEZE_SCRIPT_PATH,
                temporary / "source_snapshot" / FREEZE_SCRIPT_PATH.name,
                f"source_snapshot/{FREEZE_SCRIPT_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_DATASET_PATH,
                temporary / "development" / DEVELOPMENT_DATASET_PATH.name,
                f"development/{DEVELOPMENT_DATASET_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT_PATH,
                temporary / "development_evidence" / DEVELOPMENT_REPORT_PATH.name,
                f"development_evidence/{DEVELOPMENT_REPORT_PATH.name}",
            ),
        ]
        manifest = {
            "candidate": CANDIDATE,
            "component": "Illegal Activities",
            "candidate_type": "review-only local policy plus non-authoritative AI advisory",
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
                    "minimum_group_accuracy",
                    "action_contract_failures",
                    "processing_errors",
                )
            },
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc1": False,
            "openrouter_bulk_evaluation_used": False,
            "openrouter_model_identifier": "openai/gpt-oss-20b",
            "external_model_weights_frozen": False,
            "external_advisory_has_category_authority": False,
            "external_advisory_has_enforcement_authority": False,
            "private_identifiers_sent_to_external_provider": False,
            "child_risk_sent_to_external_provider": False,
            "external_or_restricted_data_used": False,
            "actionable_harm_instructions_stored": False,
            "permitted_active_outputs": ["Illegal Activities", "Uncertain"],
            "required_action": "Restrict and send for human review",
            "established_category_ownership_preserved": True,
            "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": True,
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

    print("ILLEGAL ACTIVITIES V1 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Local service, policy, evaluator, and advisory hashes locked: True")
    print("External model weights frozen: False")
    print("External advisory category or enforcement authority: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Connected to live moderation: True")
    print("Automatic enforcement allowed: False")
    print("RC1 is frozen for one aggregate-only independent challenge.")


if __name__ == "__main__":
    main()
