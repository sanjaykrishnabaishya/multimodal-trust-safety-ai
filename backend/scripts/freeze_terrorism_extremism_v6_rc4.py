from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
CANDIDATE_NAME = "terrorism-extremism-v6-rc4"
CANDIDATE_DIRECTORY = BACKEND_ROOT / "storage" / "candidates" / CANDIDATE_NAME
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
RC3_DIRECTORY = BACKEND_ROOT / "storage" / "candidates" / "terrorism-extremism-v5-rc3"
RC3_MANIFEST_PATH = RC3_DIRECTORY / "manifest.json"

INPUTS = {
    "source/terrorism_extremism_service.py": BACKEND_ROOT / "app" / "services" / "terrorism_extremism_service.py",
    "source/wikidata_terrorism_candidate_service.py": BACKEND_ROOT / "app" / "services" / "wikidata_terrorism_candidate_service.py",
    "source/terrorism_extremism_v4_rc2_service.py": BACKEND_ROOT / "app" / "services" / "terrorism_extremism_v4_rc2_service.py",
    "source/wikidata_terrorism_candidate_v4_rc2_service.py": BACKEND_ROOT / "app" / "services" / "wikidata_terrorism_candidate_v4_rc2_service.py",
    "source/terrorism_extremism_v5_rc3_service.py": BACKEND_ROOT / "app" / "services" / "terrorism_extremism_v5_rc3_service.py",
    "source/wikidata_terrorism_candidate_v5_rc3_service.py": BACKEND_ROOT / "app" / "services" / "wikidata_terrorism_candidate_v5_rc3_service.py",
    "source/terrorism_extremism_v6_rc4_service.py": BACKEND_ROOT / "app" / "services" / "terrorism_extremism_v6_rc4_service.py",
    "source/wikidata_terrorism_candidate_v6_rc4_service.py": BACKEND_ROOT / "app" / "services" / "wikidata_terrorism_candidate_v6_rc4_service.py",
    "data/candidates.csv": PROJECT_ROOT / "datasets" / "public" / "wikidata_terrorism_candidates_v1" / "candidates.csv",
    "data/wikidata_manifest.json": PROJECT_ROOT / "datasets" / "public" / "wikidata_terrorism_candidates_v1" / "manifest.json",
    "development/development.csv": PROJECT_ROOT / "datasets" / "development" / "terrorism_extremism_v6_rc4" / "development.csv",
    "evidence/development_report.json": PROJECT_ROOT / "reports" / "evaluation" / "terrorism_extremism" / "v6_rc4_development" / "report.json",
}

