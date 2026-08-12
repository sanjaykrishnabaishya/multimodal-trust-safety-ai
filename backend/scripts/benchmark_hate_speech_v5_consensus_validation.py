from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from scripts.benchmark_identity_hate_v4_validation import (
    MINIMUM_ACCEPTED,
    MINIMUM_CIVIL_ACCEPTED,
    MINIMUM_HATEXPLAIN_ACCEPTED,
    MINIMUM_RECALL,
    TARGET_CIVIL_PRECISION,
    TARGET_HATEXPLAIN_PRECISION,
    TARGET_OVERALL_PRECISION,
    TARGET_OVERALL_SPECIFICITY,
    TARGET_SOURCE_SPECIFICITY,
    load_validation_records,
    run_inference as run_identity_hate_inference,
    source_metrics,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "hate_speech" / "v5_consensus_validation"
)
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"
CALIBRATION_PATH = REPORT_DIRECTORY / "calibration.json"

HATE_MODEL_NAME = "Hate-speech-CNERG/dehatebert-mono-english"
HATE_MODEL_REVISION = "e9a75bdbd4ba695cafe7e0378504e8ad3bc1bf54"
HATE_MODEL_LICENSE = "Apache-2.0"
HATE_LABEL = "HATE"
BATCH_SIZE = 16
MAX_LENGTH = 128


def find_label_index(model: Any, required_label: str) -> int:
    labels = {
        int(index): str(label).strip().upper()
        for index, label in model.config.id2label.items()
    }
    for index, label in labels.items():
        if label == required_label.upper():
            return index
    raise RuntimeError(
        f"The pinned hate model does not expose {required_label!r}. "
        f"Available labels: {labels}"
    )


def run_hate_model_inference(texts: list[str]) -> tuple[np.ndarray, dict[int, str]]:
    print("Loading the pinned hate-specific validation candidate...")
    tokenizer = AutoTokenizer.from_pretrained(
        HATE_MODEL_NAME,
        revision=HATE_MODEL_REVISION,
        use_fast=True,
    )
    model = AutoModelForSequenceClassification.from_pretrained(
        HATE_MODEL_NAME,
        revision=HATE_MODEL_REVISION,
    )
    model.eval()
    model.to("cpu")
    hate_index = find_label_index(model, HATE_LABEL)
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
            probabilities = torch.softmax(logits, dim=-1)[:, hate_index]
            scores.append(probabilities.detach().cpu().numpy())
            completed = min(start + len(batch), len(texts))
            if completed % 160 == 0 or completed == len(texts):
                print(f"Processed {completed:,}/{len(texts):,} hate-model records...")

    return np.concatenate(scores), labels


def evaluate_selection(
    selected: np.ndarray,
    truth: np.ndarray,
    sources: np.ndarray,
    policy: dict[str, Any],
) -> dict[str, Any]:
    accepted = int(selected.sum())
    true_positives = int((selected & truth).sum())
    false_positives = int((selected & ~truth).sum())
    positives = int(truth.sum())
    negatives = int((~truth).sum())
    precision = true_positives / accepted if accepted else 0.0
    recall = true_positives / positives if positives else 0.0
    specificity = 1.0 - (
        false_positives / negatives if negatives else 0.0
    )
    return {
        **policy,
        "accepted": accepted,
        "true_positives": true_positives,
        "false_positives": false_positives,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "source_metrics": {
            source: source_metrics(selected, truth, sources == source)
            for source in ("Civil Comments", "HateXplain")
        },
    }


def gate_checks(result: dict[str, Any]) -> dict[str, bool]:
    civil = result["source_metrics"]["Civil Comments"]
    hatexplain = result["source_metrics"]["HateXplain"]
    return {
        "overall_precision": result["precision"] >= TARGET_OVERALL_PRECISION,
        "overall_specificity": (
            result["specificity"] >= TARGET_OVERALL_SPECIFICITY
        ),
        "overall_recall": result["recall"] >= MINIMUM_RECALL,
        "accepted_volume": result["accepted"] >= MINIMUM_ACCEPTED,
        "civil_precision": civil["precision"] >= TARGET_CIVIL_PRECISION,
        "civil_specificity": (
            civil["specificity"] >= TARGET_SOURCE_SPECIFICITY
        ),
        "civil_volume": civil["accepted"] >= MINIMUM_CIVIL_ACCEPTED,
        "hatexplain_precision": (
            hatexplain["precision"] >= TARGET_HATEXPLAIN_PRECISION
        ),
        "hatexplain_specificity": (
            hatexplain["specificity"] >= TARGET_SOURCE_SPECIFICITY
        ),
        "hatexplain_volume": (
            hatexplain["accepted"] >= MINIMUM_HATEXPLAIN_ACCEPTED
        ),
    }


def add_diagnostics(result: dict[str, Any]) -> dict[str, Any]:
    checks = gate_checks(result)
    precision = float(result["precision"])
    recall = float(result["recall"])
    f1 = (
        2.0 * precision * recall / (precision + recall)
        if precision + recall
        else 0.0
    )
    return {
        **result,
        "f1": round(f1, 4),
        "gates_passed": sum(checks.values()),
        "gates_total": len(checks),
        "failed_gates": [name for name, passed in checks.items() if not passed],
    }


def passes_all_gates(result: dict[str, Any]) -> bool:
    return all(gate_checks(result).values())


