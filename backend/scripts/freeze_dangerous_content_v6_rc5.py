from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
BACKEND_DIRECTORY = ROOT_DIRECTORY / "backend"
CANDIDATE = "dangerous-content-v6-rc5"
CANDIDATE_PARENT = BACKEND_DIRECTORY / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE

SERVICE_PATH = (
    BACKEND_DIRECTORY / "app" / "services" / "dangerous_content_v6_rc5_service.py"
)
DEVELOPMENT_EVALUATOR_PATH = (
    BACKEND_DIRECTORY
    / "scripts"
    / "evaluate_dangerous_content_v6_rc5_development.py"
)
FREEZE_SCRIPT_PATH = Path(__file__).resolve()
DATASET_DIRECTORY = (
    ROOT_DIRECTORY / "datasets" / "development" / "dangerous_content_v6_rc5"
)
DATASET_PATH = DATASET_DIRECTORY / "development.csv"
DATASET_MANIFEST_PATH = DATASET_DIRECTORY / "manifest.json"
DEVELOPMENT_REPORT_PATH = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v6_rc5_policy_generalization_development"
    / "report.json"
)

RC4_CANDIDATE_DIRECTORY = CANDIDATE_PARENT / "dangerous-content-v5-rc4"
RC4_MANIFEST_PATH = RC4_CANDIDATE_DIRECTORY / "manifest.json"
RC4_VERDICT_PATH = RC4_CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
RC4_LIVE_SERVICE_PATH = (
    BACKEND_DIRECTORY / "app" / "services" / "dangerous_content_v5_rc4_service.py"
)
RC3_LIVE_SERVICE_PATH = (
    BACKEND_DIRECTORY / "app" / "services" / "dangerous_content_v4_rc3_service.py"
)
RC3_LIVE_MODEL_PATH = (
    BACKEND_DIRECTORY
    / "storage"
    / "models"
    / "dangerous_content_v4_rc3"
    / "classifier_bundle.joblib"
)
RC3_LIVE_CONFIG_PATH = RC3_LIVE_MODEL_PATH.parent / "config.json"

FORBIDDEN_PRE_FREEZE_PATHS = (
    ROOT_DIRECTORY
    / "datasets"
    / "evaluation"
    / "dangerous_content_v6_rc5_independent",
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v6_rc5_independent",
)

INDEPENDENT_GATE = {
    "minimum_accuracy": 0.90,
    "minimum_dangerous_precision": 0.92,
    "minimum_dangerous_recall": 0.90,
    "minimum_safe_specificity": 0.97,
    "minimum_f1": 0.90,
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


def artifact_map(manifest: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item["relative_path"]): item
        for item in manifest.get("artifacts", [])
    }


