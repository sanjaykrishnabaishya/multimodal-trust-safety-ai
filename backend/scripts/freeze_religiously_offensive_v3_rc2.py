from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SERVICE_PATH = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "religiously_offensive_v3_rc2_service.py"
)
EVALUATOR_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "evaluate_religiously_offensive_v3_rc2_development.py"
)
DEVELOPMENT_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v3_rc2"
    / "development.csv"
)
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v3_rc2_development"
    / "report.json"
)
FAILED_RC1_VERDICT = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v2-rc1"
    / "independent_evaluation_verdict.json"
)
CANDIDATE_PARENT = ROOT / "backend" / "storage" / "candidates"
CANDIDATE_NAME = "religiously-offensive-v3-rc2"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE_NAME
REQUIRED_ACTION = "Remove and send for human review"


# Locked before any RC2 independent challenge is created or evaluated.
INDEPENDENT_GATE = {
    "minimum_overall_accuracy": 0.85,
    "minimum_religious_precision": 0.85,
    "minimum_religious_recall": 0.85,
    "minimum_safe_specificity": 0.85,
    "minimum_boundary_accuracy": 0.85,
    "minimum_group_accuracy": 0.80,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_processing_errors": 0,
    "require_zero_development_overlap": True,
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


def main() -> None:
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "The frozen RC2 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )

    for path in (
        SERVICE_PATH,
        EVALUATOR_PATH,
        DEVELOPMENT_DATASET,
        DEVELOPMENT_REPORT,
        FAILED_RC1_VERDICT,
    ):
        require_file(path)

    development = json.loads(DEVELOPMENT_REPORT.read_text(encoding="utf-8"))
    if development.get("candidate") != "religiously-offensive-v3-rc2-development":
        raise RuntimeError("Unexpected V3 RC2 development report candidate.")
    if development.get("passed_development_gate") is not True:
        raise RuntimeError("V3 RC2 did not pass its development gate.")
    if development.get("prior_development_overlap") != 0:
        raise RuntimeError("V3 RC2 development contains prior-development overlap.")
    if development.get("connected_to_live_moderation") is not False:
        raise RuntimeError("V3 RC2 must remain disconnected before freezing.")
    if development.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("V3 RC2 must remain review-only before freezing.")
    if development.get("rc1_holdout_used_for_training_or_tuning") is not False:
        raise RuntimeError("The failed RC1 holdout must not be used to tune RC2.")

    rc1_verdict = json.loads(FAILED_RC1_VERDICT.read_text(encoding="utf-8"))
    if rc1_verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("The predecessor RC1 failure record is inconsistent.")

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="religiously-offensive-v3-rc2-freeze-",
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
                EVALUATOR_PATH,
                temporary / "source_snapshot" / EVALUATOR_PATH.name,
                f"source_snapshot/{EVALUATOR_PATH.name}",
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
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "candidate_type": "deterministic clause-level policy-boundary specialist",
            "predecessor_candidate": "religiously-offensive-v2-rc1",
            "predecessor_status": "Failed synthetic independent readiness gate",
            "rc1_holdout_used_for_rc2_training_or_tuning": False,
            "permitted_active_output": "Religiously Offensive Content",
            "protected_follower_boundary": "Hate Speech & Discrimination",
            "safe_context_behavior": "No religious-category override",
            "unrelated_category_behavior": "No category override",
            "development_gate_passed": True,
            "development_metrics": {
                "records": development["records"],
                "accuracy": development["accuracy"],
                "religious_precision": development["religious_precision"],
                "religious_recall": development["religious_recall"],
                "safe_specificity": development["safe_specificity"],
                "boundary_accuracy": development["boundary_accuracy"],
                "minimum_group_accuracy": development["minimum_group_accuracy"],
                "false_positives": development["false_positives"],
                "false_negatives": development["false_negatives"],
            },
            "development_dataset": {
                "path": str(DEVELOPMENT_DATASET.relative_to(ROOT)).replace("\\", "/"),
                "size_bytes": DEVELOPMENT_DATASET.stat().st_size,
                "sha256": sha256_file(DEVELOPMENT_DATASET),
            },
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc2": False,
            "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_enforcement_allowed": False,
            "required_action_if_later_integrated": REQUIRED_ACTION,
            "evaluation_reporting_contract": {
                "store_raw_holdout_text": False,
                "store_individual_predictions": False,
                "print_individual_predictions": False,
                "report_aggregate_metrics_only": True,
            },
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(CANDIDATE_DIRECTORY)

    print("RELIGIOUSLY OFFENSIVE CONTENT V3 RC2 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("RC1 holdout used for RC2 tuning: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC2 is frozen and ready for a new independent challenge.")


if __name__ == "__main__":
    main()
