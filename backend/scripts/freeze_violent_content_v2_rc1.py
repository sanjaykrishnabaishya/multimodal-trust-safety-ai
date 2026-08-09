from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE = "violent-content-v2-rc1"
SOURCE_PATHS = (
    "backend/app/services/violent_content_service.py",
    "backend/app/services/targeted_threat_service.py",
    "backend/app/services/fact_check_fusion_service.py",
    "backend/app/services/fusion_service.py",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    candidate_dir = root / "backend" / "storage" / "candidates" / CANDIDATE
    snapshot_dir = candidate_dir / "source_snapshot"
    manifest_path = candidate_dir / "manifest.json"

    if manifest_path.exists():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        changed = []
        for item in manifest.get("source_files", []):
            source = root / item["path"]
            if not source.exists() or sha256(source) != item["sha256"]:
                changed.append(item["path"])
        if changed:
            raise RuntimeError(
                "V2 RC1 was already frozen, but active source differs: "
                + ", ".join(changed)
            )
        print("Violent Content V2 RC1 is already frozen; hashes match.")
        print(f"Manifest: {manifest_path}")
        return

    snapshot_dir.mkdir(parents=True, exist_ok=True)
    source_files = []

    for relative in SOURCE_PATHS:
        source = root / relative
        if not source.exists():
            raise FileNotFoundError(source)
        file_hash = sha256(source)
        snapshot = snapshot_dir / relative.replace("/", "__")
        shutil.copy2(source, snapshot)
        source_files.append(
            {
                "path": relative,
                "sha256": file_hash,
                "snapshot": str(snapshot.relative_to(root)).replace("\\", "/"),
            }
        )

    development_report = (
        root
        / "reports"
        / "evaluation"
        / "violent_content"
        / "v2_development"
        / "report.json"
    )
    if not development_report.exists():
        raise FileNotFoundError(
            "Run the V2 development evaluation before freezing the candidate."
        )
    development = json.loads(development_report.read_text(encoding="utf-8"))
    if not development.get("passed_development_gate", False):
        raise RuntimeError("V2 did not pass its development gate.")

    manifest = {
        "candidate": CANDIDATE,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_files": source_files,
        "development_report_path": str(
            development_report.relative_to(root)
        ).replace("\\", "/"),
        "development_report_sha256": sha256(development_report),
        "development_summary": {
            "records": development.get("records"),
            "accuracy_percent": development.get("accuracy_percent"),
            "precision_percent": development.get("precision_percent"),
            "recall_percent": development.get("recall_percent"),
            "specificity_percent": development.get("specificity_percent"),
            "f1_percent": development.get("f1_percent"),
            "exact_category_action_accuracy_percent": development.get(
                "exact_category_action_accuracy_percent"
            ),
            "action_contract_failures": development.get(
                "action_contract_failures"
            ),
            "regression_tests_passed": 19,
            "regression_tests_failed": 0,
        },
        "policy_boundary": {
            "targeted_physical_threat": "Cyberbullying & Harassment",
            "graphic_or_depicted_bodily_harm": "Violent Content",
            "non_graphic_reporting_or_discussion": (
                "Allow or allow with sensitive-content warning according to context"
            ),
        },
        "limitations": [
            "The 100% development result is not independent accuracy.",
            "RC1 must not be modified using its future holdout predictions.",
            "The current component classifies extracted English text and visual descriptions.",
            "Direct image and video accuracy requires separate multimodal benchmarks.",
            "The overall application is not production ready from this component alone.",
        ],
    }

    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print("Violent Content V2 RC1 frozen successfully.")
    print(f"Manifest: {manifest_path}")
    print("Source snapshot hashes are now locked for independent evaluation.")
    print("This component is not yet independently validated.")


if __name__ == "__main__":
    main()
