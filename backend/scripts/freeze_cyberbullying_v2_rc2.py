from __future__ import annotations

import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path


CANDIDATE = "cyberbullying-v2-rc2"
ROOT = Path(__file__).resolve().parents[2]
MODEL_DIR = ROOT / "backend" / "storage" / "models" / "cyberbullying_v2_rc2"
DATA_DIR = ROOT / "datasets" / "public" / "civil_comments_cyber"
REPORT_DIR = ROOT / "reports" / "evaluation" / "cyberbullying"
CANDIDATE_DIR = ROOT / "backend" / "storage" / "candidates" / CANDIDATE
SOURCE_DIR = CANDIDATE_DIR / "source"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    artifact = MODEL_DIR / "classifier_bundle.joblib"
    config = MODEL_DIR / "config.json"
    import_manifest = DATA_DIR / "manifest.json"
    train_data = DATA_DIR / "train.csv"
    validation_data = DATA_DIR / "validation.csv"
    test_data = DATA_DIR / "test.csv"
    training_report = REPORT_DIR / "v2_rc2_development" / "validation_report.json"
    calibration_report = REPORT_DIR / "v2_rc2_selective" / "calibration_report.json"
    sources = (
        ROOT / "backend" / "app" / "services" / "cyberbullying_boundary_service.py",
        ROOT / "backend" / "scripts" / "train_civil_comments_cyber_rc2.py",
        ROOT / "backend" / "scripts" / "calibrate_civil_comments_cyber_rc2.py",
    )
    required = (
        artifact,
        config,
        import_manifest,
        train_data,
        validation_data,
        test_data,
        training_report,
        calibration_report,
        *sources,
    )
    for path in required:
        if not path.is_file():
            raise FileNotFoundError(f"Required file not found: {path}")

    configuration = json.loads(config.read_text(encoding="utf-8"))
    calibration = json.loads(calibration_report.read_text(encoding="utf-8"))
    if calibration.get("passed_selective_development_gate") is not True:
        raise RuntimeError("Selective development gate has not passed.")
    if configuration.get("selectively_calibrated") is not True:
        raise RuntimeError("Selective thresholds are not installed in the config.")
    if configuration.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC2 must forbid automatic enforcement before holdout evaluation.")
    if CANDIDATE_DIR.exists():
        raise FileExistsError(
            f"Candidate already exists and will not be overwritten: {CANDIDATE_DIR}"
        )

    SOURCE_DIR.mkdir(parents=True, exist_ok=False)
    copies = [
        (artifact, CANDIDATE_DIR / "classifier_bundle.joblib"),
        (config, CANDIDATE_DIR / "development_config.json"),
    ]
    copies.extend((source, SOURCE_DIR / source.name) for source in sources)
    for source, destination in copies:
        shutil.copy2(source, destination)

    frozen_files = [destination for _, destination in copies]
    manifest = {
        "candidate": CANDIDATE,
        "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "frozen_pending_independent_evaluation",
        "component_scope": (
            "Message-level threat, abusive-word, and safe/no-override evidence plus "
            "policy rules for repeated harassment, unwanted contact, and coordination."
        ),
        "external_dataset": "google/civil_comments",
        "external_dataset_license": "CC0-1.0",
        "embedding_model": configuration["embedding_model"],
        "embedding_model_revision": configuration["embedding_model_revision"],
        "selective_thresholds": configuration["selective_thresholds"],
        "lexical_weight": configuration["lexical_weight"],
        "semantic_weight": configuration["semantic_weight"],
        "uncertain_behavior": configuration["uncertain_behavior"],
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "selective_development_metrics": {
            "selective_accuracy": calibration["selective_accuracy"],
            "coverage": calibration["coverage"],
            "accepted_records": calibration["accepted_records"],
        },
        "dataset_hashes": {
            "train.csv": sha256(train_data),
            "validation.csv": sha256(validation_data),
            "test.csv": sha256(test_data),
            "manifest.json": sha256(import_manifest),
        },
        "report_hashes": {
            "training_validation": sha256(training_report),
            "selective_calibration": sha256(calibration_report),
        },
        "frozen_file_hashes": {
            str(path.relative_to(CANDIDATE_DIR)).replace("\\", "/"): sha256(path)
            for path in frozen_files
        },
        "test_contract": {
            "test_split_used_before_freeze": False,
            "test_split_may_be_used_once_for_independent_evaluation": True,
            "test_split_must_not_modify_rc2": True,
        },
        "immutability_rule": (
            "Do not modify RC2 after viewing the independent test result. "
            "Create RC3 if the readiness gate fails."
        ),
    }
    manifest_path = CANDIDATE_DIR / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("CYBERBULLYING V2 RC2 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Candidate directory: {CANDIDATE_DIR}")
    print(f"Manifest: {manifest_path}")
    print("Test split used before freeze: False")
    print("Automatic enforcement allowed: False")
    print("Independently validated: False")
    print("The candidate is frozen and remains disconnected from live moderation.")


if __name__ == "__main__":
    main()