FORBIDDEN_PRE_FREEZE_PATHS = (
    PROJECT_ROOT / "datasets" / "evaluation" / "terrorism_extremism_v6_rc4",
    PROJECT_ROOT / "reports" / "evaluation" / "terrorism_extremism" / "v6_rc4_independent",
)


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise RuntimeError(f"Required file is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_rc3_dependencies() -> None:
    manifest = read_json(RC3_MANIFEST_PATH)
    locked = manifest.get("locked_file_sha256", {})
    if not isinstance(locked, dict) or not locked:
        raise RuntimeError("RC3 locked hashes are unavailable.")
    inherited = {
        key: value
        for key, value in INPUTS.items()
        if key.startswith("source/")
        and "v6_rc4" not in key
    }
    inherited.update(
        {
            "data/candidates.csv": INPUTS["data/candidates.csv"],
            "data/wikidata_manifest.json": INPUTS["data/wikidata_manifest.json"],
        }
    )
    for relative, active_path in inherited.items():
        frozen_path = RC3_DIRECTORY / relative
        expected = locked.get(relative)
        if (
            not frozen_path.exists()
            or not active_path.exists()
            or sha256_file(frozen_path) != expected
            or sha256_file(active_path) != expected
        ):
            raise RuntimeError(f"RC3 dependency changed: {relative}")


def validate() -> dict[str, object]:
    missing = [str(path) for path in INPUTS.values() if not path.exists()]
    if missing:
        raise RuntimeError("Missing RC4 freeze inputs:\n- " + "\n- ".join(missing))
    verify_rc3_dependencies()

    report = read_json(INPUTS["evidence/development_report.json"])
    community = read_json(INPUTS["data/wikidata_manifest.json"])
    failures: list[str] = []
    if report.get("candidate") != CANDIDATE_NAME:
        failures.append("Development report has the wrong candidate identity.")
    if report.get("passed_development_gate") is not True:
        failures.append("RC4 development gate did not pass.")
    if float(report.get("accuracy", 0.0)) < 0.90:
        failures.append("RC4 development accuracy is below 90%.")
    if float(report.get("minimum_group_accuracy", 0.0)) < 0.85:
        failures.append("An RC4 development group is below 85%.")
    for key in ("action_contract_failures", "policy_contract_failures", "processing_errors"):
        if report.get(key) != 0:
            failures.append(f"RC4 development failure: {key}.")
    if report.get("rc3_aggregate_user_result_used_as_development_signal") is not True:
        failures.append("RC4 provenance omits the RC3 aggregate signal.")
    if report.get("rc3_holdout_cases_read") is not False:
        failures.append("RC3 holdout cases were read during RC4 development.")
    if report.get("rc3_predictions_or_mismatches_read") is not False:
        failures.append("RC3 predictions or mismatches were read during RC4 development.")
    for key in (
        "official_registry_used",
        "permission_restricted_source_used",
        "automatic_enforcement_allowed",
        "connected_to_live_moderation",
    ):
        if report.get(key) is not False:
            failures.append(f"Unsafe RC4 development contract: {key}.")

    policy = community.get("policy_contract", {})
    validation = community.get("validation", {})
    if not isinstance(policy, dict):
        policy = {}
    if not isinstance(validation, dict):
        validation = {}
    if community.get("source_license") != "CC0-1.0":
        failures.append("Wikidata data is not marked CC0-1.0.")
    if validation.get("passed") is not True:
        failures.append("Wikidata import validation did not pass.")
    if policy.get("wikipedia_prose_downloaded") is not False:
        failures.append("Wikipedia prose was used.")
    if policy.get("automatic_enforcement_allowed") is not False:
        failures.append("Community data permits automatic enforcement.")

    preexisting = [str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()]
    if preexisting:
        failures.append(
            "An RC4 independent dataset or report exists before freeze: "
            + ", ".join(preexisting)
        )
    if failures:
        raise RuntimeError("RC4 freeze validation failed:\n- " + "\n- ".join(failures))
    return {
        "development_records": report.get("records"),
        "development_accuracy": report.get("accuracy"),
        "minimum_group_accuracy": report.get("minimum_group_accuracy"),
        "wikidata_candidate_records": validation.get("records"),
        "wikidata_license": community.get("source_license"),
    }


def main() -> None:
    evidence = validate()
    expected_hashes = {relative: sha256_file(path) for relative, path in INPUTS.items()}
    if MANIFEST_PATH.exists():
        existing = read_json(MANIFEST_PATH)
        if existing.get("locked_file_sha256") != expected_hashes:
            raise RuntimeError("A different RC4 freeze exists; create a new version instead.")
        print("TERRORISM & EXTREMISM V6 RC4 FREEZE")
        print("=" * 60)
        print("RC4 is already frozen with matching hashes.")
        print(f"Manifest: {MANIFEST_PATH}")
        return

    for relative, source in INPUTS.items():
        destination = CANDIDATE_DIRECTORY / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    copied_hashes = {
        str(path.relative_to(CANDIDATE_DIRECTORY)).replace("\\", "/"): sha256_file(path)
        for path in CANDIDATE_DIRECTORY.rglob("*")
        if path.is_file()
    }
    if copied_hashes != expected_hashes:
        raise RuntimeError("Frozen RC4 copies do not match source hashes.")

    manifest = {
        "candidate": CANDIDATE_NAME,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "locked_file_sha256": copied_hashes,
        "evidence_summary": evidence,
        "development_gate_passed": True,
        "rc3_active_and_frozen_dependencies_verified": True,
        "rc3_aggregate_used_as_rc4_development_signal": True,
        "rc3_holdout_cases_or_predictions_used": False,
        "independent_holdout_created_before_freeze": False,
        "independent_holdout_used_before_freeze": False,
        "independent_gate_locked_before_holdout": True,
        "independently_validated": False,
        "eligible_for_live_integration": False,
        "confirmed_legal_designations": 0,
        "permitted_community_candidate_output": "Uncertain only",
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "wikipedia_prose_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("TERRORISM & EXTREMISM V6 RC4 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {MANIFEST_PATH}")
    print("Development gate passed: True")
    print("RC3 active and frozen dependencies verified: True")
    print("RC3 aggregate used as RC4 development signal: True")
    print("RC3 holdout cases or predictions used: False")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Independent gate locked before holdout: True")
    print("Confirmed legal designations: 0")
    print("Permitted community-candidate output: Uncertain only")
    print("Official registry used: False")
    print("Permission-restricted source used: False")
    print("Wikipedia prose used: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("RC4 is frozen and ready for one new independent challenge.")


if __name__ == "__main__":
    main()
