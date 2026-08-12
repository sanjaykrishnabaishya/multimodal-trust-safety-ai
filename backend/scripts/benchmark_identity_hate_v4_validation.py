from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer


ROOT = Path(__file__).resolve().parents[2]
CIVIL_VALIDATION = (
    ROOT / "datasets" / "public" / "civil_comments_hate_rc2" / "validation.csv"
)
HATEXPLAIN_VALIDATION = (
    ROOT / "datasets" / "public" / "hatexplain" / "validation.csv"
)
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v4_identity_hate_validation"
)
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"
CALIBRATION_PATH = REPORT_DIRECTORY / "calibration.json"

MODEL_NAME = "unitary/toxic-bert"
MODEL_REVISION = "b21edc82a6515081ad01388bba038721352bc50d"
MODEL_LICENSE = "Apache-2.0"
ACTIVE_MODEL_LABEL = "identity_hate"
BATCH_SIZE = 16
MAX_LENGTH = 256

TARGET_OVERALL_PRECISION = 0.90
TARGET_CIVIL_PRECISION = 0.85
TARGET_HATEXPLAIN_PRECISION = 0.85
TARGET_OVERALL_SPECIFICITY = 0.95
TARGET_SOURCE_SPECIFICITY = 0.90
MINIMUM_RECALL = 0.15
MINIMUM_ACCEPTED = 35
MINIMUM_CIVIL_ACCEPTED = 5
MINIMUM_HATEXPLAIN_ACCEPTED = 25

HATEXPLAIN_MAPPING = {
    "Hate Speech & Discrimination": True,
    "Abusive Words": False,
    "Normal/Ignore": False,
}


def load_validation_records() -> list[dict[str, Any]]:
    for path in (CIVIL_VALIDATION, HATEXPLAIN_VALIDATION):
        if not path.is_file():
            raise FileNotFoundError(f"Validation split was not found: {path}")

    records: list[dict[str, Any]] = []

    with CIVIL_VALIDATION.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            label = str(row.get("label", "")).strip()
            if not text or label not in {
                "hate_speech",
                "abusive_words",
                "safe_or_other",
            }:
                continue
            records.append(
                {
                    "text": text,
                    "is_hate": label == "hate_speech",
                    "source": "Civil Comments",
                }
            )

    with HATEXPLAIN_VALIDATION.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            category = str(row.get("category", "")).strip()
            if not text or category not in HATEXPLAIN_MAPPING:
                continue
            records.append(
                {
                    "text": text,
                    "is_hate": HATEXPLAIN_MAPPING[category],
                    "source": "HateXplain",
                }
            )

    if not records:
        raise RuntimeError("No validation records were loaded.")
    return records


def label_index(model: Any, required_label: str) -> int:
    labels = {
        int(index): str(label).strip().lower()
        for index, label in model.config.id2label.items()
    }
    for index, label in labels.items():
        if label == required_label.lower():
            return index
    raise RuntimeError(
        f"The pinned model does not expose the required label {required_label!r}. "
        f"Available labels: {labels}"
    )


def run_inference(texts: list[str]) -> tuple[np.ndarray, dict[int, str]]:
    print("Loading the pinned identity-hate validation candidate...")
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        use_fast=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        MODEL_NAME,
        revision=MODEL_REVISION,
        use_safetensors=True,
    )
    model.eval()
    model.to("cpu")

    identity_index = label_index(model, ACTIVE_MODEL_LABEL)
    labels = {
        int(index): str(label)
        for index, label in model.config.id2label.items()
    }
    scores: list[np.ndarray] = []

    with torch.inference_mode():
        for start in range(0, len(texts), BATCH_SIZE):
            batch = texts[start : start + BATCH_SIZE]
            encoded = tokenizer(
                batch,
                padding=True,
                truncation=True,
                max_length=MAX_LENGTH,
                return_tensors="pt",
            )
            logits = model(**encoded).logits
            probability = torch.sigmoid(logits)[:, identity_index]
            scores.append(probability.detach().cpu().numpy())
            completed = min(start + len(batch), len(texts))
            if completed % 160 == 0 or completed == len(texts):
                print(f"Processed {completed:,}/{len(texts):,} validation records...")

    return np.concatenate(scores), labels


def source_metrics(
    selected: np.ndarray,
    truth: np.ndarray,
    source_mask: np.ndarray,
) -> dict[str, float | int]:
    accepted = selected & source_mask
    accepted_count = int(accepted.sum())
    true_positives = int((accepted & truth).sum())
    false_positives = int((accepted & ~truth).sum())
    positives = int((source_mask & truth).sum())
    negatives = int((source_mask & ~truth).sum())
    false_positive_rate = false_positives / negatives if negatives else 0.0
    return {
        "records": int(source_mask.sum()),
        "positive_records": positives,
        "negative_records": negatives,
        "accepted": accepted_count,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "precision": round(
            true_positives / accepted_count if accepted_count else 0.0,
            4,
        ),
        "recall": round(true_positives / positives if positives else 0.0, 4),
        "specificity": round(1.0 - false_positive_rate, 4),
    }


def evaluate_threshold(
    threshold: float,
    scores: np.ndarray,
    truth: np.ndarray,
    sources: np.ndarray,
) -> dict[str, Any]:
    selected = scores >= threshold
    accepted = int(selected.sum())
    true_positives = int((selected & truth).sum())
    false_positives = int((selected & ~truth).sum())
    positives = int(truth.sum())
    negatives = int((~truth).sum())

    result: dict[str, Any] = {
        "threshold": round(float(threshold), 4),
        "accepted": accepted,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "precision": round(
            true_positives / accepted if accepted else 0.0,
            4,
        ),
        "recall": round(true_positives / positives if positives else 0.0, 4),
        "specificity": round(
            1.0 - (false_positives / negatives if negatives else 0.0),
            4,
        ),
        "source_metrics": {},
    }
    for source in ("Civil Comments", "HateXplain"):
        result["source_metrics"][source] = source_metrics(
            selected,
            truth,
            sources == source,
        )
    return result


