from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
BACKEND_DIRECTORY = ROOT_DIRECTORY / "backend"
CANDIDATE = "dangerous-content-v4-rc3"
CANDIDATE_PARENT = BACKEND_DIRECTORY / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE

SERVICE_PATH = (
    BACKEND_DIRECTORY / "app" / "services" / "dangerous_content_v4_rc3_service.py"
)
TRAINER_PATH = (
    BACKEND_DIRECTORY / "scripts" / "train_dangerous_content_v4_rc3_contrastive.py"
)
DIAGNOSTIC_PATH = (
    BACKEND_DIRECTORY
    / "scripts"
    / "diagnose_dangerous_content_v4_rc3_development.py"
)
FREEZE_SCRIPT_PATH = Path(__file__).resolve()

DATASET_DIRECTORY = (
    ROOT_DIRECTORY / "datasets" / "development" / "dangerous_content_v4_rc3"
)
TRAIN_PATH = DATASET_DIRECTORY / "train.csv"
VALIDATION_PATH = DATASET_DIRECTORY / "validation.csv"
DATASET_MANIFEST_PATH = DATASET_DIRECTORY / "manifest.json"

MODEL_DIRECTORY = (
    BACKEND_DIRECTORY / "storage" / "models" / "dangerous_content_v4_rc3"
)
MODEL_PATH = MODEL_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "config.json"
DEVELOPMENT_REPORT_PATH = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v4_rc3_contrastive_development"
    / "validation_report.json"
)
FORBIDDEN_PRE_FREEZE_PATHS = (
    ROOT_DIRECTORY
    / "datasets"
    / "evaluation"
    / "dangerous_content_v4_rc3_independent",
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v4_rc3_independent",
)

