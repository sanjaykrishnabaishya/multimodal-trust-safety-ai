from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE = "cyberbullying-v2-rc1"
ROOT = Path(__file__).resolve().parents[2]
SERVICE = ROOT / "backend" / "app" / "services" / "cyberbullying_boundary_service.py"
EVALUATOR = ROOT / "backend" / "scripts" / "evaluate_cyberbullying_v2_development.py"
DATASET = ROOT / "datasets" / "development" / "cyberbullying_v1" / "development.csv"
REPORT = ROOT / "reports" / "evaluation" / "cyberbullying" / "development_v2" / "report.json"
CANDIDATE_DIR = ROOT / "backend" / "storage" / "candidates" / CANDIDATE
SOURCE_DIR = CANDIDATE_DIR / "source"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    required = (SERVICE, EVALUATOR, DATASET, REPORT)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    if report.get("passed_development_gate") is not True:
        raise RuntimeError("Cyberbullying V2 development gate has not passed.")
    if report.get("every_group_passes_85_percent") is not True:
        raise RuntimeError("Every policy behavior group must pass 85% before freezing.")
    if CANDIDATE_DIR.exists():
        raise FileExistsError(
            f"Candidate already exists and will not be overwritten: {CANDIDATE_DIR}"
        )

    SOURCE_DIR.mkdir(parents=True, exist_ok=False)
    service_copy = SOURCE_DIR / SERVICE.name
    evaluator_copy = SOURCE_DIR / EVALUATOR.name
    shutil.copy2(SERVICE, service_copy)
    shutil.copy2(EVALUATOR, evaluator_copy)
    frozen_files = (service_copy, evaluator_copy)
    manifest = {
        "candidate": CANDIDATE,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_pending_independent_evaluation",
        "primary_category_rule": (
            "Cyberbullying & Harassment is primary when repeated targeted abuse, "
            "continued unwanted contact, coordinated harassment, or targeted intimidation exists."
        ),
        "abusive_words_rule": (
            "Abusive Words is primary only when targeted abusive wording exists without "
            "a supported cyberbullying behavior. Detected terms are partially masked."
        ),
        "primary_category_count": 1,
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "development_metrics": {
            "records": report["records"],
            "accuracy": report["accuracy"],
            "label_metrics": report["label_metrics"],
        },
        "development_dataset_sha256": sha256(DATASET),
        "development_report_sha256": sha256(REPORT),
        "frozen_file_hashes": {
            str(path.relative_to(CANDIDATE_DIR)).replace("\\", "/"): sha256(path)
            for path in frozen_files
        },
        "immutability_rule": (
            "Do not modify RC1 after viewing its independent holdout result. "
            "Create RC2 if it fails."
        ),
    }
    manifest_path = CANDIDATE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("CYBERBULLYING V2 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIR}")
    print(f"Manifest: {manifest_path}")
    print("Automatic enforcement allowed: False")
    print("Independently validated: False")
    print("The candidate is frozen and remains disconnected from live moderation.")


if __name__ == "__main__":
    main()
