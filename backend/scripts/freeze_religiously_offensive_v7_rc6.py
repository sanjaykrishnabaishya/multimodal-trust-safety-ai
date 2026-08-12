from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_NAME = "religiously-offensive-v7-rc6"
DEVELOPMENT_NAME = "religiously-offensive-v7-rc6-development"
SERVICE_PATH = (
    ROOT / "backend" / "app" / "services" / "religiously_offensive_v7_rc6_service.py"
)
CALIBRATION_SCRIPT = (
    ROOT
    / "backend"
    / "scripts"
    / "calibrate_religiously_offensive_v7_rc6_dual_evidence_gate.py"
)
FREEZE_SCRIPT = Path(__file__).resolve()
MODEL_DIRECTORY = (
    ROOT / "backend" / "storage" / "models" / "religiously_offensive_v7_rc6"
)
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v7_rc6_dual_evidence_development"
    / "validation_report.json"
)
EXPANSION_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v7_rc6"
    / "policy_expansion.csv"
)
BASE_TRAIN = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v4_rc3"
    / "train.csv"
)
BASE_VALIDATION = BASE_TRAIN.parent / "validation.csv"
BASE_CANDIDATE = (
    ROOT / "backend" / "storage" / "candidates" / "religiously-offensive-v6-rc5"
)
BASE_MANIFEST = BASE_CANDIDATE / "manifest.json"
BASE_VERDICT = BASE_CANDIDATE / "independent_evaluation_verdict.json"
RC5_AUDIT = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v6_rc5_pre_holdout_policy_contract"
    / "report.json"
)
CANDIDATE_PARENT = ROOT / "backend" / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE_NAME


