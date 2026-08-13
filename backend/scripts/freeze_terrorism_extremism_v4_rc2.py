from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
CANDIDATE_NAME = "terrorism-extremism-v4-rc2"
CANDIDATE_DIRECTORY = BACKEND_ROOT / "storage" / "candidates" / CANDIDATE_NAME
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"

INPUTS = {
    "source/terrorism_extremism_service.py": (
        BACKEND_ROOT / "app" / "services" / "terrorism_extremism_service.py"
    ),
    "source/wikidata_terrorism_candidate_service.py": (
        BACKEND_ROOT
        / "app"
        / "services"
        / "wikidata_terrorism_candidate_service.py"
    ),
    "source/terrorism_extremism_v4_rc2_service.py": (
        BACKEND_ROOT
        / "app"
        / "services"
        / "terrorism_extremism_v4_rc2_service.py"
    ),
    "source/wikidata_terrorism_candidate_v4_rc2_service.py": (
        BACKEND_ROOT
        / "app"
        / "services"
        / "wikidata_terrorism_candidate_v4_rc2_service.py"
    ),
    "data/candidates.csv": (
        PROJECT_ROOT
        / "datasets"
        / "public"
        / "wikidata_terrorism_candidates_v1"
        / "candidates.csv"
    ),
    "data/wikidata_manifest.json": (
        PROJECT_ROOT
        / "datasets"
        / "public"
        / "wikidata_terrorism_candidates_v1"
        / "manifest.json"
    ),
    "development/development.csv": (
        PROJECT_ROOT
        / "datasets"
        / "development"
        / "terrorism_extremism_v4_rc2"
        / "development.csv"
    ),
    "evidence/development_report.json": (
        PROJECT_ROOT
        / "reports"
        / "evaluation"
        / "terrorism_extremism"
        / "v4_rc2_development"
        / "report.json"
    ),
}

FORBIDDEN_PRE_FREEZE_PATHS = (
    PROJECT_ROOT
    / "datasets"
    / "evaluation"
    / "terrorism_extremism_v4_rc2",
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "v4_rc2_independent",
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


def validate() -> dict[str, object]:
    missing = [str(path) for path in INPUTS.values() if not path.exists()]
    if missing:
        raise RuntimeError("Missing RC2 freeze inputs:\n- " + "\n- ".join(missing))

    report = read_json(INPUTS["evidence/development_report.json"])
    community = read_json(INPUTS["data/wikidata_manifest.json"])
    failures: list[str] = []
    if report.get("candidate") != CANDIDATE_NAME:
        failures.append("Development report has the wrong candidate identity.")
    if report.get("passed_development_gate") is not True:
        failures.append("RC2 development gate did not pass.")
    if float(report.get("accuracy", 0.0)) < 0.90:
        failures.append("RC2 development accuracy is below 90%.")
    if float(report.get("minimum_group_accuracy", 0.0)) < 0.85:
        failures.append("An RC2 development group is below 85%.")
    if report.get("action_contract_failures") != 0:
        failures.append("RC2 has action-contract failures.")
    if report.get("policy_contract_failures") != 0:
        failures.append("RC2 has policy-contract failures.")
    if report.get("processing_errors") != 0:
        failures.append("RC2 has development processing errors.")
    if report.get("rc1_independent_holdout_read") is not False:
        failures.append("RC1 holdout was used during RC2 development.")
    if report.get("rc1_individual_predictions_read") is not False:
        failures.append("RC1 predictions were used during RC2 development.")
    for key in (
        "official_registry_used",
        "permission_restricted_source_used",
        "automatic_enforcement_allowed",
        "connected_to_live_moderation",
    ):
        if report.get(key) is not False:
            failures.append(f"Unsafe RC2 report contract: {key}.")

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
    if policy.get("extremism_inferred_from_ideology") is not False:
        failures.append("Extremism was inferred from ideology.")
    if policy.get("automatic_enforcement_allowed") is not False:
        failures.append("Community data permits automatic enforcement.")

    preexisting = [str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()]
    if preexisting:
        failures.append(
            "An RC2 independent dataset or report exists before freeze: "
            + ", ".join(preexisting)
        )
    if failures:
        raise RuntimeError("RC2 freeze validation failed:\n- " + "\n- ".join(failures))
    return {
        "development_records": report.get("records"),
        "development_accuracy": report.get("accuracy"),
        "minimum_group_accuracy": report.get("minimum_group_accuracy"),
        "wikidata_candidate_records": validation.get("records"),
        "wikidata_license": community.get("source_license"),
    }


def source_hashes() -> dict[str, str]:
    return {relative: sha256_file(path) for relative, path in INPUTS.items()}


def main() -> None:
    evidence = validate()
    expected_hashes = source_hashes()
    if MANIFEST_PATH.exists():
        existing = read_json(MANIFEST_PATH)
        if existing.get("locked_file_sha256") != expected_hashes:
            raise RuntimeError(
                "A different RC2 freeze already exists. Create a new version "
                "instead of overwriting it."
            )
        print("TERRORISM & EXTREMISM V4 RC2 FREEZE")
        print("=" * 60)
        print("RC2 is already frozen with matching hashes.")
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
        raise RuntimeError("Frozen RC2 copies do not match their source hashes.")

    manifest = {
        "candidate": CANDIDATE_NAME,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "locked_file_sha256": copied_hashes,
        "evidence_summary": evidence,
        "development_gate_passed": True,
        "rc1_holdout_used_for_rc2_development": False,
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

    print("TERRORISM & EXTREMISM V4 RC2 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {MANIFEST_PATH}")
    print("Development gate passed: True")
    print("RC1 holdout used for RC2 development: False")
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
    print("RC2 is frozen and ready for one new independent challenge.")


if __name__ == "__main__":
    main()
