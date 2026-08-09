from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SCRIPT_DIRECTORY.parent
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent
DEVELOPMENT_DATASET_DIRECTORY = (
    PROJECT_DIRECTORY
    / "datasets"
    / "development"
    / "stable_knowledge_v3"
)
DEVELOPMENT_MANIFEST_PATH = DEVELOPMENT_DATASET_DIRECTORY / "manifest.json"
DEVELOPMENT_REPORT_ROOT = (
    PROJECT_DIRECTORY
    / "reports"
    / "evaluation"
    / "stable_knowledge_v3_development"
)
RELEASE_CANDIDATE_ROOT = (
    PROJECT_DIRECTORY
    / "reports"
    / "evaluation"
    / "stable_knowledge_v3"
    / "release_candidates"
)

ENGINE_FILES = (
    Path("app/services/structured_claim_service.py"),
    Path("app/services/structured_evidence_service.py"),
    Path("app/services/stable_knowledge_service.py"),
    Path("app/services/stable_knowledge_v3_service.py"),
    Path("app/services/fact_check_decision_service.py"),
    Path("app/services/fact_check_retrieval_service.py"),
)

EXPECTED_DEVELOPMENT_VERSION = "2026.08-v3-development"
EXPECTED_ENGINE_VERSION = "india-world-english-v3.3-structured-knowledge"


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Freeze the exact Stable Knowledge V3 engine files before an "
            "independent holdout is created or executed."
        )
    )
    parser.add_argument(
        "--candidate-id",
        default="rc1",
        help="Immutable candidate identifier, for example rc1 or rc2.",
    )
    parser.add_argument(
        "--development-run",
        default="full-development-v2",
        help="Development run that must have passed its development gate.",
    )
    return parser.parse_args()


def safe_identifier(value: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "-", str(value or "")).strip("-")
    if not cleaned:
        raise ValueError("The candidate identifier is empty.")
    return cleaned


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file was not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return payload


def validate_development_evidence(
    development_run: str,
) -> tuple[dict[str, Any], dict[str, Any], Path]:
    dataset_manifest = read_json(DEVELOPMENT_MANIFEST_PATH)
    development_report_path = (
        DEVELOPMENT_REPORT_ROOT / development_run / "report.json"
    )
    development_report = read_json(development_report_path)

    if dataset_manifest.get("version") != EXPECTED_DEVELOPMENT_VERSION:
        raise ValueError("Unexpected V3 development dataset version.")
    if dataset_manifest.get("eligible_for_holdout") is not False:
        raise ValueError("Development records are not explicitly excluded from holdout use.")
    if dataset_manifest.get("uses_v2_holdout_records") is not False:
        raise ValueError("The development manifest violates V2 holdout separation.")
    if dataset_manifest.get("uses_v2_mismatch_report") is not False:
        raise ValueError("The development manifest violates V2 mismatch separation.")
    if development_report.get("evaluation_type") != (
        "development_only_not_independent_accuracy"
    ):
        raise ValueError("The selected report is not a development-only evaluation.")
    if development_report.get("dataset_sha256") != dataset_manifest.get(
        "dataset_sha256"
    ):
        raise ValueError("Development report and dataset hashes do not match.")
    if development_report.get("passed_development_gate") is not True:
        raise ValueError("The selected development run did not pass its gate.")

    required_zero_metrics = (
        "evidence_conflicts",
        "policy_contract_failures",
        "processing_errors",
        "retrieval_infrastructure_failures",
        "retrieval_degraded_records",
    )
    for metric in required_zero_metrics:
        if int(development_report.get(metric, -1)) != 0:
            raise ValueError(
                f"Development report must have zero {metric}: "
                f"{development_report.get(metric)!r}"
            )

    minimum_metrics = {
        "exact_accuracy_percent": 85.0,
        "routing_accuracy_percent": 95.0,
        "selective_accuracy_percent": 90.0,
        "expected_conclusive_coverage_percent": 85.0,
    }
    for metric, minimum in minimum_metrics.items():
        value = float(development_report.get(metric, 0.0) or 0.0)
        if value < minimum:
            raise ValueError(
                f"Development metric {metric} is below {minimum}: {value}"
            )

    return dataset_manifest, development_report, development_report_path


def engine_file_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []

    for relative_path in ENGINE_FILES:
        absolute_path = BACKEND_DIRECTORY / relative_path
        if not absolute_path.exists():
            raise FileNotFoundError(
                f"Required engine file was not found: {absolute_path}"
            )
        records.append(
            {
                "path": relative_path.as_posix(),
                "sha256": sha256_file(absolute_path),
                "size_bytes": absolute_path.stat().st_size,
            }
        )

    return records


