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
CANDIDATE = "captionless-visual-policy-v8-rc2"
CANDIDATE_PARENT = BACKEND / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / CANDIDATE
SERVICE_PATH = (
    BACKEND
    / "app"
    / "services"
    / "captionless_visual_policy_v8_rc2_service.py"
)
EVALUATOR_PATH = (
    BACKEND
    / "scripts"
    / "evaluate_captionless_visual_policy_v8_rc2_development.py"
)
FREEZE_PATH = Path(__file__).resolve()
DEVELOPMENT_REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_policy_v8_rc2_development"
    / "report.json"
)
V7_CANDIDATE_DIRECTORY = (
    BACKEND / "storage" / "candidates" / "captionless-visual-evidence-v7-rc1"
)
V7_MANIFEST_PATH = V7_CANDIDATE_DIRECTORY / "manifest.json"
FORBIDDEN_PRE_FREEZE_PATHS = (
    ROOT
    / "datasets"
    / "evaluation"
    / "captionless_visual_policy_v8_rc2_independent",
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_policy_v8_rc2_independent",
)

INDEPENDENT_POLICY_GATE = {
    "minimum_records": 240,
    "minimum_records_per_group": 20,
    "minimum_exact_accuracy": 0.95,
    "minimum_group_accuracy": 0.90,
    "maximum_action_contract_failures": 0,
    "maximum_art_auto_allow_contract_failures": 0,
    "maximum_screen_media_auto_allow_failures": 0,
    "maximum_llm_authority_failures": 0,
    "maximum_age_inference_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_processing_errors": 0,
    "require_zero_development_overlap": True,
    "require_frozen_source_and_dependency_hashes": True,
    "require_no_raw_media": True,
    "require_no_individual_predictions": True,
    "require_screen_media_never_creates_allow": True,
    "require_unsupported_decode_fails_closed": True,
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
    source: Path, destination: Path, relative_path: str
) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "relative_path": relative_path,
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def verify_v7_dependency() -> dict[str, Any]:
    manifest = read_json(V7_MANIFEST_PATH)
    failures: list[str] = []
    if manifest.get("candidate") != "captionless-visual-evidence-v7-rc1":
        failures.append("Unexpected V7 dependency candidate identifier.")
    if manifest.get("development_gate_passed") is not True:
        failures.append("The frozen V7 dependency did not pass development.")
    required_false = (
        "automatic_allow_enabled",
        "automatic_enforcement_allowed",
        "connected_to_live_moderation",
        "independently_validated",
        "production_eligible",
    )
    for key in required_false:
        if manifest.get(key) is not False:
            failures.append(f"Unsafe V7 dependency contract: {key}")

    artifacts = manifest.get("artifacts")
    if not isinstance(artifacts, list) or not artifacts:
        failures.append("The V7 dependency has no frozen artifacts.")
    else:
        for artifact in artifacts:
            if not isinstance(artifact, dict):
                failures.append("A V7 dependency artifact entry is invalid.")
                continue
            relative = str(artifact.get("relative_path", ""))
            artifact_path = V7_CANDIDATE_DIRECTORY / relative
            if not artifact_path.is_file():
                failures.append(f"V7 dependency artifact is missing: {relative}")
                continue
            if sha256_file(artifact_path) != artifact.get("sha256"):
                failures.append(f"V7 dependency artifact hash changed: {relative}")
    if failures:
        raise RuntimeError(
            "Captionless Visual Policy V8 RC2 dependency validation failed:\n- "
            + "\n- ".join(failures)
        )
    return manifest


def validate_development_report() -> dict[str, Any]:
    report = read_json(DEVELOPMENT_REPORT_PATH)
    failures: list[str] = []
    if report.get("candidate") != CANDIDATE:
        failures.append("Unexpected development candidate identifier.")
    if report.get("passed_development_gate") is not True:
        failures.append("The RC2 development gate did not pass.")
    if int(report.get("records", 0)) != 170:
        failures.append("The locked development report must contain 170 records.")
    if float(report.get("accuracy", 0.0)) != 1.0:
        failures.append("Development accuracy is not 100%.")
    if float(report.get("minimum_group_accuracy", 0.0)) != 1.0:
        failures.append("Minimum group accuracy is not 100%.")
    contract_failures = report.get("contract_failures", {})
    if not isinstance(contract_failures, dict):
        failures.append("Development contract-failure object is missing.")
    else:
        for key in (
            "action",
            "art_auto_allow",
            "screen_auto_allow",
            "llm_authority",
            "age_inference",
            "category_mix",
        ):
            if int(contract_failures.get(key, -1)) != 0:
                failures.append(f"Development contract is nonzero: {key}")
    gate_checks = report.get("gate_checks", {})
    if not isinstance(gate_checks, dict) or not gate_checks:
        failures.append("Development gate checks are missing.")
    elif not all(value is True for value in gate_checks.values()):
        failures.append("One or more development gate checks failed.")
    required_false = (
        "raw_media_used",
        "independent_holdout_opened",
        "copyrighted_user_examples_used",
        "frozen_rc1_modified",
        "automatic_allow_enabled",
        "automatic_enforcement_allowed",
        "connected_to_live_moderation",
    )
    for key in required_false:
        if report.get(key) is not False:
            failures.append(f"Unsafe or unexpected development contract: {key}")
    if report.get("synthetic_signed_evidence_only") is not True:
        failures.append("Development was not evidence-only synthetic policy testing.")
    if failures:
        raise RuntimeError(
            "Captionless Visual Policy V8 RC2 freeze validation failed:\n- "
            + "\n- ".join(failures)
        )
    return report


