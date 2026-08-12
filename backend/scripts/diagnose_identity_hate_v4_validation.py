from __future__ import annotations

import json
from datetime import datetime, timezone

import numpy as np

from scripts.benchmark_identity_hate_v4_validation import (
    MINIMUM_ACCEPTED,
    MINIMUM_CIVIL_ACCEPTED,
    MINIMUM_HATEXPLAIN_ACCEPTED,
    REPORT_DIRECTORY,
    TARGET_CIVIL_PRECISION,
    TARGET_HATEXPLAIN_PRECISION,
    TARGET_OVERALL_PRECISION,
    TARGET_OVERALL_SPECIFICITY,
    TARGET_SOURCE_SPECIFICITY,
    MINIMUM_RECALL,
    evaluate_threshold,
    load_validation_records,
    run_inference,
)


DIAGNOSTIC_PATH = REPORT_DIRECTORY / "failure_diagnostic.json"


def f1_score(precision: float, recall: float) -> float:
    if precision + recall == 0:
        return 0.0
    return 2.0 * precision * recall / (precision + recall)


def gate_checks(result: dict) -> dict[str, bool]:
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


def normalized_shortfall(value: float, target: float) -> float:
    if target <= 0 or value >= target:
        return 0.0
    return (target - value) / target


def gate_shortfall(result: dict) -> float:
    civil = result["source_metrics"]["Civil Comments"]
    hatexplain = result["source_metrics"]["HateXplain"]
    return sum(
        (
            normalized_shortfall(result["precision"], TARGET_OVERALL_PRECISION),
            normalized_shortfall(
                result["specificity"],
                TARGET_OVERALL_SPECIFICITY,
            ),
            normalized_shortfall(result["recall"], MINIMUM_RECALL),
            normalized_shortfall(result["accepted"], MINIMUM_ACCEPTED),
            normalized_shortfall(civil["precision"], TARGET_CIVIL_PRECISION),
            normalized_shortfall(
                civil["specificity"],
                TARGET_SOURCE_SPECIFICITY,
            ),
            normalized_shortfall(civil["accepted"], MINIMUM_CIVIL_ACCEPTED),
            normalized_shortfall(
                hatexplain["precision"],
                TARGET_HATEXPLAIN_PRECISION,
            ),
            normalized_shortfall(
                hatexplain["specificity"],
                TARGET_SOURCE_SPECIFICITY,
            ),
            normalized_shortfall(
                hatexplain["accepted"],
                MINIMUM_HATEXPLAIN_ACCEPTED,
            ),
        )
    )


def summarize(result: dict) -> dict:
    checks = gate_checks(result)
    return {
        **result,
        "f1": round(f1_score(result["precision"], result["recall"]), 4),
        "gates_passed": sum(checks.values()),
        "gates_total": len(checks),
        "failed_gates": [name for name, passed in checks.items() if not passed],
        "gate_checks": checks,
        "normalized_gate_shortfall": round(gate_shortfall(result), 6),
    }


def print_candidate(title: str, result: dict) -> None:
    print(title)
    print("-" * 60)
    print(f"Threshold: {result['threshold']:.3f}")
    print(f"Accepted: {result['accepted']:,}")
    print(f"Precision: {result['precision'] * 100:.2f}%")
    print(f"Recall: {result['recall'] * 100:.2f}%")
    print(f"Specificity: {result['specificity'] * 100:.2f}%")
    print(f"F1: {result['f1'] * 100:.2f}%")
    print(f"Gates passed: {result['gates_passed']}/{result['gates_total']}")
    print(f"Failed gates: {', '.join(result['failed_gates']) or 'None'}")
    for source, metrics in result["source_metrics"].items():
        print(
            f"  {source}: accepted {metrics['accepted']:,} | "
            f"precision {metrics['precision'] * 100:.2f}% | "
            f"recall {metrics['recall'] * 100:.2f}% | "
            f"specificity {metrics['specificity'] * 100:.2f}%"
        )


def main() -> None:
    records = load_validation_records()
    texts = [str(record["text"]) for record in records]
    truth = np.array([bool(record["is_hate"]) for record in records])
    sources = np.array([str(record["source"]) for record in records])

    scores, _ = run_inference(texts)
    thresholds = np.unique(
        np.concatenate(
            (
                np.arange(0.001, 0.050, 0.001),
                np.arange(0.05, 0.991, 0.01),
            )
        )
    )
    candidates = [
        summarize(evaluate_threshold(threshold, scores, truth, sources))
        for threshold in thresholds
    ]

    closest = min(
        candidates,
        key=lambda item: (
            item["normalized_gate_shortfall"],
            -item["gates_passed"],
            -item["recall"],
            -item["precision"],
        ),
    )
    best_f1 = max(
        candidates,
        key=lambda item: (item["f1"], item["precision"], item["recall"]),
    )
    best_precision_with_volume = max(
        (
            item
            for item in candidates
            if item["accepted"] >= MINIMUM_ACCEPTED
        ),
        key=lambda item: (item["precision"], item["recall"]),
    )

    report = {
        "candidate": "hate-speech-v4-identity-hate-validation",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "validation_records": len(records),
        "thresholds_evaluated": len(candidates),
        "closest_to_all_gates": closest,
        "best_f1": best_f1,
        "best_precision_with_minimum_volume": best_precision_with_volume,
        "test_splits_opened": False,
        "raw_validation_text_stored": False,
        "record_level_predictions_stored": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    DIAGNOSTIC_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("HATE SPEECH V4 FAILURE DIAGNOSTIC")
    print("=" * 60)
    print_candidate("CLOSEST CANDIDATE TO ALL SAFETY GATES", closest)
    print()
    print_candidate("BEST F1 CANDIDATE", best_f1)
    print()
    print_candidate(
        "BEST PRECISION WITH MINIMUM ACCEPTED VOLUME",
        best_precision_with_volume,
    )
    print()
    print(f"Diagnostic: {DIAGNOSTIC_PATH}")
    print("Neither test split was opened.")
    print("No raw text or record-level predictions were stored.")
    print("The candidate remains disconnected from live moderation.")


if __name__ == "__main__":
    main()
