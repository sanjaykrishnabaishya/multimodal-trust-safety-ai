from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
CANDIDATE_NAME = "terrorism-extremism-v3-rc1"
CANDIDATE_DIRECTORY = (
    BACKEND_ROOT / "storage" / "candidates" / CANDIDATE_NAME
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"

BEHAVIOR_SERVICE = (
    BACKEND_ROOT / "app" / "services" / "terrorism_extremism_service.py"
)
COMMUNITY_SERVICE = (
    BACKEND_ROOT
    / "app"
    / "services"
    / "wikidata_terrorism_candidate_service.py"
)
COMMUNITY_CSV = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "wikidata_terrorism_candidates_v1"
    / "candidates.csv"
)
COMMUNITY_MANIFEST = COMMUNITY_CSV.parent / "manifest.json"
BEHAVIOR_REPORT = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "development_v2_behavior_only"
    / "report.json"
)
MATCHING_REPORT = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "wikidata_candidate_contract_v1"
    / "report.json"
)

FORBIDDEN_PRE_FREEZE_PATHS = (
    PROJECT_ROOT
    / "datasets"
    / "evaluation"
    / "terrorism_extremism_v3_rc1",
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "v3_rc1_independent",
)


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        raise RuntimeError(f"Required file is missing: {path}")
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_hashes() -> dict[str, str]:
    files = {
        "source/terrorism_extremism_service.py": BEHAVIOR_SERVICE,
        "source/wikidata_terrorism_candidate_service.py": COMMUNITY_SERVICE,
        "data/candidates.csv": COMMUNITY_CSV,
        "data/wikidata_manifest.json": COMMUNITY_MANIFEST,
        "evidence/behavior_development_report.json": BEHAVIOR_REPORT,
        "evidence/community_matching_contract.json": MATCHING_REPORT,
    }
    for path in files.values():
        if not path.exists():
            raise RuntimeError(f"Required freeze input is missing: {path}")
    return {name: sha256_file(path) for name, path in files.items()}


def validate_inputs() -> dict[str, object]:
    behavior = read_json(BEHAVIOR_REPORT)
    matching = read_json(MATCHING_REPORT)
    community = read_json(COMMUNITY_MANIFEST)

    failures: list[str] = []
    if behavior.get("passed_development_gate") is not True:
        failures.append("Behavior-only development gate did not pass.")
    if behavior.get("official_organization_registry_used") is not False:
        failures.append("An official organization registry was unexpectedly used.")
    if behavior.get("permission_restricted_source_used") is not False:
        failures.append("Permission-restricted source data was unexpectedly used.")
    if behavior.get("automatic_enforcement_allowed") is not False:
        failures.append("Behavior candidate permits automatic enforcement.")
    if behavior.get("connected_to_live_moderation") is not False:
        failures.append("Behavior candidate is already connected to live moderation.")

    if matching.get("passed_development_contract") is not True:
        failures.append("Community-candidate matching contract did not pass.")
    policy = matching.get("policy_contract", {})
    if not isinstance(policy, dict):
        policy = {}
    if policy.get("community_candidates_are_confirmed_designations") is not False:
        failures.append("Community candidates were treated as confirmed designations.")
    if policy.get("permitted_active_category") != "Uncertain only":
        failures.append("Community matcher permits an unsafe category output.")
    if policy.get("automatic_enforcement_allowed") is not False:
        failures.append("Community matcher permits automatic enforcement.")
    if policy.get("connected_to_live_moderation") is not False:
        failures.append("Community matcher is already connected to live moderation.")

    community_policy = community.get("policy_contract", {})
    validation = community.get("validation", {})
    if not isinstance(community_policy, dict):
        community_policy = {}
    if not isinstance(validation, dict):
        validation = {}
    if community.get("source_license") != "CC0-1.0":
        failures.append("Community candidate data is not marked CC0-1.0.")
    if validation.get("passed") is not True:
        failures.append("Community candidate import validation did not pass.")
    if community_policy.get("wikipedia_prose_downloaded") is not False:
        failures.append("Wikipedia prose was unexpectedly downloaded.")
    if community_policy.get("extremism_inferred_from_ideology") is not False:
        failures.append("Extremism was inferred from ideology.")
    if community_policy.get("automatic_enforcement_allowed") is not False:
        failures.append("Community data permits automatic enforcement.")

    existing_holdout_paths = [
        str(path) for path in FORBIDDEN_PRE_FREEZE_PATHS if path.exists()
    ]
    if existing_holdout_paths:
        failures.append(
            "An RC1 independent dataset or report already exists before freeze: "
            + ", ".join(existing_holdout_paths)
        )
    if failures:
        raise RuntimeError("Freeze validation failed:\n- " + "\n- ".join(failures))

    return {
        "behavior_records": behavior.get("records"),
        "behavior_accuracy": behavior.get("accuracy"),
        "matching_contract_records": matching.get("records"),
        "matching_contract_accuracy_percent": matching.get("accuracy_percent"),
        "community_candidate_records": validation.get("records"),
        "community_data_license": community.get("source_license"),
    }


