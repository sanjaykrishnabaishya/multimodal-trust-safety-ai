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
    / "religiously_offensive_v2_service.py"
)
EVALUATOR_PATH = (
    ROOT
    / "backend"
    / "scripts"
    / "evaluate_religiously_offensive_v2_development.py"
)
DEVELOPMENT_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v1"
    / "development.csv"
)
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "development_v2"
    / "report.json"
)
CANDIDATE_PARENT = ROOT / "backend" / "storage" / "candidates"
CANDIDATE_DIRECTORY = (
    CANDIDATE_PARENT / "religiously-offensive-v2-rc1"
)
CANDIDATE_NAME = "religiously-offensive-v2-rc1"

# Locked before an independent challenge is generated or evaluated.
INDEPENDENT_GATE = {
    "minimum_overall_accuracy": 0.85,
    "minimum_religious_precision": 0.85,
    "minimum_religious_recall": 0.85,
    "minimum_safe_specificity": 0.85,
    "minimum_boundary_accuracy": 0.85,
    "minimum_group_accuracy": 0.75,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_processing_errors": 0,
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
            "The frozen RC1 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )

    for path in (
        SERVICE_PATH,
        EVALUATOR_PATH,
        DEVELOPMENT_DATASET,
        DEVELOPMENT_REPORT,
    ):
        require_file(path)

    development = json.loads(
        DEVELOPMENT_REPORT.read_text(encoding="utf-8")
    )
    if development.get("candidate") != "religiously-offensive-v2-development":
        raise RuntimeError("Unexpected V2 development report candidate.")
    if development.get("passed_development_gate") is not True:
        raise RuntimeError("V2 did not pass its development gate.")
    if development.get("live_moderation_changed") is not False:
        raise RuntimeError("V2 must remain disconnected before freezing.")
    if development.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("V2 must remain review-only before freezing.")

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="religiously-offensive-v2-rc1-freeze-",
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
            "candidate_type": "deterministic policy-boundary specialist",
            "permitted_active_output": "Religiously Offensive Content",
            "protected_follower_boundary": "Hate Speech & Discrimination",
            "safe_context_behavior": "No religious-category override",
            "development_gate_passed": True,
            "development_metrics": {
                "records": development["records"],
                "accuracy": development["accuracy"],
                "precision": development["precision"],
                "recall": development["recall"],
                "specificity": development["specificity"],
                "boundary_accuracy": development["boundary_accuracy"],
                "false_positives": development["false_positives"],
                "false_negatives": development["false_negatives"],
            },
            "development_dataset": {
                "path": str(DEVELOPMENT_DATASET.relative_to(ROOT)).replace(
                    "\\", "/"
                ),
                "size_bytes": DEVELOPMENT_DATASET.stat().st_size,
                "sha256": sha256_file(DEVELOPMENT_DATASET),
            },
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "development_mismatches_may_modify_rc1_after_freeze": False,
            "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_enforcement_allowed": False,
            "required_action_if_later_integrated": (
                "Remove and send for human review"
            ),
        }
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(CANDIDATE_DIRECTORY)

    print("RELIGIOUSLY OFFENSIVE CONTENT V2 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC1 is frozen and ready for an independent challenge.")


if __name__ == "__main__":
    main()
