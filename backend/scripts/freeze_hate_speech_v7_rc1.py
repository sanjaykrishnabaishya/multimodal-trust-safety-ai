from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIRECTORY = ROOT / "backend" / "storage" / "models" / "hate_speech_v7"
DEVELOPMENT_REPORT = (
    ROOT
    / "reports"
    / "evaluation"
    / "hate_speech"
    / "v7_selective_development"
    / "validation_report.json"
)
CANDIDATE_PARENT = ROOT / "backend" / "storage" / "candidates"
CANDIDATE_DIRECTORY = CANDIDATE_PARENT / "hate-speech-v7-rc1"
TRAINING_SOURCE = ROOT / "backend" / "scripts" / "train_hate_speech_v7_selective.py"
DEPENDENCY_SOURCE = ROOT / "backend" / "scripts" / "train_hate_speech_v6_finetuned.py"

DEVELOPMENT_DATA_FILES = (
    ROOT / "datasets" / "public" / "civil_comments_hate_rc2" / "train.csv",
    ROOT / "datasets" / "public" / "civil_comments_hate_rc2" / "validation.csv",
    ROOT / "datasets" / "public" / "hatexplain" / "train.csv",
    ROOT / "datasets" / "public" / "hatexplain" / "validation.csv",
)

CANDIDATE_NAME = "hate-speech-v7-rc1"
INDEPENDENT_GATE = {
    "minimum_overall_selective_precision": 0.85,
    "minimum_overall_recall": 0.30,
    "minimum_overall_specificity": 0.95,
    "minimum_civil_selective_precision": 0.85,
    "minimum_civil_recall": 0.20,
    "minimum_civil_specificity": 0.95,
    "minimum_hatexplain_selective_precision": 0.85,
    "minimum_hatexplain_recall": 0.20,
    "minimum_hatexplain_specificity": 0.95,
    "minimum_total_accepted": 100,
    "minimum_civil_accepted": 10,
    "maximum_action_contract_failures": 0,
    "maximum_category_mix_failures": 0,
    "maximum_processing_errors": 0,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required freeze input was not found: {path}")


def copy_with_hash(source: Path, destination: Path) -> dict[str, Any]:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return {
        "relative_path": destination.as_posix(),
        "size_bytes": destination.stat().st_size,
        "sha256": sha256_file(destination),
    }


def main() -> None:
    if CANDIDATE_DIRECTORY.exists():
        raise FileExistsError(
            f"Frozen candidate already exists and will not be overwritten: "
            f"{CANDIDATE_DIRECTORY}"
        )

    require_file(DEVELOPMENT_REPORT)
    require_file(TRAINING_SOURCE)
    require_file(DEPENDENCY_SOURCE)
    for path in DEVELOPMENT_DATA_FILES:
        require_file(path)

    development = json.loads(DEVELOPMENT_REPORT.read_text(encoding="utf-8"))
    if development.get("candidate") != "hate-speech-v7-selective-development":
        raise RuntimeError("Unexpected V7 development report candidate name.")
    if development.get("passed_development_gate") is not True:
        raise RuntimeError("V7 did not pass its predefined development gate.")
    if development.get("test_splits_opened") is not False:
        raise RuntimeError("The V7 test-split contract is invalid.")
    if development.get("connected_to_live_moderation") is not False:
        raise RuntimeError("V7 must be disconnected before it can be frozen.")
    if development.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("V7 must remain review-only before freeze.")

    required_model_files = (
        "model.safetensors",
        "config.json",
        "tokenizer_config.json",
        "tokenizer.json",
        "development_config.json",
        "calibration.json",
    )
    for name in required_model_files:
        require_file(MODEL_DIRECTORY / name)

    CANDIDATE_PARENT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="hate-speech-v7-rc1-freeze-",
        dir=CANDIDATE_PARENT,
    ) as temporary_name:
        temporary = Path(temporary_name)
        artifacts: list[dict[str, Any]] = []

        for name in required_model_files:
            source = MODEL_DIRECTORY / name
            destination = temporary / "model" / name
            item = copy_with_hash(source, destination)
            item["relative_path"] = f"model/{name}"
            artifacts.append(item)

        report_destination = temporary / "development_evidence" / "validation_report.json"
        item = copy_with_hash(DEVELOPMENT_REPORT, report_destination)
        item["relative_path"] = "development_evidence/validation_report.json"
        artifacts.append(item)

        for source in (TRAINING_SOURCE, DEPENDENCY_SOURCE):
            destination = temporary / "source_snapshot" / source.name
            item = copy_with_hash(source, destination)
            item["relative_path"] = f"source_snapshot/{source.name}"
            artifacts.append(item)

        development_data = [
            {
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "size_bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "role": "development train/validation only",
            }
            for path in DEVELOPMENT_DATA_FILES
        ]

        manifest = {
            "candidate": CANDIDATE_NAME,
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "component": "Hate Speech & Discrimination",
            "permitted_active_output": "Hate Speech & Discrimination",
            "abusive_words_behavior": "No override; validated RC2 retains ownership",
            "safe_or_other_behavior": "No allow override",
            "uncertain_behavior": "No category override",
            "development_gate_passed": True,
            "test_splits_used_before_freeze": False,
            "test_split_files_opened_by_freeze": False,
            "independently_validated": False,
            "eligible_for_live_integration": False,
            "connected_to_live_moderation": False,
            "automatic_enforcement_allowed": False,
            "required_action_if_later_integrated": "Refer to human review",
            "independent_gate_frozen_before_test": INDEPENDENT_GATE,
            "artifacts": artifacts,
            "development_data_hashes": development_data,
            "reserved_test_contract": {
                "civil_comments_test": "sealed until one RC1 evaluation",
                "hatexplain_test": "sealed until one RC1 evaluation",
                "test_data_may_enter_training": False,
                "test_data_may_enter_rag": False,
                "record_level_test_predictions_may_be_stored": False,
                "raw_test_text_may_be_stored": False,
            },
        }
        manifest_path = temporary / "manifest.json"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        temporary.rename(CANDIDATE_DIRECTORY)

    print("HATE SPEECH V7 RC1 FREEZE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Candidate directory: {CANDIDATE_DIRECTORY}")
    print(f"Manifest: {CANDIDATE_DIRECTORY / 'manifest.json'}")
    print("Development gate passed: True")
    print("Test splits used before freeze: False")
    print("Test files opened by freeze: False")
    print("Independent gate locked before testing: True")
    print("Independently validated: False")
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC1 is frozen and ready for one independent evaluation.")


if __name__ == "__main__":
    main()