def passes_gates(result: dict[str, Any]) -> bool:
    civil = result["source_metrics"]["Civil Comments"]
    hatexplain = result["source_metrics"]["HateXplain"]
    return bool(
        result["precision"] >= TARGET_OVERALL_PRECISION
        and result["specificity"] >= TARGET_OVERALL_SPECIFICITY
        and result["recall"] >= MINIMUM_RECALL
        and result["accepted"] >= MINIMUM_ACCEPTED
        and civil["accepted"] >= MINIMUM_CIVIL_ACCEPTED
        and civil["precision"] >= TARGET_CIVIL_PRECISION
        and civil["specificity"] >= TARGET_SOURCE_SPECIFICITY
        and hatexplain["accepted"] >= MINIMUM_HATEXPLAIN_ACCEPTED
        and hatexplain["precision"] >= TARGET_HATEXPLAIN_PRECISION
        and hatexplain["specificity"] >= TARGET_SOURCE_SPECIFICITY
    )


def choose_policy(
    scores: np.ndarray,
    truth: np.ndarray,
    sources: np.ndarray,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates = [
        evaluate_threshold(threshold, scores, truth, sources)
        for threshold in np.arange(0.05, 0.991, 0.01)
    ]
    passing = [candidate for candidate in candidates if passes_gates(candidate)]
    if not passing:
        return (
            {
                "enabled": False,
                "method": "none",
                "reason": "No identity_hate threshold satisfied every validation gate.",
            },
            candidates,
        )

    # Prefer useful recall, then coverage, while never weakening precision gates.
    best = max(
        passing,
        key=lambda item: (
            item["recall"],
            item["accepted"],
            item["precision"],
            item["specificity"],
        ),
    )
    return {"enabled": True, "method": "identity_hate_threshold", **best}, candidates


def main() -> None:
    records = load_validation_records()
    texts = [str(record["text"]) for record in records]
    truth = np.array([bool(record["is_hate"]) for record in records])
    sources = np.array([str(record["source"]) for record in records])

    scores, model_labels = run_inference(texts)
    policy, candidates = choose_policy(scores, truth, sources)
    passed = bool(policy["enabled"])

    report = {
        "candidate": "hate-speech-v4-identity-hate-validation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_name": MODEL_NAME,
        "model_revision": MODEL_REVISION,
        "model_license": MODEL_LICENSE,
        "model_labels": model_labels,
        "active_model_label": ACTIVE_MODEL_LABEL,
        "records": len(records),
        "source_record_counts": {
            source: int((sources == source).sum())
            for source in ("Civil Comments", "HateXplain")
        },
        "positive_records": int(truth.sum()),
        "negative_records": int((~truth).sum()),
        "policy": policy,
        "gates": {
            "minimum_overall_precision": TARGET_OVERALL_PRECISION,
            "minimum_civil_precision": TARGET_CIVIL_PRECISION,
            "minimum_hatexplain_precision": TARGET_HATEXPLAIN_PRECISION,
            "minimum_overall_specificity": TARGET_OVERALL_SPECIFICITY,
            "minimum_source_specificity": TARGET_SOURCE_SPECIFICITY,
            "minimum_recall": MINIMUM_RECALL,
            "minimum_accepted": MINIMUM_ACCEPTED,
            "minimum_civil_accepted": MINIMUM_CIVIL_ACCEPTED,
            "minimum_hatexplain_accepted": MINIMUM_HATEXPLAIN_ACCEPTED,
        },
        "passed_validation_gate": passed,
        "test_splits_opened": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "active_output_category": "Hate Speech & Discrimination",
        "abusive_words_behavior": "No hate override unless identity_hate passes every gate",
        "safe_behavior": "No allow override",
        "raw_validation_text_stored": False,
        "thresholds_evaluated": len(candidates),
    }

    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    CALIBRATION_PATH.write_text(
        json.dumps(
            {
                "candidate": report["candidate"],
                "model_name": MODEL_NAME,
                "model_revision": MODEL_REVISION,
                "model_license": MODEL_LICENSE,
                "active_model_label": ACTIVE_MODEL_LABEL,
                "policy": policy,
                "passed_validation_gate": passed,
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
    print("HATE SPEECH V4 IDENTITY-HATE VALIDATION")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print(f"Pinned revision: {MODEL_REVISION}")
    print(f"Licence: {MODEL_LICENSE}")
    print(f"Validation records: {len(records):,}")
    print(f"Enabled: {policy['enabled']}")
    print(f"Method: {policy['method']}")
    if policy["enabled"]:
        print(f"Threshold: {policy['threshold']:.2f}")
        print(f"Accepted: {policy['accepted']:,}")
        print(f"Precision: {policy['precision'] * 100:.2f}%")
        print(f"Recall: {policy['recall'] * 100:.2f}%")
        print(f"Specificity: {policy['specificity'] * 100:.2f}%")
        print()
        print("SOURCE RESULTS")
        print("-" * 60)
        for source, metrics in policy["source_metrics"].items():
            print(source)
            print(f"  Accepted: {metrics['accepted']:,}")
            print(f"  Precision: {metrics['precision'] * 100:.2f}%")
            print(f"  Recall: {metrics['recall'] * 100:.2f}%")
            print(f"  Specificity: {metrics['specificity'] * 100:.2f}%")
    else:
        print(f"Reason: {policy['reason']}")
    print()
    print(f"Passed validation gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print("Neither test split was opened.")
    print("No validation text or record-level predictions were stored.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
