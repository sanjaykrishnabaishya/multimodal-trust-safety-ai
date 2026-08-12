from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_NAME = "religiously-offensive-v6-rc5"
DEVELOPMENT_NAME = "religiously-offensive-v6-rc5-development"
SERVICE_PATH = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "religiously_offensive_v6_rc5_service.py"
)
CALIBRATION_SCRIPT = (
    ROOT
    / "backend"
    / "scripts"
    / "calibrate_religiously_offensive_v6_rc5_policy_gate.py"
)
FREEZE_SCRIPT = Path(__file__).resolve()
MODEL_DIRECTORY = (
    ROOT / "backend" / "storage" / "models" / "religiously_offensive_v6_rc5"
)
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v6_rc5_policy_gate_development"
    / "validation_report.json"
)
BASE_CANDIDATE = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v5-rc4"
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


# Locked before any RC5 independent challenge exists.
INDEPENDENT_GATE = {
    "minimum_binary_accuracy": 0.90,
    "minimum_religious_precision": 0.95,
    "minimum_religious_recall": 0.90,
    "minimum_religious_f1": 0.92,
    "minimum_nonreligious_specificity": 0.98,
    "minimum_neutral_religious_safe_rate": 0.98,
    "minimum_group_accuracy": 0.85,
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
        raise FileNotFoundError(f"Required RC5 freeze input is missing: {path}")


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
            "The frozen RC5 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )
    for path in (
        SERVICE_PATH,
        CALIBRATION_SCRIPT,
        FREEZE_SCRIPT,
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
    if report.get("candidate") != DEVELOPMENT_NAME:
        raise RuntimeError("Unexpected RC5 development report.")
    if config.get("candidate") != DEVELOPMENT_NAME:
        raise RuntimeError("Unexpected RC5 model configuration.")
    if report.get("passed_development_gate") is not True:
        raise RuntimeError("RC5 did not pass its development gate.")
    if report.get("rc4_holdout_report_predictions_or_cases_used") is not False:
        raise RuntimeError("RC4 holdout material was used to calibrate RC5.")
    if report.get("classifier_retrained") is not False:
        raise RuntimeError("RC5 must use the frozen base classifier unchanged.")
    if report.get("connected_to_live_moderation") is not False:
        raise RuntimeError("RC5 must remain disconnected before freezing.")
    if report.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC5 must remain review-only.")
    if int(report.get("category_mix_failures", -1)) != 0:
        raise RuntimeError("RC5 development still contains category mixing.")
    if float(report.get("religious_precision", 0.0)) < 0.95:
        raise RuntimeError("RC5 development precision is below its freeze gate.")
    if float(report.get("religious_recall", 0.0)) < 0.90:
        raise RuntimeError("RC5 development recall is below its freeze gate.")
    if float(report.get("nonreligious_specificity", 0.0)) < 0.98:
        raise RuntimeError("RC5 development specificity is below its freeze gate.")
    if config.get("policy_gate_source_sha256") != sha256_file(CALIBRATION_SCRIPT):
        raise RuntimeError("The RC5 calibration source changed after calibration.")
    if config.get("base_classifier_sha256") != sha256_file(MODEL_ARTIFACT):
        raise RuntimeError("The RC5 classifier hash is inconsistent.")
    if config.get("requires_semantic_signal") is not True:
        raise RuntimeError("RC5 semantic evidence is not required.")
    if config.get("requires_sacred_attack_anchor") is not True:
        raise RuntimeError("RC5 sacred-target anchoring is not required.")
    if config.get("safe_context_veto_enabled") is not True:
        raise RuntimeError("RC5 safe-context veto is disabled.")
    if config.get("protected_follower_veto_enabled") is not True:
        raise RuntimeError("RC5 protected-follower veto is disabled.")
    if config.get("follower_boundary_output_enabled") is not False:
        raise RuntimeError("RC5 must not output the protected-follower boundary.")
    if base_manifest.get("candidate") != "religiously-offensive-v5-rc4":
        raise RuntimeError("Unexpected RC4 base manifest.")
    if base_verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("The RC4 predecessor status is inconsistent.")
    if base_verdict.get("holdout_may_modify_rc4") is not False:
        raise RuntimeError("The RC4 holdout integrity contract is invalid.")
    if sha256_file(TRAIN_DATASET) != base_manifest["datasets"]["train"]["sha256"]:
        raise RuntimeError("The base training dataset changed after RC4 freeze.")
    if sha256_file(VALIDATION_DATASET) != base_manifest["datasets"]["validation"]["sha256"]:
        raise RuntimeError("The base validation dataset changed after RC4 freeze.")

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="religiously-offensive-v6-rc5-freeze-",
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
                FREEZE_SCRIPT,
                temporary / "source_snapshot" / FREEZE_SCRIPT.name,
                f"source_snapshot/{FREEZE_SCRIPT.name}",
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
            "candidate_type": "semantic plus sacred-target policy gate",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "base_candidate": "religiously-offensive-v5-rc4",
            "base_candidate_status": "Failed religious-only synthetic independent readiness gate",
            "base_classifier_retrained": False,
            "rc4_holdout_report_predictions_or_cases_used": False,
            "policy_gate_version": config["policy_gate_version"],
            "requires_semantic_signal": True,
            "requires_sacred_attack_anchor": True,
            "safe_context_veto_enabled": True,
            "protected_follower_veto_enabled": True,
            "permitted_active_output": "Religiously Offensive Content only",
            "all_other_decisions": "No religious-category override",
            "follower_boundary_output_enabled": False,
            "follower_boundary_owner": "Hate Speech & Discrimination V7",
            "development_gate_passed": True,
            "development_metrics": {
                "validation_records": report["validation_records"],
                "accuracy": report["accuracy"],
                "religious_precision": report["religious_precision"],
                "religious_recall": report["religious_recall"],
                "religious_f1": report["religious_f1"],
                "nonreligious_specificity": report["nonreligious_specificity"],
                "minimum_family_accuracy": report["minimum_family_accuracy"],
                "neutral_religious_safe_rate": report[
                    "neutral_religious_safe_rate"
                ],
                "category_mix_failures": report["category_mix_failures"],
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
            "independent_holdout_may_modify_rc5": False,
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

    print("RELIGIOUSLY OFFENSIVE CONTENT V6 RC5 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Policy-gate development passed: True")
    print("RC4 holdout report, predictions, and cases used: False")
    print("Base classifier retrained: False")
    print("Semantic signal required: True")
    print("Sacred-target attack anchor required: True")
    print("Safe-context veto enabled: True")
    print("Protected-follower veto enabled: True")
    print("Follower-boundary output enabled: False")
    print("Follower-boundary owner: Hate Speech & Discrimination V7")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC5 is frozen and ready for one new religious-only independent challenge.")


if __name__ == "__main__":
    main()
