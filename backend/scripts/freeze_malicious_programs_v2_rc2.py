"""Freeze the passing Malicious Programs V2 RC2 recovery candidate."""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "malicious-programs-v2-rc2"
CANDIDATE_DIRECTORY = (
    BACKEND / "storage" / "candidates" / CANDIDATE
)
RC1_DIRECTORY = (
    BACKEND
    / "storage"
    / "candidates"
    / "malicious-programs-v1-rc1"
)
DATASET_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "malicious_programs_v2_rc2"
    / "development.csv"
)
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "malicious_programs"
    / "v2_rc2_development"
    / "report.json"
)
SOURCE_ARTIFACTS = {
    "source_snapshot/malicious_programs_v2_rc2_service.py": (
        BACKEND
        / "app"
        / "services"
        / "malicious_programs_v2_rc2_service.py"
    ),
    "policy_snapshot/malicious_programs_v2_rc2_policy.json": (
        BACKEND
        / "app"
        / "evidence"
        / "malicious_programs_v2_rc2_policy.json"
    ),
    "source_snapshot/evaluate_malicious_programs_v2_rc2_development.py": (
        BACKEND
        / "scripts"
        / "evaluate_malicious_programs_v2_rc2_development.py"
    ),
    "source_snapshot/freeze_malicious_programs_v2_rc2.py": (
        Path(__file__).resolve()
    ),
    "development/development.csv": DATASET_PATH,
    "development_evidence/report.json": REPORT_PATH,
}
INDEPENDENT_GATE = {
    "minimum_accuracy": 0.95,
    "minimum_malicious_precision": 0.97,
    "minimum_malicious_recall": 0.95,
    "minimum_safe_specificity": 0.99,
    "minimum_f1": 0.96,
    "minimum_group_accuracy": 0.92,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_non_execution_failures": 0,
    "maximum_payload_storage_failures": 0,
    "maximum_authority_contract_failures": 0,
    "maximum_processing_errors": 0,
    "require_zero_development_overlap": True,
    "require_frozen_source_hashes": True,
    "require_no_raw_holdout_storage": True,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024), b""
        ):
            digest.update(chunk)
    return digest.hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def main() -> None:
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            f"Frozen candidate already exists: {CANDIDATE_DIRECTORY}"
        )
    report = _read_json(REPORT_PATH)
    requirements = {
        "passed_development_gate": True,
        "records": 480,
        "unique_texts": 480,
        "prior_development_overlap": 0,
        "action_contract_failures": 0,
        "category_mix_failures": 0,
        "non_execution_failures": 0,
        "payload_storage_failures": 0,
        "authority_contract_failures": 0,
        "processing_errors": 0,
        "rc1_aggregate_result_used": True,
        "rc1_holdout_cases_read": False,
        "rc1_individual_predictions_read": False,
        "rc1_mismatches_read": False,
        "executable_payloads_used": False,
        "code_executed": False,
        "archives_unpacked": False,
        "payloads_stored": False,
        "credentials_used": False,
        "live_infrastructure_used": False,
        "external_provider_used": False,
        "connected_to_live_moderation": False,
    }
    for key, expected in requirements.items():
        if report.get(key) != expected:
            raise RuntimeError(
                "Development report failed freeze requirement: "
                f"{key}"
            )
    if _sha256(DATASET_PATH) != report.get("dataset_sha256"):
        raise RuntimeError("Development dataset hash mismatch.")
    with DATASET_PATH.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        rows = list(csv.DictReader(handle))
    if (
        len(rows) != 480
        or len({row["text"] for row in rows}) != 480
    ):
        raise RuntimeError(
            "Development dataset uniqueness verification failed."
        )
    for source in SOURCE_ARTIFACTS.values():
        if not source.is_file():
            raise FileNotFoundError(source)

    rc1_manifest_path = RC1_DIRECTORY / "manifest.json"
    rc1_verdict_path = (
        RC1_DIRECTORY / "independent_evaluation_verdict.json"
    )
    rc1_manifest = _read_json(rc1_manifest_path)
    rc1_verdict = _read_json(rc1_verdict_path)
    if (
        rc1_manifest.get("candidate") != "malicious-programs-v1-rc1"
        or rc1_verdict.get(
            "passed_synthetic_independent_readiness_gate"
        )
        is not False
        or rc1_verdict.get("candidate_may_be_modified_using_this_holdout")
        is not False
    ):
        raise RuntimeError("RC1 dependency boundary is invalid.")
    rc1_service_snapshot = (
        RC1_DIRECTORY
        / "source_snapshot"
        / "malicious_programs_v1_rc1_service.py"
    )
    rc1_live_service = (
        BACKEND
        / "app"
        / "services"
        / "malicious_programs_v1_rc1_service.py"
    )
    if _sha256(rc1_service_snapshot) != _sha256(rc1_live_service):
        raise RuntimeError("Frozen RC1 service dependency was modified.")

    temporary = CANDIDATE_DIRECTORY.with_name(
        CANDIDATE_DIRECTORY.name + ".tmp"
    )
    if temporary.exists():
        raise FileExistsError(temporary)
    temporary.mkdir(parents=True)
    try:
        artifacts: list[dict[str, Any]] = []
        for relative_path, source in SOURCE_ARTIFACTS.items():
            destination = temporary / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
            artifacts.append(
                {
                    "relative_path": relative_path,
                    "size_bytes": destination.stat().st_size,
                    "sha256": _sha256(destination),
                }
            )
        manifest = {
            "candidate": CANDIDATE,
            "component": "Malicious Programs",
            "candidate_type": (
                "local deterministic non-executing word-order "
                "recovery router"
            ),
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                key: report[key]
                for key in (
                    "records",
                    "unique_texts",
                    "prior_development_overlap",
                    "accuracy",
                    "malicious_precision",
                    "malicious_recall",
                    "safe_specificity",
                    "f1",
                    "minimum_group_accuracy",
                    "action_contract_failures",
                    "category_mix_failures",
                    "non_execution_failures",
                    "payload_storage_failures",
                    "authority_contract_failures",
                    "processing_errors",
                )
            },
            "artifacts": artifacts,
            "dependencies": {
                "malicious-programs-v1-rc1": {
                    "manifest_sha256": _sha256(rc1_manifest_path),
                    "verdict_sha256": _sha256(rc1_verdict_path),
                    "service_snapshot_sha256": _sha256(
                        rc1_service_snapshot
                    ),
                    "independent_gate_passed": False,
                    "used_as_frozen_base_only": True,
                }
            },
            "rc1_aggregate_result_used": True,
            "rc1_holdout_cases_or_predictions_used": False,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc2": False,
            "executable_payloads_used": False,
            "code_execution_allowed": False,
            "archive_unpacking_allowed": False,
            "payload_storage_allowed": False,
            "credentials_storage_allowed": False,
            "live_infrastructure_storage_allowed": False,
            "external_provider_used": False,
            "external_transmission_allowed": False,
            "permitted_active_outputs": [
                "Malicious Programs", "Uncertain"
            ],
            "required_malicious_action": (
                "Block and send for security review"
            ),
            "human_review_required": True,
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
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise

    print("MALICIOUS PROGRAMS V2 RC2 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print("Development gate passed: True")
    print("Frozen RC1 dependency hashes verified: True")
    print("RC1 aggregate result used: True")
    print("RC1 holdout cases or predictions used: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Executable payloads used: False")
    print("Code execution or archive unpacking allowed: False")
    print("External provider used: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC2 is frozen for one new aggregate-only challenge.")


if __name__ == "__main__":
    main()
