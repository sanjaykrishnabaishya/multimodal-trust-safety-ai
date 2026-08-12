from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

from scripts import train_hate_speech_v6_finetuned as v6


ROOT = Path(__file__).resolve().parents[2]
MODEL_DIRECTORY = ROOT / "backend" / "storage" / "models" / "hate_speech_v7"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v7_selective_development"
)
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"
CONFIG_PATH = MODEL_DIRECTORY / "development_config.json"
CALIBRATION_PATH = MODEL_DIRECTORY / "calibration.json"

# This is a new candidate. These values are defined before V7 is evaluated.
V7_SEED = 20260812
V7_EPOCHS = 4
V7_LEARNING_RATE = 1.5e-5

# V7 is permitted to output only Hate Speech & Discrimination.
# Abusive Words remains owned by the independently validated RC2 component.
MINIMUM_SELECTIVE_PRECISION = 0.90
MINIMUM_SELECTIVE_RECALL = 0.30
MINIMUM_SELECTIVE_SPECIFICITY = 0.97
MINIMUM_SOURCE_PRECISION = 0.85
MINIMUM_SOURCE_RECALL = 0.20
MINIMUM_SOURCE_SPECIFICITY = 0.95
MINIMUM_ACCEPTED = 200


def v7_gate_checks(policy: dict[str, Any]) -> dict[str, bool]:
    if not policy.get("enabled"):
        return {"calibrated_policy_enabled": False}
    civil = policy["source_metrics"]["Civil Comments"]
    hatexplain = policy["source_metrics"]["HateXplain"]
    return {
        "calibrated_policy_enabled": True,
        "overall_precision": policy["precision"] >= MINIMUM_SELECTIVE_PRECISION,
        "overall_recall": policy["recall"] >= MINIMUM_SELECTIVE_RECALL,
        "overall_specificity": (
            policy["specificity"] >= MINIMUM_SELECTIVE_SPECIFICITY
        ),
        "accepted_volume": policy["accepted"] >= MINIMUM_ACCEPTED,
        "civil_precision": civil["precision"] >= MINIMUM_SOURCE_PRECISION,
        "civil_recall": civil["recall"] >= MINIMUM_SOURCE_RECALL,
        "civil_specificity": (
            civil["specificity"] >= MINIMUM_SOURCE_SPECIFICITY
        ),
        "hatexplain_precision": (
            hatexplain["precision"] >= MINIMUM_SOURCE_PRECISION
        ),
        "hatexplain_recall": hatexplain["recall"] >= MINIMUM_SOURCE_RECALL,
        "hatexplain_specificity": (
            hatexplain["specificity"] >= MINIMUM_SOURCE_SPECIFICITY
        ),
    }


def print_policy(policy: dict[str, Any]) -> None:
    if not policy.get("enabled"):
        print("Enabled: False")
        print(f"Reason: {policy.get('reason', 'Calibration failed.')}")
        closest = policy.get("closest_candidate")
        if closest:
            print("Closest rejected calibration candidate:")
            print(f"  Threshold: {closest['probability_threshold']:.2f}")
            print(f"  Margin: {closest['minimum_margin']:.2f}")
            print(f"  Precision: {closest['precision'] * 100:.2f}%")
            print(f"  Recall: {closest['recall'] * 100:.2f}%")
            print(f"  Specificity: {closest['specificity'] * 100:.2f}%")
        return

    print("Enabled: True")
    print(f"Probability threshold: {policy['probability_threshold']:.2f}")
    print(f"Minimum margin: {policy['minimum_margin']:.2f}")
    print(f"Accepted: {policy['accepted']:,}")
    print(f"Precision: {policy['precision'] * 100:.2f}%")
    print(f"Recall: {policy['recall'] * 100:.2f}%")
    print(f"Specificity: {policy['specificity'] * 100:.2f}%")
    for source, metrics in policy["source_metrics"].items():
        print(
            f"  {source}: precision {metrics['precision'] * 100:.2f}% | "
            f"recall {metrics['recall'] * 100:.2f}% | "
            f"specificity {metrics['specificity'] * 100:.2f}% | "
            f"accepted {metrics['accepted']:,}"
        )


