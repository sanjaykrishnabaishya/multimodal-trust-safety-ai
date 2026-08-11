from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE = "violent-content-v3-rc2"
ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "backend" / "storage" / "models" / "violent_content_v3_rc2"
DATASET_DIR = ROOT / "datasets" / "development" / "violent_content_v3"
REPORT_DIR = ROOT / "reports" / "evaluation" / "violent_content" / "v3_rc2_development"
CANDIDATE_DIR = ROOT / "backend" / "storage" / "candidates" / CANDIDATE
SOURCE_DIR = CANDIDATE_DIR / "source"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    classifier = MODEL_DIR / "classifier_bundle.joblib"
    config = MODEL_DIR / "config.json"
    report = REPORT_DIR / "validation_report.json"
    dataset = DATASET_DIR / "development.csv"
    dataset_manifest = DATASET_DIR / "manifest.json"
    generator = ROOT / "backend" / "scripts" / "generate_violent_content_v3_development.py"
    trainer = ROOT / "backend" / "scripts" / "train_violent_content_v3_rc2.py"
    required = (classifier, config, report, dataset, dataset_manifest, generator, trainer)
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    report_data = json.loads(report.read_text(encoding="utf-8"))
    config_data = json.loads(config.read_text(encoding="utf-8"))
    if report_data.get("passed_development_gate") is not True:
        raise RuntimeError("RC2 development gate has not passed.")
    if float(config_data.get("minimum_score_margin", 0.0)) <= 0.0:
        raise RuntimeError("RC2 must have a positive score margin.")
    if config_data.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC2 must forbid automatic enforcement before validation.")
    if CANDIDATE_DIR.exists():
        raise FileExistsError(
            f"Frozen candidate already exists and will not be overwritten: {CANDIDATE_DIR}"
        )

    SOURCE_DIR.mkdir(parents=True, exist_ok=False)
    copies = (
        (classifier, CANDIDATE_DIR / "classifier_bundle.joblib"),
        (config, CANDIDATE_DIR / "development_config.json"),
        (generator, SOURCE_DIR / generator.name),
        (trainer, SOURCE_DIR / trainer.name),
    )
    for source, destination in copies:
        shutil.copy2(source, destination)

    frozen_files = tuple(destination for _, destination in copies)
    manifest = {
        "candidate": CANDIDATE,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_pending_independent_evaluation",
        "architecture": "three one-vs-rest evidence detectors with safe default",
        "embedding_model": config_data["embedding_model"],
        "embedding_model_revision": config_data["embedding_model_revision"],
        "embedding_model_license": "Apache-2.0",
        "minimum_score_margin": config_data["minimum_score_margin"],
        "thresholds": config_data["thresholds"],
        "default_result": "safe_or_other",
        "default_behavior": "No specialist override",
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "development_metrics": {
            "accuracy": report_data["accuracy"],
            "macro_f1": report_data["macro_f1"],
            "records": report_data["validation_records"],
        },
        "development_dataset_sha256": sha256(dataset),
        "development_manifest_sha256": sha256(dataset_manifest),
        "development_report_sha256": sha256(report),
        "frozen_file_hashes": {
            str(path.relative_to(CANDIDATE_DIR)).replace("\\", "/"): sha256(path)
            for path in frozen_files
        },
        "prohibited_evaluation_data": [
            "violent-content-v1-rc1 holdout",
            "violent-content-v2-rc1 holdout",
            "violent-content-v3-rc1 holdout",
        ],
        "immutability_rule": (
            "Never modify RC2 after viewing its independent holdout result. "
            "Create RC3 if the readiness gate fails."
        ),
    }
    manifest_path = CANDIDATE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("VIOLENT CONTENT V3 RC2 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Minimum score margin: {manifest['minimum_score_margin']:.2f}")
    print(f"Candidate directory: {CANDIDATE_DIR}")
    print(f"Manifest: {manifest_path}")
    print("Automatic enforcement allowed: False")
    print("Independently validated: False")
    print("The candidate is frozen and remains disconnected from live moderation.")


if __name__ == "__main__":
    main()