INDEPENDENT_GATE = {
    "minimum_binary_accuracy": 0.90,
    "minimum_religious_precision": 0.95,
    "minimum_religious_recall": 0.90,
    "minimum_religious_f1": 0.92,
    "minimum_nonreligious_specificity": 0.98,
    "minimum_reported_advocacy_safe_rate": 0.98,
    "minimum_protected_follower_safe_rate": 0.98,
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
        raise FileNotFoundError(f"Required RC6 freeze input is missing: {path}")


def copy_artifact(source: Path, destination: Path, relative_path: str) -> dict[str, Any]:
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
            "The frozen RC6 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )
    for path in (
        SERVICE_PATH,
        CALIBRATION_SCRIPT,
        FREEZE_SCRIPT,
        MODEL_ARTIFACT,
        MODEL_CONFIG,
        DEVELOPMENT_REPORT,
        EXPANSION_DATASET,
        BASE_TRAIN,
        BASE_VALIDATION,
        BASE_MANIFEST,
        RC5_AUDIT,
    ):
        require_file(path)
    if BASE_VERDICT.exists():
        raise RuntimeError("RC5 unexpectedly received an independent verdict.")

    report = json.loads(DEVELOPMENT_REPORT.read_text(encoding="utf-8"))
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    base_manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    audit = json.loads(RC5_AUDIT.read_text(encoding="utf-8"))
    if report.get("candidate") != DEVELOPMENT_NAME or config.get("candidate") != DEVELOPMENT_NAME:
        raise RuntimeError("Unexpected RC6 development identity.")
    if report.get("passed_development_gate") is not True:
        raise RuntimeError("RC6 did not pass development.")
    if report.get("rc5_independent_holdout_created_or_used") is not False:
        raise RuntimeError("RC5 independent material was used for RC6.")
    if report.get("prior_holdout_records_read") is not False:
        raise RuntimeError("Prior holdout records were read for RC6.")
    if report.get("classifier_retrained") is not False:
        raise RuntimeError("RC6 must preserve the classifier unchanged.")
    if int(report.get("category_mix_failures", -1)) != 0:
        raise RuntimeError("RC6 development contains category mixing.")
    if float(report.get("religious_precision", 0.0)) < 0.98:
        raise RuntimeError("RC6 development precision is below its freeze gate.")
    if float(report.get("religious_recall", 0.0)) < 0.92:
        raise RuntimeError("RC6 development recall is below its freeze gate.")
    if float(report.get("reported_advocacy_safe_rate", 0.0)) != 1.0:
        raise RuntimeError("RC6 reported-advocacy safe routing is incomplete.")
    if float(report.get("protected_follower_safe_rate", 0.0)) != 1.0:
        raise RuntimeError("RC6 follower boundary routing is incomplete.")
    if config.get("policy_gate_source_sha256") != sha256_file(CALIBRATION_SCRIPT):
        raise RuntimeError("RC6 calibration source changed after calibration.")
    if config.get("base_classifier_sha256") != sha256_file(MODEL_ARTIFACT):
        raise RuntimeError("RC6 classifier hash is inconsistent.")
    if config.get("strong_safe_veto_enabled") is not True:
        raise RuntimeError("RC6 strong safe-context veto is disabled.")
    if config.get("reported_context_veto_enabled") is not True:
        raise RuntimeError("RC6 reported-context veto is disabled.")
    if config.get("protected_follower_veto_enabled") is not True:
        raise RuntimeError("RC6 follower veto is disabled.")
    if config.get("follower_boundary_output_enabled") is not False:
        raise RuntimeError("RC6 must not output the follower boundary.")
    if base_manifest.get("candidate") != "religiously-offensive-v6-rc5":
        raise RuntimeError("Unexpected RC5 base manifest.")
    if audit.get("passed_pre_holdout_policy_contract") is not False:
        raise RuntimeError("The recorded RC5 audit did not fail as expected.")
    if audit.get("independent_holdout_created_or_used") is not False:
        raise RuntimeError("The RC5 audit used an independent holdout.")

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="religiously-offensive-v7-rc6-freeze-", dir=CANDIDATE_PARENT
    ) as temporary_name:
        temporary = Path(temporary_name)
        artifacts = [
            copy_artifact(MODEL_ARTIFACT, temporary / "model" / "classifier.joblib", "model/classifier.joblib"),
            copy_artifact(MODEL_CONFIG, temporary / "model" / "config.json", "model/config.json"),
            copy_artifact(SERVICE_PATH, temporary / "source_snapshot" / SERVICE_PATH.name, f"source_snapshot/{SERVICE_PATH.name}"),
            copy_artifact(CALIBRATION_SCRIPT, temporary / "source_snapshot" / CALIBRATION_SCRIPT.name, f"source_snapshot/{CALIBRATION_SCRIPT.name}"),
            copy_artifact(FREEZE_SCRIPT, temporary / "source_snapshot" / FREEZE_SCRIPT.name, f"source_snapshot/{FREEZE_SCRIPT.name}"),
            copy_artifact(DEVELOPMENT_REPORT, temporary / "development_evidence" / "report.json", "development_evidence/report.json"),
        ]
        manifest = {
            "candidate": CANDIDATE_NAME,
            "component": "Religiously Offensive Content",
            "candidate_type": "dual-evidence sacred-target policy gate",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "base_candidate": "religiously-offensive-v6-rc5",
            "base_candidate_status": "Failed pre-holdout policy contract",
            "base_classifier_retrained": False,
            "rc5_independent_holdout_created_or_used": False,
            "prior_holdout_records_read": False,
            "policy_gate_version": config["policy_gate_version"],
            "decision_paths": config["decision_paths"],
            "strong_safe_veto_enabled": True,
            "reported_context_veto_enabled": True,
            "protected_follower_veto_enabled": True,
            "permitted_active_output": "Religiously Offensive Content only",
            "all_other_decisions": "No religious-category override",
            "follower_boundary_output_enabled": False,
            "follower_boundary_owner": "Hate Speech & Discrimination V7",
            "development_gate_passed": True,
            "development_metrics": config["development_metrics"],
            "embedding_model": config["embedding_model"],
            "embedding_model_revision": config["embedding_model_revision"],
            "datasets": {
                "train": dataset_record(BASE_TRAIN),
                "validation": dataset_record(BASE_VALIDATION),
                "policy_expansion": dataset_record(EXPANSION_DATASET),
            },
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc6": False,
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
            json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
        )
        temporary.rename(CANDIDATE_DIRECTORY)

    print("RELIGIOUSLY OFFENSIVE CONTENT V7 RC6 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Dual-evidence development gate passed: True")
    print("RC5 independent holdout created or used: False")
    print("Prior holdout records read: False")
    print("Base classifier retrained: False")
    print("Semantic and direct-advocacy evidence paths locked: True")
    print("Reported-context and protected-follower vetoes locked: True")
    print("Follower-boundary output enabled: False")
    print("Follower-boundary owner: Hate Speech & Discrimination V7")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC6 is frozen and ready for one new independent challenge.")


if __name__ == "__main__":
    main()