def main() -> None:
    # Override only development hyperparameters before any V7 data is loaded.
    v6.SEED = V7_SEED
    v6.EPOCHS = V7_EPOCHS
    v6.LEARNING_RATE = V7_LEARNING_RATE
    v6.set_seed()

    train_rows, validation_rows = v6.load_development_data()
    print("HATE SPEECH V7 SELECTIVE DEVELOPMENT")
    print("=" * 60)
    print(f"Training records: {len(train_rows):,}")
    print(f"Validation records: {len(validation_rows):,}")
    print(f"Training label counts: {dict(Counter(row['label'] for row in train_rows))}")
    print("Reserved test splits opened: False")
    print("Permitted active output: Hate Speech & Discrimination only")
    print()

    (
        model,
        tokenizer,
        probabilities,
        truth,
        history,
        device_type,
    ) = v6.train_model(train_rows, validation_rows)

    raw_metrics = v6.multiclass_metrics(probabilities, truth)
    sources = np.array([str(row["source"]) for row in validation_rows])
    policy = v6.calibrate_hate_output(probabilities, truth, sources)
    checks = v7_gate_checks(policy)
    passed = bool(checks and all(checks.values()))

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(MODEL_DIRECTORY, safe_serialization=True)
    tokenizer.save_pretrained(MODEL_DIRECTORY)

    gate_contract = {
        "minimum_selective_precision": MINIMUM_SELECTIVE_PRECISION,
        "minimum_selective_recall": MINIMUM_SELECTIVE_RECALL,
        "minimum_selective_specificity": MINIMUM_SELECTIVE_SPECIFICITY,
        "minimum_source_precision": MINIMUM_SOURCE_PRECISION,
        "minimum_source_recall": MINIMUM_SOURCE_RECALL,
        "minimum_source_specificity": MINIMUM_SOURCE_SPECIFICITY,
        "minimum_accepted": MINIMUM_ACCEPTED,
    }
    report = {
        "candidate": "hate-speech-v7-selective-development",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "base_model": v6.BASE_MODEL_NAME,
        "base_model_revision": v6.BASE_MODEL_REVISION,
        "base_model_license": v6.BASE_MODEL_LICENSE,
        "device": device_type,
        "training_records": len(train_rows),
        "validation_records": len(validation_rows),
        "training_label_counts": dict(Counter(row["label"] for row in train_rows)),
        "training_source_counts": dict(Counter(row["source"] for row in train_rows)),
        "training_parameters": {
            "seed": V7_SEED,
            "max_length": v6.MAX_LENGTH,
            "batch_size": v6.BATCH_SIZE,
            "epochs": V7_EPOCHS,
            "learning_rate": V7_LEARNING_RATE,
            "weight_decay": v6.WEIGHT_DECAY,
            "warmup_ratio": v6.WARMUP_RATIO,
        },
        "training_history": history,
        "raw_validation_metrics_for_diagnostics_only": raw_metrics,
        "hate_output_policy": policy,
        "v7_gate_contract": gate_contract,
        "v7_gate_checks": checks,
        "passed_development_gate": passed,
        "permitted_active_output": "Hate Speech & Discrimination",
        "abusive_words_behavior": "No override; validated RC2 retains ownership",
        "safe_or_other_behavior": "No allow override",
        "uncertain_behavior": "No override and refer to human review when applicable",
        "test_splits_opened": False,
        "raw_text_stored_in_report": False,
        "record_level_predictions_stored": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    compact_config = {
        "candidate": report["candidate"],
        "base_model": report["base_model"],
        "base_model_revision": report["base_model_revision"],
        "base_model_license": report["base_model_license"],
        "label_to_id": v6.LABEL_TO_ID,
        "hate_output_policy": policy,
        "v7_gate_contract": gate_contract,
        "v7_gate_checks": checks,
        "passed_development_gate": passed,
        "permitted_active_output": report["permitted_active_output"],
        "test_splits_opened": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    CONFIG_PATH.write_text(
        json.dumps(compact_config, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    CALIBRATION_PATH.write_text(
        json.dumps(
            {
                "candidate": report["candidate"],
                "hate_output_policy": policy,
                "v7_gate_contract": gate_contract,
                "v7_gate_checks": checks,
                "passed_development_gate": passed,
                "test_splits_opened": False,
                "automatic_enforcement_allowed": False,
                "connected_to_live_moderation": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH V7 SELECTIVE DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Raw diagnostic accuracy: {raw_metrics['accuracy'] * 100:.2f}%")
    print(f"Raw diagnostic macro F1: {raw_metrics['macro_f1'] * 100:.2f}%")
    print()
    print("SELECTIVE HATE OUTPUT")
    print("-" * 60)
    print_policy(policy)
    print()
    print("V7 GATE CHECKS")
    print("-" * 60)
    for name, value in checks.items():
        print(f"{name}: {value}")
    print()
    print(f"Passed V7 development gate: {passed}")
    print(f"Model artifact: {MODEL_DIRECTORY}")
    print(f"Report: {REPORT_PATH}")
    print("Neither reserved test split was opened.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
