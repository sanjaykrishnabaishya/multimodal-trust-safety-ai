from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "graphic-sexual-content-v2-rc1"
CANDIDATE_PARENT = BACKEND / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE
SERVICE_PATH = (
    BACKEND / "app" / "services" / "graphic_sexual_content_v2_service.py"
)
V1_EVALUATOR_PATH = (
    BACKEND / "scripts" / "evaluate_graphic_sexual_content_v1_development.py"
)
V2_EVALUATOR_PATH = (
    BACKEND / "scripts" / "evaluate_graphic_sexual_content_v2_development.py"
)
FREEZE_PATH = Path(__file__).resolve()
DEVELOPMENT_DATASET_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "graphic_sexual_content_v1"
    / "development.csv"
)
DEVELOPMENT_REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "development_v2"
    / "report.json"
)
DEVELOPMENT_MISMATCH_PATH = DEVELOPMENT_REPORT_PATH.parent / "mismatches.csv"

FORBIDDEN_PRE_FREEZE_PATHS = (
    ROOT
    / "datasets"
    / "evaluation"
    / "graphic_sexual_content_v2_rc1_independent",
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "v2_rc1_independent",
)

INDEPENDENT_GATE = {
    "minimum_accuracy": 0.90,
    "minimum_graphic_sexual_precision": 0.90,
    "minimum_graphic_sexual_recall": 0.90,
    "minimum_sexual_harassment_precision": 0.90,
    "minimum_sexual_harassment_recall": 0.90,
    "minimum_no_override_recall": 0.95,
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
    required = (
        SERVICE_PATH,
        V1_EVALUATOR_PATH,
        V2_EVALUATOR_PATH,
        FREEZE_PATH,
        DEVELOPMENT_DATASET_PATH,
        DEVELOPMENT_REPORT_PATH,
        DEVELOPMENT_MISMATCH_PATH,
    )
    for path in required:
        require_file(path)
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "A frozen Graphic/Sexual RC1 candidate already exists and will "
            f"not be overwritten: {CANDIDATE_DIRECTORY}"
        )
    preexisting = [
        str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()
    ]
    if preexisting:
        raise RuntimeError(
            "Independent material exists before freeze:\n- "
            + "\n- ".join(preexisting)
        )

    report = read_json(DEVELOPMENT_REPORT_PATH)
    failures: list[str] = []
    if report.get("passed_development_gate") is not True:
        failures.append("The V2 development gate did not pass.")
    if int(report.get("records", 0)) != 140:
        failures.append("Unexpected development record count.")
    if float(report.get("accuracy", 0.0)) < 0.85:
        failures.append("Development accuracy is below 85%.")
    label_results = report.get("label_results", {})
    required_label_metrics = {
        ("graphic_sexual_content", "precision"): 0.85,
        ("graphic_sexual_content", "recall"): 0.85,
        ("sexual_harassment", "precision"): 0.85,
        ("sexual_harassment", "recall"): 0.85,
        ("no_override", "recall"): 0.95,
    }
    for (label, metric), minimum in required_label_metrics.items():
        value = float(label_results.get(label, {}).get(metric, 0.0))
        if value < minimum:
            failures.append(f"Development metric below gate: {label}.{metric}")
    for key in ("action_contract_failures", "category_mix_failures"):
        if int(report.get(key, -1)) != 0:
            failures.append(f"Development contract is nonzero: {key}")
    for key in (
        "external_or_restricted_data_used",
        "explicit_descriptions_stored",
        "child_exploitation_boundary_output_enabled",
        "automatic_enforcement_allowed",
        "connected_to_live_moderation",
    ):
        if report.get(key) is not False:
            failures.append(f"Unsafe or unexpected development contract: {key}")
    if failures:
        raise RuntimeError(
            "Graphic/Sexual Content V2 RC1 freeze validation failed:\n- "
            + "\n- ".join(failures)
        )

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="graphic-sexual-content-v2-rc1-freeze-",
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
                V1_EVALUATOR_PATH,
                temporary / "source_snapshot" / V1_EVALUATOR_PATH.name,
                f"source_snapshot/{V1_EVALUATOR_PATH.name}",
            ),
            copy_artifact(
                V2_EVALUATOR_PATH,
                temporary / "source_snapshot" / V2_EVALUATOR_PATH.name,
                f"source_snapshot/{V2_EVALUATOR_PATH.name}",
            ),
            copy_artifact(
                FREEZE_PATH,
                temporary / "source_snapshot" / FREEZE_PATH.name,
                f"source_snapshot/{FREEZE_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_DATASET_PATH,
                temporary / "development" / DEVELOPMENT_DATASET_PATH.name,
                f"development/{DEVELOPMENT_DATASET_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT_PATH,
                temporary / "development_evidence" / "report.json",
                "development_evidence/report.json",
            ),
            copy_artifact(
                DEVELOPMENT_MISMATCH_PATH,
                temporary / "development_evidence" / "mismatches.csv",
                "development_evidence/mismatches.csv",
            ),
        ]
        manifest = {
            "candidate": CANDIDATE,
            "component": "Graphic, Obscene & Sexual Content boundary",
            "candidate_type": "high-level policy-pattern boundary specialist",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                "records": report["records"],
                "accuracy": report["accuracy"],
                "label_results": report["label_results"],
                "minimum_group_accuracy": report["minimum_group_accuracy"],
                "action_contract_failures": report["action_contract_failures"],
                "category_mix_failures": report["category_mix_failures"],
            },
            "permitted_outputs": [
                "Graphic, Obscene & Sexual Content",
                "Sexual Harassment",
            ],
            "all_other_decisions": "No boundary override",
            "child_exploitation_boundary_output_enabled": False,
            "legitimate_medical_educational_artistic_veto_locked": True,
            "nonsexual_context_veto_locked": True,
            "sexual_harassment_precedence_locked": True,
            "external_data_used": False,
            "restricted_data_used": False,
            "explicit_descriptions_stored": False,
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc1": False,
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

    print("GRAPHIC/SEXUAL CONTENT V2 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Medical, educational, artistic, and nonsexual vetoes locked: True")
    print("Sexual Harassment ownership precedence locked: True")
    print("Child Exploitation output enabled: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("External or restricted data used: False")
    print("Explicit sexual descriptions stored: False")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC1 is frozen and ready for one independent challenge.")


if __name__ == "__main__":
    main()
