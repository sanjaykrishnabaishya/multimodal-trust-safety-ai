from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_NAME = "religiously-offensive-v4-rc3"
SERVICE_PATH = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "religiously_offensive_v4_rc3_service.py"
)
TRAINING_SCRIPT = (
    ROOT
    / "backend"
    / "scripts"
    / "train_religiously_offensive_v4_rc3_semantic.py"
)
MODEL_DIRECTORY = (
    ROOT / "backend" / "storage" / "models" / "religiously_offensive_v4_rc3"
)
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"
TRAIN_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v4_rc3"
    / "train.csv"
)
VALIDATION_DATASET = TRAIN_DATASET.parent / "validation.csv"
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v4_rc3_semantic_development"
    / "validation_report.json"
)
RC1_VERDICT = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v2-rc1"
    / "independent_evaluation_verdict.json"
)
RC2_VERDICT = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v3-rc2"
    / "independent_evaluation_verdict.json"
)
CANDIDATE_PARENT = ROOT / "backend" / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE_NAME


# Locked before the RC3 holdout is created or evaluated.
INDEPENDENT_GATE = {
    "minimum_external_decision_accuracy": 0.85,
    "minimum_religious_precision": 0.85,
    "minimum_religious_recall": 0.85,
    "minimum_religious_f1": 0.85,
    "minimum_follower_boundary_precision": 0.85,
    "minimum_follower_boundary_recall": 0.85,
    "minimum_follower_boundary_f1": 0.85,
    "minimum_nonreligious_specificity": 0.90,
    "minimum_neutral_religious_safe_rate": 0.95,
    "minimum_group_accuracy": 0.80,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_processing_errors": 0,
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
        raise FileNotFoundError(f"Required freeze input was not found: {path}")


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
            "The frozen RC3 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )
    for path in (
        SERVICE_PATH,
        TRAINING_SCRIPT,
        MODEL_ARTIFACT,
        MODEL_CONFIG,
        TRAIN_DATASET,
        VALIDATION_DATASET,
        DEVELOPMENT_REPORT,
        RC1_VERDICT,
        RC2_VERDICT,
    ):
        require_file(path)

    report = json.loads(DEVELOPMENT_REPORT.read_text(encoding="utf-8"))
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    rc1_verdict = json.loads(RC1_VERDICT.read_text(encoding="utf-8"))
    rc2_verdict = json.loads(RC2_VERDICT.read_text(encoding="utf-8"))
    if report.get("candidate") != "religiously-offensive-v4-rc3-development":
        raise RuntimeError("Unexpected RC3 development report.")
    if report.get("passed_development_gate") is not True:
        raise RuntimeError("RC3 did not pass its strengthened development gate.")
    if report.get("train_validation_text_overlap") != 0:
        raise RuntimeError("RC3 contains train/validation text overlap.")
    if report.get("train_validation_family_overlap") != 0:
        raise RuntimeError("RC3 contains train/validation template-family overlap.")
    if report.get("rc1_or_rc2_holdout_used_for_training_tuning_or_calibration") is not False:
        raise RuntimeError("A failed holdout was used to develop RC3.")
    if report.get("connected_to_live_moderation") is not False:
        raise RuntimeError("RC3 must remain disconnected before freezing.")
    if report.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC3 must remain review-only before freezing.")
    policy = dict(config.get("religious_output_policy", {}))
    if policy.get("passed_development_gate") is not True:
        raise RuntimeError("The RC3 selective policy did not pass development.")
    if int(policy.get("neutral_religious_harmful_overrides", -1)) != 0:
        raise RuntimeError("RC3 still creates harmful neutral-religious overrides.")
    if rc1_verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("The RC1 predecessor record is inconsistent.")
    if rc2_verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("The RC2 predecessor record is inconsistent.")

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="religiously-offensive-v4-rc3-freeze-",
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
                TRAINING_SCRIPT,
                temporary / "source_snapshot" / TRAINING_SCRIPT.name,
                f"source_snapshot/{TRAINING_SCRIPT.name}",
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
            "candidate_type": "semantic classifier with selective policy boundaries",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "predecessors": [
                {
                    "candidate": "religiously-offensive-v2-rc1",
                    "status": "Failed synthetic independent readiness gate",
                },
                {
                    "candidate": "religiously-offensive-v3-rc2",
                    "status": "Failed synthetic independent readiness gate",
                },
            ],
            "prior_holdouts_used_for_training_tuning_or_calibration": False,
            "permitted_active_output": "Religiously Offensive Content only",
            "protected_follower_boundary": "Hate Speech & Discrimination",
            "safe_context_behavior": "No religious-category override",
            "neutral_religious_behavior": "No harmful category override",
            "development_gate_passed": True,
            "development_metrics": {
                "training_records": report["training_records"],
                "validation_records": report["validation_records"],
                "accuracy": policy["accuracy"],
                "macro_f1": policy["macro_f1"],
                "religious_precision": policy["religious_precision"],
                "religious_recall": policy["religious_recall"],
                "religious_f1": policy["religious_f1"],
                "nonreligious_specificity": policy["nonreligious_specificity"],
                "neutral_religious_safe_rate": policy["neutral_religious_safe_rate"],
                "neutral_religious_harmful_overrides": policy[
                    "neutral_religious_harmful_overrides"
                ],
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
            "independent_holdout_may_modify_rc3": False,
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

    print("RELIGIOUSLY OFFENSIVE CONTENT V4 RC3 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Strengthened development gate passed: True")
    print("RC1/RC2 holdouts used for RC3 development: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC3 is frozen and ready for one independent challenge.")


if __name__ == "__main__":
    main()