def main() -> None:
    for path in (
        SERVICE_PATH,
        EVALUATOR_PATH,
        FREEZE_PATH,
        DEVELOPMENT_REPORT_PATH,
        V7_MANIFEST_PATH,
    ):
        require_file(path)
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            "A frozen Captionless Visual Policy V8 RC2 candidate already exists "
            f"and will not be overwritten: {CANDIDATE_DIRECTORY}"
        )
    preexisting = [str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()]
    if preexisting:
        raise RuntimeError(
            "Independent material exists before freeze:\n- "
            + "\n- ".join(preexisting)
        )

    report = validate_development_report()
    v7_manifest = verify_v7_dependency()
    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="captionless-visual-policy-v8-rc2-freeze-",
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
                FREEZE_PATH,
                temporary / "source_snapshot" / FREEZE_PATH.name,
                f"source_snapshot/{FREEZE_PATH.name}",
            ),
            copy_artifact(
                DEVELOPMENT_REPORT_PATH,
                temporary / "development_evidence" / "report.json",
                "development_evidence/report.json",
            ),
            copy_artifact(
                V7_MANIFEST_PATH,
                temporary
                / "dependency_evidence"
                / "captionless-visual-evidence-v7-rc1-manifest.json",
                (
                    "dependency_evidence/"
                    "captionless-visual-evidence-v7-rc1-manifest.json"
                ),
            ),
        ]
        manifest = {
            "candidate": CANDIDATE,
            "component": "Captionless visual art and screen-media policy",
            "candidate_type": "deterministic evidence-routing policy",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {
                "records": report["records"],
                "accuracy": report["accuracy"],
                "minimum_group_accuracy": report["minimum_group_accuracy"],
                "contract_failures": report["contract_failures"],
            },
            "locked_policy": {
                "verified_art_culture_education_only_allow_route": True,
                "film_or_television_identity_can_create_allow": False,
                "llm_or_self_report_can_create_allow": False,
                "age_inferred_from_pixels": False,
                "unsupported_or_incomplete_decode_fails_closed": True,
                "child_or_age_ambiguity_requires_review": True,
                "established_category_ownership_preserved": True,
                "explicit_verified_adult_route": "Age-restrict/block distribution",
                "non_explicit_intimacy_route": (
                    "Allow with sensitive-content warning and refer to human review"
                ),
            },
            "v7_dependency": {
                "candidate": v7_manifest["candidate"],
                "manifest_sha256": sha256_file(V7_MANIFEST_PATH),
                "frozen_artifacts_verified": True,
                "independently_validated": False,
                "connected_to_live_moderation": False,
            },
            "v7_dependency_modified": False,
            "copyrighted_user_examples_used": False,
            "raw_media_used": False,
            "training_or_calibration_performed": False,
            "local_llm_used": False,
            "automatic_allow_policy_defined": True,
            "automatic_allow_enabled": False,
            "automatic_enforcement_allowed": False,
            "independently_validated": False,
            "production_eligible": False,
            "connected_to_live_moderation": False,
            "artifacts": artifacts,
            "independent_policy_gate_frozen_before_holdout": (
                INDEPENDENT_POLICY_GATE
            ),
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc2": False,
            "policy_challenge_pass_can_enable_live_integration": False,
            "policy_challenge_pass_can_enable_automatic_allow": False,
            "visual_dependency_must_pass_separate_independent_evaluation": True,
            "evaluation_reporting_contract": {
                "store_raw_media": False,
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

    print("CAPTIONLESS VISUAL POLICY V8 RC2 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Frozen V7 dependency and artifact hashes verified: True")
    print("V7 dependency modified: False")
    print("Verified art/culture/education is the only Allow route: True")
    print("Film or television identity can create Allow: False")
    print("LLM or self-report can create Allow: False")
    print("Unsupported or incomplete decoding fails closed: True")
    print("Independent policy holdout created before freeze: False")
    print("Independent policy holdout used before freeze: False")
    print("Independent policy gate locked before holdout: True")
    print("Visual evidence dependency independently validated: False")
    print("Automatic Allow enabled: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("RC2 is frozen for one evidence-only independent policy challenge.")
    print("A policy pass cannot replace independent visual-model validation.")


if __name__ == "__main__":
    main()
