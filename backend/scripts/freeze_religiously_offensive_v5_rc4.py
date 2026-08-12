from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_NAME = "religiously-offensive-v5-rc4"
SERVICE_PATH = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "religiously_offensive_v5_rc4_service.py"
)
CALIBRATION_SCRIPT = (
    ROOT
    / "backend"
    / "scripts"
    / "calibrate_religiously_offensive_v5_rc4_guard.py"
)
MODEL_DIRECTORY = (
    ROOT / "backend" / "storage" / "models" / "religiously_offensive_v5_rc4"
)
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v5_rc4_guard_development"
    / "validation_report.json"
)
BASE_CANDIDATE = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v4-rc3"
)
BASE_MANIFEST = BASE_CANDIDATE / "manifest.json"
BASE_VERDICT = BASE_CANDIDATE / "independent_evaluation_verdict.json"
TRAIN_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v4_rc3"
    / "train.csv"
)
VALIDATION_DATASET = TRAIN_DATASET.parent / "validation.csv"
CANDIDATE_PARENT = ROOT / "backend" / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE_NAME


# Locked before an RC4 holdout exists.
INDEPENDENT_GATE = {
    "minimum_binary_accuracy": 0.85,
    "minimum_religious_precision": 0.85,
    "minimum_religious_recall": 0.85,
    "minimum_religious_f1": 0.85,
    "minimum_nonreligious_specificity": 0.95,
    "minimum_neutral_religious_safe_rate": 0.95,
    "minimum_group_accuracy": 0.80,
    "maximum_category_mix_failures": 0,
    "maximum_action_contract_failures": 0,
    "maximum_processing_errors": 0,
    "require_follower_boundary_output_disabled": True,
    "require_zero_development_overlap": True,
    "require_zero_prior_challenge_reuse": True,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required RC4 freeze input is missing: {path}")


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


def dataset_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path.relative_to(ROOT)).replace("\\", "/"),
        "size_bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def main() -> None:
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "The frozen RC4 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )
    for path in (
        SERVICE_PATH,
        CALIBRATION_SCRIPT,
        MODEL_ARTIFACT,
        MODEL_CONFIG,
        DEVELOPMENT_REPORT,
        BASE_MANIFEST,
        BASE_VERDICT,
        TRAIN_DATASET,
        VALIDATION_DATASET,
    ):
        require_file(path)

    report = json.loads(DEVELOPMENT_REPORT.read_text(encoding="utf-8"))
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    base_manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    base_verdict = json.loads(BASE_VERDICT.read_text(encoding="utf-8"))
    if report.get("candidate") != "religiously-offensive-v5-rc4-development":
        raise RuntimeError("Unexpected RC4 development report.")
    if report.get("passed_development_gate") is not True:
        raise RuntimeError("RC4 did not pass its development gate.")
    if report.get("rc3_holdout_report_predictions_or_cases_used") is not False:
        raise RuntimeError("RC3 holdout material was used to calibrate RC4.")
    if report.get("classifier_retrained") is not False:
        raise RuntimeError("RC4 must use the frozen base classifier unchanged.")
    if report.get("connected_to_live_moderation") is not False:
        raise RuntimeError("RC4 must remain disconnected before freezing.")
    if report.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC4 must remain review-only.")
    if base_manifest.get("candidate") != "religiously-offensive-v4-rc3":
        raise RuntimeError("Unexpected RC3 base manifest.")
    if base_verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("The RC3 predecessor record is inconsistent.")
    policy = dict(config.get("religious_only_guard_policy", {}))
    if policy.get("passed_development_gate") is not True:
        raise RuntimeError("The RC4 religious-only guard did not pass development.")
    if int(policy.get("category_mix_failures", -1)) != 0:
        raise RuntimeError("RC4 development still contains category mixing.")
    if config.get("base_classifier_sha256") != sha256_file(MODEL_ARTIFACT):
        raise RuntimeError("RC4 classifier does not match the frozen base classifier.")
    if sha256_file(TRAIN_DATASET) != base_manifest["datasets"]["train"]["sha256"]:
        raise RuntimeError("The base training dataset changed after RC3 freeze.")
    if sha256_file(VALIDATION_DATASET) != base_manifest["datasets"]["validation"]["sha256"]:
        raise RuntimeError("The base validation dataset changed after RC3 freeze.")

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="religiously-offensive-v5-rc4-freeze-",
        dir=CANDIDATE_PARENT,
    ) as temporary_name:
        temporary = Path(temporary_name)
        artifacts = [
            copy_artifact(
                MODEL_ARTIFACT,
                temporary / "model" / "classifier.joblib",
                "model/classifier.joblib",
            ),
            copy_artifact(
                MODEL_CONFIG,
                temporary / "model" / "config.json",
                "model/config.json",
            ),
            copy_artifact(
                SERVICE_PATH,
                temporary / "source_snapshot" / SERVICE_PATH.name,
                f"source_snapshot/{SERVICE_PATH.name}",
            ),
            copy_artifact(
                CALIBRATION_SCRIPT,
                temporary / "source_snapshot" / CALIBRATION_SCRIPT.name,
                f"source_snapshot/{CALIBRATION_SCRIPT.name}",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT,
                temporary / "development_evidence" / "report.json",
                "development_evidence/report.json",
            ),
        ]
        manifest = {
            "candidate": CANDIDATE_NAME,
            "component": "Religiously Offensive Content",
            "candidate_type": "religious-only semantic guard",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "base_candidate": "religiously-offensive-v4-rc3",
            "base_candidate_status": "Failed synthetic independent readiness gate",
            "base_classifier_retrained": False,
            "rc3_holdout_report_predictions_or_cases_used": False,
            "permitted_active_output": "Religiously Offensive Content only",
            "all_nonreligious_model_labels": "No religious-category override",
            "follower_boundary_output_enabled": False,
            "follower_boundary_owner": "Hate Speech & Discrimination V7",
            "development_gate_passed": True,
            "development_metrics": {
                "validation_records": report["validation_records"],
                "accuracy": policy["accuracy"],
                "religious_precision": policy["precision"],
                "religious_recall": policy["recall"],
                "religious_f1": policy["f1"],
                "nonreligious_specificity": policy["specificity"],
                "minimum_family_accuracy": policy["minimum_family_accuracy"],
                "neutral_religious_safe_rate": policy[
                    "neutral_religious_safe_rate"
                ],
                "category_mix_failures": policy["category_mix_failures"],
            },
            "embedding_model": config["embedding_model"],
            "embedding_model_revision": config["embedding_model_revision"],
            "datasets": {
                "train": dataset_record(TRAIN_DATASET),
                "validation": dataset_record(VALIDATION_DATASET),
            },
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc4": False,
            "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_enforcement_allowed": False,
            "required_action_if_later_integrated": "Remove and send for human review",
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

    print("RELIGIOUSLY OFFENSIVE CONTENT V5 RC4 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Guarded development gate passed: True")
    print("RC3 holdout report, predictions, and cases used: False")
    print("Base classifier retrained: False")
    print("Follower-boundary output enabled: False")
    print("Follower-boundary owner: Hate Speech & Discrimination V7")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC4 is frozen and ready for one religious-only independent challenge.")


if __name__ == "__main__":
    main()

