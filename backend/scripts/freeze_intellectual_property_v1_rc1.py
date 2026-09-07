"""Freeze development-passing Intellectual Property V1 RC1."""

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
CANDIDATE = "intellectual-property-v1-rc1"
DEST = BACKEND / "storage" / "candidates" / CANDIDATE
DATA = ROOT / "datasets" / "development" / "intellectual_property_v1_rc1" / "development.csv"
REPORT = ROOT / "reports" / "evaluation" / "intellectual_property" / "v1_rc1_development" / "report.json"
SOURCES = {
    "source_snapshot/intellectual_property_v1_rc1_service.py": BACKEND / "app" / "services" / "intellectual_property_v1_rc1_service.py",
    "policy_snapshot/intellectual_property_v1_rc1_policy.json": BACKEND / "app" / "evidence" / "intellectual_property_v1_rc1_policy.json",
    "source_snapshot/evaluate_intellectual_property_v1_rc1_development.py": BACKEND / "scripts" / "evaluate_intellectual_property_v1_rc1_development.py",
    "source_snapshot/freeze_intellectual_property_v1_rc1.py": Path(__file__).resolve(),
    "source_boundary/INTELLECTUAL_PROPERTY_SOURCE_BOUNDARY.md": ROOT / "docs" / "INTELLECTUAL_PROPERTY_SOURCE_BOUNDARY.md",
    "development/development.csv": DATA,
    "development_evidence/report.json": REPORT,
}
GATE = {
    "minimum_accuracy": 0.95,
    "minimum_ip_precision": 0.97,
    "minimum_ip_recall": 0.95,
    "minimum_safe_specificity": 0.99,
    "minimum_f1": 0.96,
    "minimum_group_accuracy": 0.92,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_data_contract_failures": 0,
    "maximum_authority_contract_failures": 0,
    "maximum_processing_errors": 0,
    "require_zero_development_overlap": True,
    "require_frozen_source_hashes": True,
    "require_no_raw_holdout_storage": True,
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    if DEST.exists():
        raise FileExistsError(DEST)
    report = read(REPORT)
    required = {
        "passed_development_gate": True, "records": 600, "unique_texts": 600,
        "action_contract_failures": 0, "category_mix_failures": 0,
        "data_contract_failures": 0, "authority_contract_failures": 0,
        "processing_errors": 0, "raw_copyrighted_works_used": False,
        "pirated_material_used": False, "private_claimant_data_used": False,
        "external_provider_used": False, "connected_to_live_moderation": False,
    }
    for key, value in required.items():
        if report.get(key) != value:
            raise RuntimeError(f"Development freeze requirement failed: {key}")
    if sha(DATA) != report.get("dataset_sha256"):
        raise RuntimeError("Dataset hash mismatch")
    with DATA.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 600 or len({row["text"] for row in rows}) != 600:
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
            "candidate": CANDIDATE,
            "component": "Intellectual Property Infringement",
            "candidate_type": "local deterministic evidence-aware review router",
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "development_gate_passed": True,
            "development_metrics": {key: report[key] for key in (
                "records", "unique_texts", "accuracy", "ip_precision", "ip_recall",
                "safe_specificity", "f1", "minimum_group_accuracy",
                "action_contract_failures", "category_mix_failures",
                "data_contract_failures", "authority_contract_failures", "processing_errors")},
            "artifacts": artifacts, "independent_gate_frozen_before_holdout": GATE,
            "independent_holdout_created_before_freeze": False,
            "independent_holdout_used_before_freeze": False,
            "independent_holdout_may_modify_rc1": False,
            "raw_copyrighted_works_used": False, "pirated_material_used": False,
            "private_claimant_data_used": False,
            "ownership_or_licence_inference_allowed": False,
            "legal_determination_allowed": False,
            "external_provider_used": False, "external_transmission_allowed": False,
            "permitted_active_outputs": ["Intellectual Property Infringement", "Uncertain"],
            "required_ip_action": "Restrict distribution and send for qualified human review",
            "human_review_required": True, "independently_validated": False,
            "eligible_for_guarded_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_takedown_allowed": False, "automatic_enforcement_allowed": False,
            "evaluation_reporting_contract": {
                "store_raw_holdout_text": False, "store_individual_predictions": False,
                "print_individual_predictions": False, "report_aggregate_metrics_only": True,
            },
        }
        (temporary / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
        temporary.rename(DEST)
    except Exception:
        if temporary.exists():
            shutil.rmtree(temporary)
        raise
    print("INTELLECTUAL PROPERTY V1 RC1 FREEZE\n" + "=" * 60)
    print(f"Candidate: {CANDIDATE}\nCandidate directory: {DEST}\nDevelopment gate passed: True")
    print("Independent holdout created before freeze: False\nIndependent holdout used before freeze: False")
    print("Raw copyrighted works used: False\nExternal provider used: False")
    print("Connected to live moderation: False\nAutomatic enforcement allowed: False")
    print("RC1 is frozen for one aggregate-only independent challenge.")


if __name__ == "__main__":
    main()
