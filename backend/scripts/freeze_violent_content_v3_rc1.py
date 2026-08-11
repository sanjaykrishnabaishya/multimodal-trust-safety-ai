from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE = "violent-content-v3-rc1"
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
EMBEDDING_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "backend" / "storage" / "models" / "violent_content_v3"
DATASET_DIR = ROOT / "datasets" / "development" / "violent_content_v3"
REPORT_DIR = ROOT / "reports" / "evaluation" / "violent_content" / "v3_development"
CANDIDATE_DIR = ROOT / "backend" / "storage" / "candidates" / CANDIDATE
SOURCE_DIR = CANDIDATE_DIR / "source"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required file not found: {path}")


def main() -> None:
    classifier = MODEL_DIR / "classifier.joblib"
    config = MODEL_DIR / "config.json"
    dataset = DATASET_DIR / "development.csv"
    dataset_manifest = DATASET_DIR / "manifest.json"
    validation_report = REPORT_DIR / "validation_report.json"
    generator_source = ROOT / "backend" / "scripts" / "generate_violent_content_v3_development.py"
    trainer_source = ROOT / "backend" / "scripts" / "train_violent_content_v3_semantic.py"

    required = (
        classifier,
        config,
        dataset,
        dataset_manifest,
        validation_report,
        generator_source,
        trainer_source,
    )
    for path in required:
        require_file(path)

    development = json.loads(validation_report.read_text(encoding="utf-8"))
    if development.get("passed_development_gate") is not True:
        raise RuntimeError("The V3 development gate has not passed. Refusing to freeze.")
    model_config = json.loads(config.read_text(encoding="utf-8"))
    if model_config.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("Development candidate must forbid automatic enforcement.")
    if CANDIDATE_DIR.exists():
        raise FileExistsError(
            f"Candidate already exists and will not be overwritten: {CANDIDATE_DIR}"
        )

    SOURCE_DIR.mkdir(parents=True, exist_ok=False)
    shutil.copy2(classifier, CANDIDATE_DIR / "classifier.joblib")
    shutil.copy2(config, CANDIDATE_DIR / "development_config.json")
    shutil.copy2(generator_source, SOURCE_DIR / generator_source.name)
    shutil.copy2(trainer_source, SOURCE_DIR / trainer_source.name)

    frozen_files = (
        CANDIDATE_DIR / "classifier.joblib",
        CANDIDATE_DIR / "development_config.json",
        SOURCE_DIR / generator_source.name,
        SOURCE_DIR / trainer_source.name,
    )
    manifest = {
        "candidate": CANDIDATE,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_pending_independent_evaluation",
        "embedding_model": EMBEDDING_MODEL,
        "embedding_model_revision": EMBEDDING_REVISION,
        "embedding_model_license": "Apache-2.0",
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "development_metrics": {
            "accuracy": development.get("accuracy"),
            "macro_f1": development.get("macro_f1"),
            "records": development.get("records"),
        },
        "development_dataset_sha256": sha256(dataset),
        "development_manifest_sha256": sha256(dataset_manifest),
        "development_report_sha256": sha256(validation_report),
        "frozen_file_hashes": {
            str(path.relative_to(CANDIDATE_DIR)).replace("\\", "/"): sha256(path)
            for path in frozen_files
        },
        "immutability_rule": (
            "Do not modify this candidate after viewing any independent holdout "
            "aggregate or record-level result. Create a new candidate instead."
        ),
        "holdout_rule": (
            "V1 RC1 and V2 RC1 holdouts are prohibited. A fresh, fixed V3 "
            "holdout must be created after this freeze."
        ),
    }
    manifest_path = CANDIDATE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("VIOLENT CONTENT V3 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Embedding revision: {EMBEDDING_REVISION}")
    print(f"Candidate directory: {CANDIDATE_DIR}")
    print(f"Manifest: {manifest_path}")
    print("Automatic enforcement allowed: False")
    print("Independently validated: False")
    print("\nThe candidate is frozen and remains disconnected from live moderation.")


if __name__ == "__main__":
    main()