def copy_inputs() -> None:
    copies = {
        CANDIDATE_DIRECTORY / "source" / "terrorism_extremism_service.py": BEHAVIOR_SERVICE,
        CANDIDATE_DIRECTORY
        / "source"
        / "wikidata_terrorism_candidate_service.py": COMMUNITY_SERVICE,
        CANDIDATE_DIRECTORY / "data" / "candidates.csv": COMMUNITY_CSV,
        CANDIDATE_DIRECTORY
        / "data"
        / "wikidata_manifest.json": COMMUNITY_MANIFEST,
        CANDIDATE_DIRECTORY
        / "evidence"
        / "behavior_development_report.json": BEHAVIOR_REPORT,
        CANDIDATE_DIRECTORY
        / "evidence"
        / "community_matching_contract.json": MATCHING_REPORT,
    }
    for destination, source in copies.items():
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)


def main() -> None:
    evidence_summary = validate_inputs()
    expected_hashes = source_hashes()

    if MANIFEST_PATH.exists():
        existing = read_json(MANIFEST_PATH)
        if existing.get("locked_file_sha256") != expected_hashes:
            raise RuntimeError(
                "The frozen candidate already exists with different hashes. "
                "Create a new candidate version instead of overwriting it."
            )
        print("TERRORISM & EXTREMISM V3 RC1 FREEZE")
        print("=" * 60)
        print("The candidate is already frozen with matching hashes.")
        print(f"Candidate: {CANDIDATE_NAME}")
        print(f"Manifest: {MANIFEST_PATH}")
        return

    copy_inputs()
    copied_hashes = {
        str(path.relative_to(CANDIDATE_DIRECTORY)).replace("\\", "/"): sha256_file(path)
        for path in CANDIDATE_DIRECTORY.rglob("*")
        if path.is_file()
    }
    if copied_hashes != expected_hashes:
        raise RuntimeError("Copied candidate files do not match their source hashes.")

    manifest = {
        "candidate": CANDIDATE_NAME,
        "frozen_utc": datetime.now(timezone.utc).isoformat(),
        "locked_file_sha256": copied_hashes,
        "evidence_summary": evidence_summary,
        "development_gate_passed": True,
        "community_matching_contract_passed": True,
        "independent_holdout_created_before_freeze": False,
        "independent_holdout_used_before_freeze": False,
        "independently_validated": False,
        "eligible_for_live_integration": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "permitted_community_candidate_output": "Uncertain only",
        "confirmed_legal_designations": 0,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "wikipedia_prose_used": False,
        "wikidata_license": "CC0-1.0",
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("TERRORISM & EXTREMISM V3 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {MANIFEST_PATH}")
    print("Behavior development gate passed: True")
    print("Community matching contract passed: True")
    print("Independent holdout created before freeze: False")
    print("Independent holdout used before freeze: False")
    print("Confirmed legal designations: 0")
    print("Permitted community-candidate output: Uncertain only")
    print("Official registry used: False")
    print("Permission-restricted source used: False")
    print("Wikipedia prose used: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("RC1 is frozen and ready for one independent challenge.")


if __name__ == "__main__":
    main()