def verify_rc4_dependency(rc4_manifest: dict[str, Any]) -> None:
    artifacts = artifact_map(rc4_manifest)
    checks = (
        (
            "source_snapshot/dangerous_content_v5_rc4_service.py",
            RC4_LIVE_SERVICE_PATH,
        ),
        (
            "dependency_snapshot/dangerous_content_v4_rc3_service.py",
            RC3_LIVE_SERVICE_PATH,
        ),
        (
            "dependency_snapshot/classifier_bundle.joblib",
            RC3_LIVE_MODEL_PATH,
        ),
        (
            "dependency_snapshot/rc3_config.json",
            RC3_LIVE_CONFIG_PATH,
        ),
    )
    for relative_path, live_path in checks:
        frozen_path = RC4_CANDIDATE_DIRECTORY / relative_path
        record = artifacts.get(relative_path)
        if record is None:
            raise RuntimeError(f"RC4 dependency artifact is missing: {relative_path}")
        require_file(frozen_path)
        require_file(live_path)
        frozen_hash = sha256_file(frozen_path)
        if frozen_hash != record.get("sha256"):
            raise RuntimeError(f"RC4 frozen artifact changed: {relative_path}")
        if sha256_file(live_path) != frozen_hash:
            raise RuntimeError(f"Live dependency differs from RC4 freeze: {relative_path}")


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
    required_paths = (
        SERVICE_PATH,
        DEVELOPMENT_EVALUATOR_PATH,
        FREEZE_SCRIPT_PATH,
        DATASET_PATH,
        DATASET_MANIFEST_PATH,
        DEVELOPMENT_REPORT_PATH,
        RC4_MANIFEST_PATH,
        RC4_VERDICT_PATH,
    )
    for path in required_paths:
        require_file(path)

    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "A frozen RC5 candidate already exists and will not be overwritten: "
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

    report = read_json(DEVELOPMENT_REPORT_PATH)
    dataset_manifest = read_json(DATASET_MANIFEST_PATH)
    rc4_manifest = read_json(RC4_MANIFEST_PATH)
    rc4_verdict = read_json(RC4_VERDICT_PATH)
    verify_rc4_dependency(rc4_manifest)

    failures: list[str] = []
    if report.get("candidate") != "dangerous-content-v6-rc5-development":
        failures.append("Unexpected RC5 development candidate identity.")
    if report.get("passed_development_gate") is not True:
        failures.append("The RC5 development gate did not pass.")
    metric_minimums = {
        "accuracy": 0.90,
        "dangerous_precision": 0.92,
        "dangerous_recall": 0.90,
        "safe_specificity": 0.97,
        "f1": 0.90,
        "minimum_group_accuracy": 0.85,
    }
    for key, minimum in metric_minimums.items():
        if float(report.get(key, 0.0)) < minimum:
            failures.append(f"Development metric below {minimum:.0%}: {key}.")
    for key in (
        "action_contract_failures",
        "category_mix_failures",
        "processing_errors",
        "prior_development_text_overlap",
    ):
        if int(report.get(key, -1)) != 0:
            failures.append(f"Development contract is nonzero: {key}.")
    for key in (
        "rc4_holdout_cases_read",
        "rc4_holdout_predictions_or_mismatches_read",
        "external_or_restricted_data_used",
        "actionable_harm_instructions_stored",
        "connected_to_live_moderation",
        "automatic_enforcement_allowed",
    ):
        if report.get(key) is not False:
            failures.append(f"Unsafe or unexpected development contract: {key}.")
    if report.get("rc4_independent_aggregate_used_as_development_signal") is not True:
        failures.append("RC4 aggregate signal usage was not documented.")
    if dataset_manifest.get("candidate") != report.get("candidate"):
        failures.append("The RC5 dataset and report identities differ.")
    if rc4_manifest.get("candidate") != "dangerous-content-v5-rc4":
        failures.append("Unexpected RC4 dependency identity.")
    if rc4_verdict.get("passed_synthetic_independent_readiness_gate") is not False:
        failures.append("RC4 dependency verdict is not the recorded failed state.")
    if failures:
        raise RuntimeError(
            "Dangerous Content V6 RC5 freeze validation failed:\n- "
            + "\n- ".join(failures)
        )

    dependency_sources = (
        (
            RC4_CANDIDATE_DIRECTORY
            / "source_snapshot"
            / "dangerous_content_v5_rc4_service.py",
            "dependency_snapshot/dangerous_content_v5_rc4_service.py",
        ),
        (
            RC4_CANDIDATE_DIRECTORY
            / "dependency_snapshot"
            / "dangerous_content_v4_rc3_service.py",
            "dependency_snapshot/dangerous_content_v4_rc3_service.py",
        ),
        (
            RC4_CANDIDATE_DIRECTORY
            / "dependency_snapshot"
            / "classifier_bundle.joblib",
            "dependency_snapshot/classifier_bundle.joblib",
        ),
        (
            RC4_CANDIDATE_DIRECTORY
            / "dependency_snapshot"
            / "rc3_config.json",
            "dependency_snapshot/rc3_config.json",
        ),
    )
    for source, _ in dependency_sources:
        require_file(source)

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="dangerous-content-v6-rc5-freeze-",
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
                DEVELOPMENT_EVALUATOR_PATH,
                temporary / "source_snapshot" / DEVELOPMENT_EVALUATOR_PATH.name,
                f"source_snapshot/{DEVELOPMENT_EVALUATOR_PATH.name}",
            ),
            copy_artifact(
                FREEZE_SCRIPT_PATH,
                temporary / "source_snapshot" / FREEZE_SCRIPT_PATH.name,
                f"source_snapshot/{FREEZE_SCRIPT_PATH.name}",
            ),
            copy_artifact(
                DATASET_PATH,
                temporary / "development" / DATASET_PATH.name,
                f"development/{DATASET_PATH.name}",
            ),
            copy_artifact(
                DATASET_MANIFEST_PATH,
                temporary / "development" / DATASET_MANIFEST_PATH.name,
                f"development/{DATASET_MANIFEST_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT_PATH,
                temporary / "development_evidence" / DEVELOPMENT_REPORT_PATH.name,
                f"development_evidence/{DEVELOPMENT_REPORT_PATH.name}",
            ),
            copy_artifact(
                RC4_MANIFEST_PATH,
                temporary / "dependency_snapshot" / "rc4_manifest.json",
                "dependency_snapshot/rc4_manifest.json",
            ),
            copy_artifact(
                RC4_VERDICT_PATH,
                temporary / "dependency_snapshot" / "rc4_verdict.json",
                "dependency_snapshot/rc4_verdict.json",
            ),
        ]
        for source, relative_path in dependency_sources:
            artifacts.append(
                copy_artifact(source, temporary / relative_path, relative_path)
            )

        manifest = {
            "candidate": CANDIDATE,
            "component": "Dangerous Content",
            "candidate_type": (
                "frozen RC4 policy plus guarded broader-grammar recovery"
            ),
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                key: report[key]
                for key in (
                    "records",
                    "accuracy",
                    "dangerous_precision",
                    "dangerous_recall",
                    "safe_specificity",
                    "f1",
                    "minimum_group_accuracy",
                    "frozen_rc4_accepts",
                    "rc5_policy_recoveries",
                    "action_contract_failures",
                    "category_mix_failures",
                    "processing_errors",
                )
            },
            "base_dependency": {
                "candidate": "dangerous-content-v5-rc4",
                "source_and_dependency_hashes_verified": True,
                "independent_gate_passed": False,
                "used_only_inside_rc5_guards": True,
            },
            "rc4_aggregate_used_as_development_signal": True,
            "rc4_holdout_cases_or_predictions_used": False,
            "permitted_active_output": "Dangerous Content only",
            "all_other_decisions": "No Dangerous Content override",
            "safe_reporting_and_professional_veto_locked": True,
            "benign_activity_without_hazard_veto_locked": True,
            "established_category_owner_guard_locked": True,
            "recovery_requires_advocacy_participation_audience_and_hazard": True,
            "external_data_used": False,
            "restricted_data_used": False,
            "actionable_harm_instructions_stored": False,
            "artifacts": artifacts,
            "independent_gate_frozen_before_holdout": INDEPENDENT_GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc5": False,
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

    print("DANGEROUS CONTENT V6 RC5 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Frozen RC4 and transitive dependency hashes verified: True")
    print("RC4 independent aggregate used as development signal: True")
    print("RC4 holdout cases or predictions used: False")
    print("Safe/reporting/professional veto locked: True")
    print("Benign activity without hazard veto locked: True")
    print("Established-category owner guard locked: True")
    print("Broader recovery evidence requirements locked: True")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC5 is frozen and ready for one new independent challenge.")


if __name__ == "__main__":
    main()

