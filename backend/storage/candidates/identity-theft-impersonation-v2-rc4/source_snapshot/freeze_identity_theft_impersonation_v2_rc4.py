"""Freeze development-passing Identity Theft & Impersonation V2 RC4."""

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
CANDIDATE = "identity-theft-impersonation-v2-rc4"
DEST = BACKEND / "storage" / "candidates" / CANDIDATE
DATA = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc4" / "development.csv"
REPORT = ROOT / "reports" / "evaluation" / "identity_theft_impersonation" / "v2_rc4_development" / "report.json"
SOURCES = {
    "source_snapshot/identity_theft_impersonation_v2_rc4_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc4_service.py",
    "policy_snapshot/identity_theft_impersonation_v2_rc4_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc4_policy.json",
    "dependency_snapshot/identity_theft_impersonation_v2_rc3_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc3_service.py",
    "dependency_snapshot/identity_theft_impersonation_v2_rc3_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc3_policy.json",
    "dependency_snapshot/identity_theft_impersonation_v2_rc2_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc2_service.py",
    "dependency_snapshot/identity_theft_impersonation_v2_rc2_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc2_policy.json",
    "dependency_snapshot/identity_theft_impersonation_v2_rc1_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc1_service.py",
    "dependency_snapshot/identity_theft_impersonation_v2_rc1_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc1_policy.json",
    "source_snapshot/evaluate_identity_theft_impersonation_v2_rc4_development.py": BACKEND / "scripts/evaluate_identity_theft_impersonation_v2_rc4_development.py",
    "source_snapshot/freeze_identity_theft_impersonation_v2_rc4.py": Path(__file__).resolve(),
    "source_boundary/IDENTITY_THEFT_IMPERSONATION_SOURCE_BOUNDARY.md": ROOT / "docs/IDENTITY_THEFT_IMPERSONATION_SOURCE_BOUNDARY.md",
    "development/development.csv": DATA,
    "development_evidence/report.json": REPORT,
}
GATE = {
    "minimum_accuracy": .95, "minimum_identity_precision": .97,
    "minimum_identity_recall": .95, "minimum_safe_specificity": .99,
    "minimum_f1": .96, "minimum_group_accuracy": .92,
    "maximum_action_contract_failures": 0, "maximum_category_mix_failures": 0,
    "maximum_data_contract_failures": 0, "maximum_authority_contract_failures": 0,
    "maximum_processing_errors": 0, "require_zero_development_overlap": True,
    "require_frozen_source_hashes": True, "require_no_raw_holdout_storage": True,
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    if DEST.exists():
        raise FileExistsError(DEST)
    report: dict[str, Any] = json.loads(REPORT.read_text(encoding="utf-8"))
    required = {
        "passed_development_gate": True, "records": 480, "unique_texts": 480,
        "prior_development_overlap": 0, "action_contract_failures": 0,
        "category_mix_failures": 0, "data_contract_failures": 0,
        "authority_contract_failures": 0, "processing_errors": 0,
        "prior_independent_examples_used": False,
        "prior_individual_predictions_used": False,
        "real_identity_documents_used": False, "raw_credentials_used": False,
        "complete_personal_identifiers_used": False, "external_provider_used": False,
        "connected_to_live_moderation": False,
    }
    for key, value in required.items():
        if report.get(key) != value:
            raise RuntimeError(f"Development freeze requirement failed: {key}")
    if sha(DATA) != report.get("dataset_sha256"):
        raise RuntimeError("Dataset hash mismatch")
    with DATA.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 480 or len({row["text"] for row in rows}) != 480:
        raise RuntimeError("Dataset uniqueness failed")

    temporary = DEST.with_name(DEST.name + ".tmp")
    temporary.mkdir(parents=True)
    try:
        artifacts = []
        for relative, source in SOURCES.items():
            target = temporary / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            artifacts.append({"relative_path": relative, "size_bytes": target.stat().st_size,
                              "sha256": sha(target)})
        manifest = {
            "candidate": CANDIDATE, "component": "Identity Theft & Impersonation",
            "candidate_type": "local deterministic evidence-aware identity review router",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {key: report[key] for key in (
                "records", "unique_texts", "accuracy", "identity_precision", "identity_recall",
                "safe_specificity", "f1", "minimum_group_accuracy", "action_contract_failures",
                "category_mix_failures", "data_contract_failures",
                "authority_contract_failures", "processing_errors")},
            "artifacts": artifacts, "independent_gate_frozen_before_holdout": GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc4": False,
            "prior_independent_examples_used_for_rc4": False,
            "prior_individual_predictions_used_for_rc4": False,
            "real_identity_documents_used": False, "raw_credentials_used": False,
            "complete_personal_identifiers_used": False,
            "face_recognition_used": False, "voice_identity_matching_used": False,
            "biometric_embeddings_used": False,
            "appearance_based_identity_inference_allowed": False,
            "external_provider_used": False, "external_transmission_allowed": False,
            "permitted_active_outputs": ["Identity Theft & Impersonation", "Uncertain"],
            "required_identity_action": "Restrict account activity and send for identity review",
            "human_review_required": True, "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_account_suspension_allowed": False,
            "automatic_enforcement_allowed": False,
            "evaluation_reporting_contract": {
                "store_raw_holdout_text": False, "store_individual_predictions": False,
                "print_individual_predictions": False, "report_aggregate_metrics_only": True,
            },
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary.rename(DEST)
    except Exception:
        if temporary.exists(): shutil.rmtree(temporary)
        raise
    print("IDENTITY THEFT & IMPERSONATION V2 RC4 FREEZE\n" + "=" * 60)
    print(f"Candidate: {CANDIDATE}\nCandidate directory: {DEST}\nDevelopment gate passed: True")
    print("Independent holdout created before freeze: False\nIndependent holdout used before freeze: False")
    print("Prior independent examples used for RC4: False\nReal identity documents used: False")
    print("External provider used: False\nConnected to live moderation: False\nAutomatic enforcement allowed: False")
    print("V2 RC4 is frozen for one aggregate-only independent challenge.")


if __name__ == "__main__": main()
