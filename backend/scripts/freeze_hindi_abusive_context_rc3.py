from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND_ROOT = REPO_ROOT / "backend"

CANDIDATE_NAME = "hindi-abusive-context-rc3"
CANDIDATE_DIRECTORY = (
    BACKEND_ROOT / "storage" / "candidates" / CANDIDATE_NAME
)
SOURCE_SNAPSHOT_DIRECTORY = CANDIDATE_DIRECTORY / "source"
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"

SERVICE_PATH = (
    BACKEND_ROOT / "app" / "services" / "hindi_abusive_context_service.py"
)
LEXICON_PATH = (
    REPO_ROOT
    / "datasets"
    / "development"
    / "hindi_abusive_rc3"
    / "lexicon.csv"
)
PROVENANCE_PATH = LEXICON_PATH.with_name("provenance.json")
DEVELOPMENT_DATASET_PATH = LEXICON_PATH.with_name("context_development.csv")
DEVELOPMENT_REPORT_PATH = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "hindi_abusive_rc3"
    / "context_development_report.json"
)
EXTERNAL_REPORT_PATH = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "cyberbullyx63k_hindi_rc3"
    / "aggregate_report.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required RC3 file was not found: {path}")


def add_local_git_exclusions() -> bool:
    exclude_path = REPO_ROOT / ".git" / "info" / "exclude"
    if not exclude_path.parent.is_dir():
        return False
    existing = exclude_path.read_text(encoding="utf-8") if exclude_path.exists() else ""
    additions = [
        "datasets/development/hindi_abusive_rc3/",
        "reports/evaluation/cyberbullying/hindi_abusive_rc3/",
        "reports/evaluation/cyberbullying/cyberbullyx63k_hindi_rc3/",
    ]
    missing = [line for line in additions if line not in existing.splitlines()]
    if not missing:
        return True
    prefix = "" if not existing or existing.endswith("\n") else "\n"
    exclude_path.write_text(
        existing
        + prefix
        + "# Local Hindi/Hinglish evaluation data; source redistribution rights are unverified.\n"
        + "\n".join(missing)
        + "\n",
        encoding="utf-8",
    )
    return True


def main() -> None:
    for path in (
        SERVICE_PATH,
        LEXICON_PATH,
        PROVENANCE_PATH,
        DEVELOPMENT_DATASET_PATH,
        DEVELOPMENT_REPORT_PATH,
    ):
        require_file(path)

    if EXTERNAL_REPORT_PATH.exists():
        raise RuntimeError(
            "The external CyberbullyX-63K report already exists. Refusing to "
            "pretend this is a pre-evaluation freeze. Create a new candidate instead."
        )

    provenance = json.loads(PROVENANCE_PATH.read_text(encoding="utf-8"))
    development_report = json.loads(
        DEVELOPMENT_REPORT_PATH.read_text(encoding="utf-8")
    )
    if not development_report.get("passed_development_gate"):
        raise RuntimeError("The generated RC3 development gate has not passed.")

    if MANIFEST_PATH.exists():
        existing = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        expected_hashes = existing.get("frozen_input_hashes", {})
        current_hashes = {
            "service": sha256_file(SERVICE_PATH),
            "lexicon": sha256_file(LEXICON_PATH),
            "provenance": sha256_file(PROVENANCE_PATH),
            "development_dataset": sha256_file(DEVELOPMENT_DATASET_PATH),
            "development_report": sha256_file(DEVELOPMENT_REPORT_PATH),
        }
        if expected_hashes == current_hashes:
            print("Hindi/Hinglish RC3 is already frozen with matching hashes.")
            print(f"Manifest: {MANIFEST_PATH}")
            return
        raise RuntimeError(
            "A different RC3 manifest already exists. Do not overwrite a frozen "
            "candidate; create RC4."
        )

    SOURCE_SNAPSHOT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    snapshot_service_path = (
        SOURCE_SNAPSHOT_DIRECTORY / "hindi_abusive_context_service.py"
    )
    shutil.copy2(SERVICE_PATH, snapshot_service_path)

    frozen_input_hashes = {
        "service": sha256_file(SERVICE_PATH),
        "lexicon": sha256_file(LEXICON_PATH),
        "provenance": sha256_file(PROVENANCE_PATH),
        "development_dataset": sha256_file(DEVELOPMENT_DATASET_PATH),
        "development_report": sha256_file(DEVELOPMENT_REPORT_PATH),
    }
    manifest = {
        "candidate": CANDIDATE_NAME,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_pending_external_evaluation",
        "component_scope": (
            "Hindi/Hinglish abusive-word context boundary, ambiguity checks, "
            "masking, and separation from cyberbullying, hate speech, and sexual harassment."
        ),
        "source_lexicon": {
            "source_file_name": provenance.get("source_file_name", ""),
            "source_sha256": provenance.get("source_sha256", ""),
            "license_status": provenance.get("source_license_status", "unknown"),
            "redistribution_allowed": False,
            "copied_into_candidate_directory": False,
        },
        "generated_development_metrics": {
            "records": development_report.get("records"),
            "accuracy_percent": development_report.get("accuracy_percent"),
            "masking_failures": development_report.get("masking_failures"),
            "category_mix_failures": development_report.get("category_mix_failures"),
            "passed": development_report.get("passed_development_gate"),
            "counts_as_independent_accuracy": False,
        },
        "frozen_input_hashes": frozen_input_hashes,
        "snapshot_hashes": {
            "source/hindi_abusive_context_service.py": sha256_file(
                snapshot_service_path
            )
        },
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "independently_validated": False,
        "external_evaluation_contract": {
            "cyberbullyx63k_used_before_freeze": False,
            "raw_external_text_may_be_stored": False,
            "record_level_predictions_may_be_stored": False,
            "external_dataset_may_be_used_for_training": False,
            "external_result_must_not_modify_rc3": True,
            "failure_requires_new_candidate": "hindi-abusive-context-rc4",
        },
        "immutability_rule": (
            "Do not modify the RC3 service, lexicon, provenance, development "
            "dataset, or development report after external evaluation begins."
        ),
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    local_exclusions_installed = add_local_git_exclusions()

    print("HINDI/HINGLISH ABUSIVE CONTEXT RC3 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {MANIFEST_PATH}")
    print("Generated development score counted as independent accuracy: False")
    print("External CyberbullyX-63K used before freeze: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("Independently validated: False")
    print(f"Local Git exclusions installed: {local_exclusions_installed}")
    print("Unknown-licence lexicon copied into candidate directory: False")
    print("RC3 is frozen and ready for evaluation-only external testing.")


if __name__ == "__main__":
    main()