INDEPENDENT_GATE = {
    "minimum_accuracy": 0.90,
    "minimum_dangerous_precision": 0.90,
    "minimum_dangerous_recall": 0.90,
    "minimum_safe_specificity": 0.95,
    "minimum_f1": 0.90,
    "minimum_group_accuracy": 0.85,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
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


def main() -> None:
    required_paths = (
        SERVICE_PATH,
        TRAINER_PATH,
        DIAGNOSTIC_PATH,
        FREEZE_SCRIPT_PATH,
        TRAIN_PATH,
        VALIDATION_PATH,
        DATASET_MANIFEST_PATH,
        MODEL_PATH,
        CONFIG_PATH,
        DEVELOPMENT_REPORT_PATH,
    )
    for path in required_paths:
        require_file(path)

    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "A frozen RC3 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )

    preexisting_holdout_material = [
        str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()
    ]
    if preexisting_holdout_material:
        raise RuntimeError(
            "Independent material exists before freeze:\n- "
            + "\n- ".join(preexisting_holdout_material)
        )

    report = read_json(DEVELOPMENT_REPORT_PATH)
    configuration = read_json(CONFIG_PATH)
    dataset_manifest = read_json(DATASET_MANIFEST_PATH)
    policy = report.get("selective_policy", {})
    policy_metrics = policy.get("metrics", {})
    failures: list[str] = []

    if report.get("candidate") != "dangerous-content-v4-rc3-development":
        failures.append("Unexpected development candidate identity.")
    if report.get("development_gate_passed") is not True:
        failures.append("The V4 RC3 development gate did not pass.")
    if configuration.get("development_gate_passed") is not True:
        failures.append("The runtime configuration is not development-enabled.")
    if policy.get("enabled") is not True:
        failures.append("The selective Dangerous Content output is disabled.")

    for key in (
        "boundary_raw_accuracy",
        "boundary_raw_macro_f1",
        "hazard_raw_accuracy",
        "hazard_raw_macro_f1",
        "context_raw_accuracy",
        "context_raw_macro_f1",
    ):
        if float(report.get(key, 0.0)) < 0.85:
            failures.append(f"Development metric below 85%: {key}.")

    metric_minimums = {
        "accuracy": 0.90,
        "precision": 0.90,
        "recall": 0.90,
        "specificity": 0.95,
        "f1": 0.90,
    }
    for key, minimum in metric_minimums.items():
        if float(policy_metrics.get(key, 0.0)) < minimum:
            failures.append(
                f"Selective development metric below {minimum:.0%}: {key}."
            )
    if float(policy.get("minimum_family_accuracy", 0.0)) < 0.85:
        failures.append("A development family is below 85% accuracy.")
    if int(policy.get("category_mix_failures", -1)) != 0:
        failures.append("The development category-mix contract failed.")

    required_false_contracts = (
        "external_or_restricted_data_used",
        "actionable_harm_instructions_stored",
        "rc1_holdout_cases_read",
        "rc1_predictions_or_mismatches_read",
        "v3_rc2_validation_cases_reused",
        "connected_to_live_moderation",
        "automatic_enforcement_allowed",
    )
    for key in required_false_contracts:
        if report.get(key) is not False:
            failures.append(f"Unsafe or unexpected development contract: {key}.")
    if report.get("train_validation_text_overlap") != 0:
        failures.append("Training and validation text overlap is not zero.")
    if report.get("train_validation_family_overlap") != 0:
        failures.append("Training and validation family overlap is not zero.")
    if report.get("paired_contrastive_hazard_contexts") is not True:
        failures.append("Paired contrastive training is not documented.")
    if report.get("existing_category_owner_guard") is not True:
        failures.append("The established-category owner guard is not documented.")

    actual_model_sha256 = sha256_file(MODEL_PATH)
    if configuration.get("model_sha256") != actual_model_sha256:
        failures.append("The model hash does not match its runtime configuration.")
    if report.get("model_sha256") != actual_model_sha256:
        failures.append("The model hash does not match the development report.")
    if dataset_manifest.get("candidate") != report.get("candidate"):
        failures.append("The development dataset manifest identity does not match.")

    if failures:
        raise RuntimeError(
            "Dangerous Content V4 RC3 freeze validation failed:\n- "
            + "\n- ".join(failures)
        )

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="dangerous-content-v4-rc3-freeze-",
        dir=CANDIDATE_PARENT,
    ) as temporary_name:
        temporary_directory = Path(temporary_name)
        artifacts = [
            copy_artifact(
                SERVICE_PATH,
                temporary_directory / "source_snapshot" / SERVICE_PATH.name,
                f"source_snapshot/{SERVICE_PATH.name}",
            ),
            copy_artifact(
                TRAINER_PATH,
                temporary_directory / "source_snapshot" / TRAINER_PATH.name,
                f"source_snapshot/{TRAINER_PATH.name}",
            ),
            copy_artifact(
                DIAGNOSTIC_PATH,
                temporary_directory / "source_snapshot" / DIAGNOSTIC_PATH.name,
                f"source_snapshot/{DIAGNOSTIC_PATH.name}",
            ),
            copy_artifact(
                FREEZE_SCRIPT_PATH,
                temporary_directory / "source_snapshot" / FREEZE_SCRIPT_PATH.name,
                f"source_snapshot/{FREEZE_SCRIPT_PATH.name}",
            ),
            copy_artifact(
                MODEL_PATH,
                temporary_directory / "model" / MODEL_PATH.name,
                f"model/{MODEL_PATH.name}",
            ),
            copy_artifact(
                CONFIG_PATH,
                temporary_directory / "model" / CONFIG_PATH.name,
                f"model/{CONFIG_PATH.name}",
            ),
            copy_artifact(
                TRAIN_PATH,
                temporary_directory / "development" / TRAIN_PATH.name,
                f"development/{TRAIN_PATH.name}",
            ),
            copy_artifact(
                VALIDATION_PATH,
                temporary_directory / "development" / VALIDATION_PATH.name,
                f"development/{VALIDATION_PATH.name}",
            ),
            copy_artifact(
                DATASET_MANIFEST_PATH,
                temporary_directory / "development" / DATASET_MANIFEST_PATH.name,
                f"development/{DATASET_MANIFEST_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT_PATH,
                temporary_directory
                / "development_evidence"
                / DEVELOPMENT_REPORT_PATH.name,
                f"development_evidence/{DEVELOPMENT_REPORT_PATH.name}",
            ),
        ]
        manifest = {
            "candidate": CANDIDATE,
            "component": "Dangerous Content",
            "candidate_type": "three-signal contrastive semantic policy boundary",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                "training_records": report["training_records"],
                "validation_records": report["validation_records"],
                "boundary_raw_accuracy": report["boundary_raw_accuracy"],
                "boundary_raw_macro_f1": report["boundary_raw_macro_f1"],
                "hazard_raw_accuracy": report["hazard_raw_accuracy"],
                "hazard_raw_macro_f1": report["hazard_raw_macro_f1"],
                "context_raw_accuracy": report["context_raw_accuracy"],
                "context_raw_macro_f1": report["context_raw_macro_f1"],
                "selective_policy": policy,
            },
            "semantic_model_name": configuration["semantic_model_name"],
            "semantic_model_revision": configuration["semantic_model_revision"],
            "model_sha256": actual_model_sha256,
            "permitted_active_output": "Dangerous Content only",
            "all_other_decisions": "No Dangerous Content override",
            "hazard_evidence_required": True,
            "dangerous_advocacy_evidence_required": True,
            "safe_context_veto_locked": True,
            "established_category_owner_guard_locked": True,
            "paired_contrastive_training_locked": True,
            "external_data_used": False,
            "restricted_data_used": False,
            "actionable_harm_instructions_stored": False,
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc3": False,
            "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_enforcement_allowed": False,
            "required_action_if_later_integrated": (
                "Remove and send for human review"
            ),
            "evaluation_reporting_contract": {
                "store_raw_holdout_text": False,
                "store_individual_predictions": False,
                "print_individual_predictions": False,
                "report_aggregate_metrics_only": True,
            },
        }
        (temporary_directory / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary_directory.rename(CANDIDATE_DIRECTORY)

    print("DANGEROUS CONTENT V4 RC3 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Three-signal semantic policy locked: True")
    print("Safe-context veto locked: True")
    print("Established-category owner guard locked: True")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC3 is frozen and ready for one new independent challenge.")


if __name__ == "__main__":
    main()
