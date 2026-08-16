from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = ROOT / "backend"
CANDIDATE_NAME = "dangerous-content-v2-rc1"
CANDIDATE_PARENT = BACKEND_ROOT / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE_NAME

SERVICE_PATH = (
    BACKEND_ROOT / "app" / "services" / "dangerous_content_v2_service.py"
)
V1_EVALUATOR = (
    BACKEND_ROOT / "scripts" / "evaluate_dangerous_content_v1_development.py"
)
V2_EVALUATOR = (
    BACKEND_ROOT / "scripts" / "evaluate_dangerous_content_v2_development.py"
)
FREEZE_SCRIPT = Path(__file__).resolve()
DEVELOPMENT_DATASET = (
    ROOT / "datasets" / "development" / "dangerous_content_v1" / "development.csv"
)
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "development_v2"
    / "report.json"
)

FORBIDDEN_PRE_FREEZE_PATHS = (
    ROOT / "datasets" / "evaluation" / "dangerous_content_v2_rc1",
    ROOT
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v2_rc1_independent",
)

INDEPENDENT_GATE = {
    "minimum_accuracy": 0.90,
    "minimum_dangerous_precision": 0.90,
    "minimum_dangerous_recall": 0.90,
    "minimum_safe_specificity": 0.95,
    "minimum_group_accuracy": 0.85,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_processing_errors": 0,
    "require_zero_development_overlap": True,
    "require_frozen_source_hashes": True,
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
    required = (
        SERVICE_PATH,
        V1_EVALUATOR,
        V2_EVALUATOR,
        FREEZE_SCRIPT,
        DEVELOPMENT_DATASET,
        DEVELOPMENT_REPORT,
    )
    for path in required:
        require_file(path)

    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "A frozen RC1 candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )

    preexisting = [
        str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()
    ]
    if preexisting:
        raise RuntimeError(
            "Independent material exists before freeze:\n- "
            + "\n- ".join(preexisting)
        )

    report = read_json(DEVELOPMENT_REPORT)
    failures: list[str] = []
    if report.get("component") != "Dangerous Content V2 boundary development":
        failures.append("Unexpected development component identity.")
    if report.get("passed_development_gate") is not True:
        failures.append("The V2 development gate did not pass.")
    for key in ("accuracy", "precision", "recall", "specificity", "f1"):
        if float(report.get(key, 0.0)) < 0.85:
            failures.append(f"Development metric below 85%: {key}.")
    if float(report.get("minimum_group_accuracy", 0.0)) < 0.85:
        failures.append("A development group is below 85%.")
    if report.get("action_contract_failures") != 0:
        failures.append("Development has action-contract failures.")
    if report.get("category_mix_failures") != 0:
        failures.append("Development has category-mix failures.")
    if report.get("preserves_other_category_owners") is not True:
        failures.append("Other category ownership is not preserved.")
    for key in (
        "automatic_enforcement_allowed",
        "connected_to_live_moderation",
        "external_data_used",
        "actionable_harm_instructions_stored",
    ):
        if report.get(key) is not False:
            failures.append(f"Unsafe development contract: {key}.")
    if failures:
        raise RuntimeError(
            "Dangerous Content RC1 freeze validation failed:\n- "
            + "\n- ".join(failures)
        )

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="dangerous-content-v2-rc1-freeze-",
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
                V1_EVALUATOR,
                temporary / "source_snapshot" / V1_EVALUATOR.name,
                f"source_snapshot/{V1_EVALUATOR.name}",
            ),
            copy_artifact(
                V2_EVALUATOR,
                temporary / "source_snapshot" / V2_EVALUATOR.name,
                f"source_snapshot/{V2_EVALUATOR.name}",
            ),
            copy_artifact(
                FREEZE_SCRIPT,
                temporary / "source_snapshot" / FREEZE_SCRIPT.name,
                f"source_snapshot/{FREEZE_SCRIPT.name}",
            ),
            copy_artifact(
                DEVELOPMENT_DATASET,
                temporary / "development" / "development.csv",
                "development/development.csv",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT,
                temporary / "development_evidence" / "report.json",
                "development_evidence/report.json",
            ),
        ]
        manifest = {
            "candidate": CANDIDATE_NAME,
            "component": "Dangerous Content",
            "candidate_type": "context-aware policy boundary parser",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                key: report[key]
                for key in (
                    "records",
                    "accuracy",
                    "precision",
                    "recall",
                    "specificity",
                    "f1",
                    "minimum_group_accuracy",
                    "action_contract_failures",
                    "category_mix_failures",
                )
            },
            "permitted_active_output": "Dangerous Content only",
            "all_other_decisions": "No Dangerous Content boundary override",
            "safe_reporting_veto_locked": True,
            "professional_control_veto_locked": True,
            "unsafe_absence_precedence_locked": True,
            "other_category_ownership_preserved": True,
            "external_data_used": False,
            "restricted_data_used": False,
            "actionable_harm_instructions_stored": False,
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc1": False,
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
        (temporary / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(CANDIDATE_DIRECTORY)

    print("DANGEROUS CONTENT V2 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Safe reporting veto locked: True")
    print("Professional-control veto locked: True")
    print("Other category ownership preserved: True")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC1 is frozen and ready for one independent challenge.")


if __name__ == "__main__":
    main()