def composite_engine_hash(records: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["path"]):
        digest.update(str(record["path"]).encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(record["sha256"]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def verify_engine_version() -> None:
    decision_service_path = (
        BACKEND_DIRECTORY
        / "app"
        / "services"
        / "fact_check_decision_service.py"
    )
    source = decision_service_path.read_text(encoding="utf-8")
    if EXPECTED_ENGINE_VERSION not in source:
        raise ValueError(
            "The fact-check decision service does not contain the expected "
            f"engine version: {EXPECTED_ENGINE_VERSION}"
        )


def write_candidate_manifest(
    candidate_id: str,
    development_run: str,
    dataset_manifest: dict[str, Any],
    development_report: dict[str, Any],
    development_report_path: Path,
    engine_files: list[dict[str, Any]],
) -> Path:
    candidate_directory = RELEASE_CANDIDATE_ROOT / candidate_id
    manifest_path = candidate_directory / "manifest.json"
    engine_hash = composite_engine_hash(engine_files)
    development_report_hash = sha256_file(development_report_path)

    manifest: dict[str, Any] = {
        "candidate_id": candidate_id,
        "candidate_name": f"stable-knowledge-v3-{candidate_id}",
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "engine_version": EXPECTED_ENGINE_VERSION,
        "engine_composite_sha256": engine_hash,
        "engine_files": engine_files,
        "development_dataset": {
            "version": dataset_manifest.get("version"),
            "sha256": dataset_manifest.get("dataset_sha256"),
            "record_count": dataset_manifest.get("record_count"),
            "eligible_for_holdout": False,
        },
        "development_evaluation": {
            "run_name": development_run,
            "report_path": str(development_report_path),
            "report_sha256": development_report_hash,
            "records": development_report.get("records"),
            "exact_accuracy_percent": development_report.get(
                "exact_accuracy_percent"
            ),
            "macro_f1_percent": development_report.get("macro_f1_percent"),
            "routing_accuracy_percent": development_report.get(
                "routing_accuracy_percent"
            ),
            "selective_accuracy_percent": development_report.get(
                "selective_accuracy_percent"
            ),
            "expected_conclusive_coverage_percent": development_report.get(
                "expected_conclusive_coverage_percent"
            ),
            "policy_contract_failures": development_report.get(
                "policy_contract_failures"
            ),
            "processing_errors": development_report.get("processing_errors"),
            "retrieval_infrastructure_failures": development_report.get(
                "retrieval_infrastructure_failures"
            ),
            "passed_development_gate": development_report.get(
                "passed_development_gate"
            ),
            "evaluation_type": (
                "development_only_not_independent_accuracy"
            ),
        },
        "policy_contract": {
            "language": "en",
            "retrieval_mode": "live_only_except_approved_pib_records",
            "stable_knowledge_cache_allowed": False,
            "stable_knowledge_persistent_cache_used": False,
            "automatic_enforcement_allowed": False,
            "misinformation_action": "Refer to human review",
            "confidence_cap": 0.80,
        },
        "holdout_separation": {
            "v2_holdout_mismatches_inspected": False,
            "v2_holdout_used_for_v3_development": False,
            "new_independent_holdout_created": False,
            "new_independent_holdout_evaluated": False,
        },
        "readiness": {
            "development_gate_passed": True,
            "independent_holdout_gate_passed": False,
            "production_ready": False,
            "reason": (
                "The exact engine candidate is frozen, but a new independent "
                "holdout has not yet been evaluated."
            ),
        },
    }

    if manifest_path.exists():
        existing = read_json(manifest_path)
        existing_hash = existing.get("engine_composite_sha256")
        if existing_hash != engine_hash:
            raise FileExistsError(
                f"Candidate {candidate_id!r} already exists with a different "
                "engine hash. Use a new candidate ID."
            )
        print(
            "The candidate already exists with the same engine hash; "
            "the existing immutable manifest was preserved."
        )
        return manifest_path

    candidate_directory.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest_path


def main() -> None:
    arguments = parse_arguments()
    candidate_id = safe_identifier(arguments.candidate_id)
    development_run = safe_identifier(arguments.development_run)
    dataset_manifest, development_report, report_path = (
        validate_development_evidence(development_run)
    )
    verify_engine_version()
    engine_files = engine_file_records()
    manifest_path = write_candidate_manifest(
        candidate_id,
        development_run,
        dataset_manifest,
        development_report,
        report_path,
        engine_files,
    )
    manifest = read_json(manifest_path)

    print("=" * 60)
    print("STABLE KNOWLEDGE V3 RELEASE CANDIDATE FROZEN")
    print("=" * 60)
    print(f"Candidate: {manifest['candidate_name']}")
    print(f"Engine version: {manifest['engine_version']}")
    print(f"Engine SHA-256: {manifest['engine_composite_sha256']}")
    print(f"Engine files: {len(manifest['engine_files'])}")
    print(
        "Development records: "
        f"{manifest['development_evaluation']['records']}"
    )
    print(
        "Development gate passed: "
        f"{manifest['readiness']['development_gate_passed']}"
    )
    print(
        "Independent holdout passed: "
        f"{manifest['readiness']['independent_holdout_gate_passed']}"
    )
    print(f"Production ready: {manifest['readiness']['production_ready']}")
    print(f"Manifest: {manifest_path}")
    print("\nDo not modify an engine file under this candidate ID.")
    print("Any later engine change requires a new candidate ID.")


if __name__ == "__main__":
    main()
