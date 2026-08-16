from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.dangerous_content_v5_rc4_service import (
    analyze_dangerous_content_v5_rc4,
)


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
DATASET_PATH = (
    ROOT_DIRECTORY
    / "datasets"
    / "development"
    / "dangerous_content_v5_rc4"
    / "development.csv"
)
REPORT_PATH = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v5_rc4_policy_recovery_development"
    / "path_diagnostic.json"
)
DANGEROUS_CATEGORY = "Dangerous Content"


def main() -> None:
    if not DATASET_PATH.is_file():
        raise FileNotFoundError(
            "Run the V5 RC4 development evaluation before this diagnostic."
        )

    with DATASET_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))

    print("DANGEROUS CONTENT V5 RC4 DEVELOPMENT PATH DIAGNOSTIC")
    print("=" * 60)
    print("No raw text is printed or stored. No holdout is opened.")
    print()

    group_summary: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "records": 0,
            "correct": 0,
            "false_positives": 0,
            "false_negatives": 0,
            "accept_path_counts": Counter(),
            "mismatch_path_counts": Counter(),
        }
    )
    mismatch_records: list[dict[str, Any]] = []

    for row in rows:
        expected = str(row["expected_dangerous"]).strip().lower() == "true"
        result = analyze_dangerous_content_v5_rc4(
            row["text"],
            existing_category=row["existing_category"],
        )
        predicted = result.get("category") == DANGEROUS_CATEGORY
        correct = predicted == expected
        group = row["group"]
        summary = group_summary[group]
        summary["records"] += 1
        summary["correct"] += int(correct)

        path = str(result.get("dangerous_content_v5_rc4_status", "unknown"))
        if predicted:
            summary["accept_path_counts"][path] += 1
        if correct:
            continue

        mismatch_type = "false_negative" if expected else "false_positive"
        summary["false_negatives" if expected else "false_positives"] += 1
        summary["mismatch_path_counts"][path] += 1
        evidence = result.get("direct_policy_evidence") or {}
        mismatch_records.append(
            {
                "record_id": row["record_id"],
                "group": group,
                "mismatch_type": mismatch_type,
                "v5_status": path,
                "rc3_status": result.get("status"),
                "direct_recovery_used": bool(
                    result.get("direct_advocacy_recovery_used", False)
                ),
                "boundary_probability": round(
                    float(result.get("boundary_probability", 0.0)), 4
                ),
                "hazard_probability": round(
                    float(result.get("hazard_probability", 0.0)), 4
                ),
                "dangerous_context_probability": round(
                    float(result.get("dangerous_context_probability", 0.0)), 4
                ),
                "advocacy_signal_count": int(
                    evidence.get("advocacy_signal_count", 0)
                ),
                "action_signal_count": int(evidence.get("action_signal_count", 0)),
                "audience_signal_count": int(
                    evidence.get("audience_signal_count", 0)
                ),
                "harm_signal_count": int(evidence.get("harm_signal_count", 0)),
                "hazard_domain_signal_count": int(
                    evidence.get("hazard_domain_signal_count", 0)
                ),
                "unsafe_framing_signal_count": int(
                    evidence.get("unsafe_framing_signal_count", 0)
                ),
                "safe_context_signal_count": int(
                    evidence.get("safe_context_signal_count", 0)
                ),
            }
        )

    aggregate_groups: dict[str, Any] = {}
    for group, values in sorted(group_summary.items()):
        aggregate_groups[group] = {
            "records": values["records"],
            "correct": values["correct"],
            "false_positives": values["false_positives"],
            "false_negatives": values["false_negatives"],
            "accept_path_counts": dict(values["accept_path_counts"]),
            "mismatch_path_counts": dict(values["mismatch_path_counts"]),
        }

    false_positives = sum(
        record["mismatch_type"] == "false_positive"
        for record in mismatch_records
    )
    false_negatives = sum(
        record["mismatch_type"] == "false_negative"
        for record in mismatch_records
    )
    path_counts = Counter(record["v5_status"] for record in mismatch_records)
    report = {
        "candidate": "dangerous-content-v5-rc4-development",
        "records": len(rows),
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "mismatch_path_counts": dict(path_counts),
        "group_summary": aggregate_groups,
        "mismatch_records_without_text": mismatch_records,
        "raw_text_stored_or_printed": False,
        "independent_holdout_opened": False,
        "live_moderation_changed": False,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Development records: {len(rows)}")
    print(f"False positives: {false_positives}")
    print(f"False negatives: {false_negatives}")
    print(f"Mismatch paths: {dict(path_counts)}")
    print()
    print("GROUP PATH RESULTS")
    print("-" * 60)
    for group, values in aggregate_groups.items():
        print(
            f"{group}: {values['correct']}/{values['records']} correct | "
            f"FP {values['false_positives']} | FN {values['false_negatives']}"
        )
        if values["mismatch_path_counts"]:
            print(f"  mismatch paths: {values['mismatch_path_counts']}")
    print()
    print("MISMATCH RECORDS (NO TEXT)")
    print("-" * 60)
    for record in mismatch_records:
        print(
            f"{record['record_id']} | {record['mismatch_type']} | "
            f"V5: {record['v5_status']} | RC3: {record['rc3_status']} | "
            f"hazard: {record['hazard_probability']:.4f} | "
            f"safe signals: {record['safe_context_signal_count']}"
        )
    print()
    print(f"Report: {REPORT_PATH}")
    print("Raw text stored or printed: False")
    print("Independent holdout opened: False")
    print("Live moderation changed: False")


if __name__ == "__main__":
    main()