def build_candidates(
    identity_scores: np.ndarray,
    hate_scores: np.ndarray,
    truth: np.ndarray,
    sources: np.ndarray,
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    identity_thresholds = np.arange(0.10, 0.961, 0.05)
    hate_thresholds = np.arange(0.10, 0.961, 0.05)

    # Strict agreement: both independent signals must pass.
    for identity_threshold in identity_thresholds:
        for hate_threshold in hate_thresholds:
            selected = (
                (identity_scores >= identity_threshold)
                & (hate_scores >= hate_threshold)
            )
            candidates.append(
                add_diagnostics(
                    evaluate_selection(
                        selected,
                        truth,
                        sources,
                        {
                            "method": "strict_consensus",
                            "identity_hate_threshold": round(
                                float(identity_threshold), 2
                            ),
                            "hate_model_threshold": round(
                                float(hate_threshold), 2
                            ),
                        },
                    )
                )
            )

    # Weighted consensus is evaluated separately. It can pass only through the
    # same source-specific precision, specificity and volume gates.
    for identity_weight in np.arange(0.30, 0.71, 0.10):
        hate_weight = 1.0 - identity_weight
        score = identity_weight * identity_scores + hate_weight * hate_scores
        for threshold in np.arange(0.20, 0.961, 0.02):
            selected = score >= threshold
            candidates.append(
                add_diagnostics(
                    evaluate_selection(
                        selected,
                        truth,
                        sources,
                        {
                            "method": "weighted_consensus",
                            "identity_hate_weight": round(
                                float(identity_weight), 2
                            ),
                            "hate_model_weight": round(float(hate_weight), 2),
                            "combined_threshold": round(float(threshold), 2),
                        },
                    )
                )
            )
    return candidates


def select_policy(candidates: list[dict[str, Any]]) -> dict[str, Any]:
    passing = [candidate for candidate in candidates if passes_all_gates(candidate)]
    if passing:
        return {
            "enabled": True,
            **max(
                passing,
                key=lambda item: (
                    item["recall"],
                    item["accepted"],
                    item["precision"],
                    item["specificity"],
                ),
            ),
        }

    closest = max(
        candidates,
        key=lambda item: (
            item["gates_passed"],
            item["precision"],
            item["recall"],
            item["accepted"],
        ),
    )
    return {
        "enabled": False,
        "reason": "No consensus policy satisfied every validation gate.",
        "closest_candidate": closest,
    }


def print_metrics(metrics: dict[str, Any]) -> None:
    print(f"Method: {metrics['method']}")
    if metrics["method"] == "strict_consensus":
        print(
            "Identity-hate threshold: "
            f"{metrics['identity_hate_threshold']:.2f}"
        )
        print(f"Hate-model threshold: {metrics['hate_model_threshold']:.2f}")
    else:
        print(f"Identity-hate weight: {metrics['identity_hate_weight']:.2f}")
        print(f"Hate-model weight: {metrics['hate_model_weight']:.2f}")
        print(f"Combined threshold: {metrics['combined_threshold']:.2f}")
    print(f"Accepted: {metrics['accepted']:,}")
    print(f"Precision: {metrics['precision'] * 100:.2f}%")
    print(f"Recall: {metrics['recall'] * 100:.2f}%")
    print(f"Specificity: {metrics['specificity'] * 100:.2f}%")
    print(f"F1: {metrics['f1'] * 100:.2f}%")
    print(f"Gates passed: {metrics['gates_passed']}/{metrics['gates_total']}")
    print(f"Failed gates: {', '.join(metrics['failed_gates']) or 'None'}")
    for source, source_result in metrics["source_metrics"].items():
        print(
            f"  {source}: accepted {source_result['accepted']:,} | "
            f"precision {source_result['precision'] * 100:.2f}% | "
            f"recall {source_result['recall'] * 100:.2f}% | "
            f"specificity {source_result['specificity'] * 100:.2f}%"
        )


def main() -> None:
    records = load_validation_records()
    texts = [str(record["text"]) for record in records]
    truth = np.array([bool(record["is_hate"]) for record in records])
    sources = np.array([str(record["source"]) for record in records])

    identity_scores, identity_labels = run_identity_hate_inference(texts)
    hate_scores, hate_labels = run_hate_model_inference(texts)
    candidates = build_candidates(identity_scores, hate_scores, truth, sources)
    policy = select_policy(candidates)
    passed = bool(policy["enabled"])

    report = {
        "candidate": "hate-speech-v5-consensus-validation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_records": len(records),
        "identity_model": {
            "name": "unitary/toxic-bert",
            "revision": "b21edc82a6515081ad01388bba038721352bc50d",
            "license": "Apache-2.0",
            "active_label": "identity_hate",
            "labels": identity_labels,
        },
        "hate_model": {
            "name": HATE_MODEL_NAME,
            "revision": HATE_MODEL_REVISION,
            "license": HATE_MODEL_LICENSE,
            "active_label": HATE_LABEL,
            "labels": hate_labels,
        },
        "policy": policy,
        "candidates_evaluated": len(candidates),
        "passed_validation_gate": passed,
        "test_splits_opened": False,
        "raw_validation_text_stored": False,
        "record_level_predictions_stored": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "active_output_category": "Hate Speech & Discrimination",
        "abusive_words_behavior": "No override unless the V5 hate policy passes",
        "safe_behavior": "No allow override",
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
                "identity_model": report["identity_model"],
                "hate_model": report["hate_model"],
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
    print("HATE SPEECH V5 CONSENSUS VALIDATION")
    print("=" * 60)
    print(f"Validation records: {len(records):,}")
    print(f"Enabled: {policy['enabled']}")
    if passed:
        print_metrics(policy)
    else:
        print(f"Reason: {policy['reason']}")
        print()
        print("CLOSEST CANDIDATE")
        print("-" * 60)
        print_metrics(policy["closest_candidate"])
    print()
    print(f"Passed validation gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print("Neither test split was opened.")
    print("No raw text or record-level predictions were stored.")
    print("This candidate is not connected to live moderation.")


if __name__ == "__main__":
    main()
