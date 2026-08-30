"""Build and evaluate the safe synthetic Illegal Activities V1 contract."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

from app.services.illegal_activities_v1_service import (
    ILLEGAL_ACTION,
    ILLEGAL_CATEGORY,
    NORMAL_CATEGORY,
    UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_illegal_activities_v1,
    apply_illegal_activities_v1_fusion,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET_DIRECTORY = ROOT / "datasets" / "development" / "illegal_activities_v1"
DATASET_PATH = DATASET_DIRECTORY / "development.csv"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "illegal_activities" / "v1_ai_advisory_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.json"


GROUPS = {
    "controlled_goods_and_medicines": {
        "expected": ILLEGAL_CATEGORY,
        "subjects": (
            "illegal drugs",
            "controlled pills",
            "unapproved medicine",
            "psychotropic substances",
            "illegal narcotics",
        ),
        "frames": (
            "{subject} are for sale. Contact me to order now. Reference {index}.",
            "This listing offers {subject}. Delivery available; buy now. Reference {index}.",
            "The seller advertises {subject}. Message me to order. Reference {index}.",
            "A commercial post says {subject} are for sale and asks buyers to contact me. Reference {index}.",
        ),
    },
    "weapons_documents_and_counterfeit": {
        "expected": ILLEGAL_CATEGORY,
        "subjects": (
            "unlicensed gun",
            "gun without a license",
            "prohibited weapon",
            "fake identity document",
            "forged certificate",
            "counterfeit currency",
        ),
        "frames": (
            "A {subject} is for sale. Contact me to order now. Reference {index}.",
            "This post offers a {subject}; delivery available. Reference {index}.",
            "The account advertises a {subject}. Buy now. Reference {index}.",
            "A listing provides a {subject}. Message me to order. Reference {index}.",
        ),
    },
    "gambling_and_financial_facilitation": {
        "expected": ILLEGAL_CATEGORY,
        "subjects": (
            "illegal gambling",
            "illegal betting",
            "unlicensed betting",
            "unlicensed gambling",
            "money laundering service",
        ),
        "frames": (
            "Join this betting offer for {subject}; contact me. Reference {index}.",
            "The account promotes {subject}. Pay to receive access. Reference {index}.",
            "A commercial listing offers a {subject}. Contact me to order now. Reference {index}.",
            "This post advertises {subject}; buy now. Reference {index}.",
        ),
    },
    "commercial_services_and_protected_symbols": {
        "expected": ILLEGAL_CATEGORY,
        "subjects": (
            "prostitution services",
            "sexual services for money",
            "paid sexual service",
            "commercial sexual service",
            "fake government emblem",
            "misuse national emblem",
            "misuse the national flag",
        ),
        "frames": (
            "This post advertises {subject}. Contact me to order now. Reference {index}.",
            "A listing offers {subject}; book now. Reference {index}.",
            "The account promotes {subject}. Available tonight. Reference {index}.",
            "Contact me to use this in your advertisement: {subject}. Reference {index}.",
        ),
    },
    "safe_reporting_education_and_prevention": {
        "expected": NORMAL_CATEGORY,
        "subjects": (
            "illegal drugs",
            "unlicensed gun",
            "illegal gambling",
            "fake identity document",
            "counterfeit currency",
        ),
        "frames": (
            "A news report about {subject} warns viewers and condemns the conduct. Reference {index}.",
            "An educational prevention lesson discusses {subject} without facilitating a transaction. Reference {index}.",
            "A documentary reports on {subject} and says the matter was reported to authorities. Reference {index}.",
            "A safety warning says to avoid {subject}. Reference {index}.",
        ),
    },
    "legitimate_jobs_commerce_and_professional_context": {
        "expected": NORMAL_CATEGORY,
        "subjects": (
            "Microsoft job recruitment",
            "licensed pharmacy selling approved medicine",
            "licensed sporting event",
            "museum exhibition",
            "film prop",
            "lawful training range",
            "ordinary ecommerce listing",
        ),
        "frames": (
            "{subject} is described in an ordinary lawful announcement. Reference {index}.",
            "The page provides information about {subject}. Reference {index}.",
            "A verified organization publishes details about {subject}. Reference {index}.",
            "This is a neutral description of {subject}. Reference {index}.",
        ),
    },
    "fiction_history_and_research_boundary": {
        "expected": NORMAL_CATEGORY,
        "subjects": (
            "illegal drugs",
            "prohibited weapon",
            "illegal betting",
            "forged certificate",
            "fake government emblem",
        ),
        "frames": (
            "A fictional example mentions {subject} but contains no transaction or instructions. Reference {index}.",
            "Historical research discusses {subject} in an educational archive. Reference {index}.",
            "A documentary condemns {subject} and provides prevention information. Reference {index}.",
            "An academic discussion examines {subject} without facilitating it. Reference {index}.",
        ),
    },
    "jurisdiction_licensing_and_facilitation_uncertain": {
        "expected": UNCERTAIN_CATEGORY,
        "subjects": (
            "online betting service",
            "unlicensed betting",
            "protected government name",
            "unapproved medicine",
            "commercial sexual service",
        ),
        "frames": (
            "A post merely mentions an {subject}; licensing and jurisdiction are unknown. Reference {index}.",
            "The text names an {subject}, but does not establish a transaction or location. Reference {index}.",
            "A message refers to an {subject}; its legal status and purpose are unclear. Reference {index}.",
            "The content discusses an {subject} without enough context to determine facilitation. Reference {index}.",
        ),
    },
}


def build_records() -> list[dict[str, str]]:
    records = []
    for group, config in GROUPS.items():
        subjects = config["subjects"]
        frames = config["frames"]
        for index in range(1, 41):
            subject = subjects[(index - 1) % len(subjects)]
            frame = frames[((index - 1) // len(subjects)) % len(frames)]
            records.append(
                {
                    "record_id": f"{group.upper()}-{index:03d}",
                    "group": group,
                    "text": frame.format(subject=subject, index=index),
                    "expected_category": config["expected"],
                }
            )
    return records


def baseline() -> dict[str, object]:
    return {
        "category": NORMAL_CATEGORY,
        "severity": "None",
        "action": "Allow",
        "confidence": 0.70,
        "human_review_required": False,
        "reason": "No existing owner.",
        "matched_signals": [],
    }


def expected_action(category: str) -> str:
    if category == ILLEGAL_CATEGORY:
        return ILLEGAL_ACTION
    if category == UNCERTAIN_CATEGORY:
        return UNCERTAIN_ACTION
    return "Allow"


def evaluate(records: list[dict[str, str]]) -> dict:
    predictions = []
    group_results = defaultdict(lambda: {"correct": 0, "records": 0})
    mismatches = []
    action_failures = 0
    processing_errors = 0

    for record in records:
        try:
            analysis = analyze_illegal_activities_v1(
                record["text"],
                ["text"],
                use_openrouter=False,
            )
            decision = apply_illegal_activities_v1_fusion(
                **baseline(),
                analysis=analysis,
            )
            predicted = str(decision["category"])
            action_ok = decision["action"] == expected_action(
                record["expected_category"]
            )
            review_ok = bool(decision["human_review_required"]) == (
                record["expected_category"] != NORMAL_CATEGORY
            )
            contract_ok = (
                action_ok
                and review_ok
                and decision["automatic_enforcement_allowed"] is False
            )
        except Exception as error:
            processing_errors += 1
            predicted = "PROCESSING_ERROR"
            contract_ok = False
            analysis = {"fusion_status": type(error).__name__}

        correct = predicted == record["expected_category"]
        group_results[record["group"]]["records"] += 1
        group_results[record["group"]]["correct"] += int(correct)
        action_failures += int(not contract_ok)
        predictions.append((record["expected_category"], predicted))

        if not correct or not contract_ok:
            mismatches.append(
                {
                    "record_id": record["record_id"],
                    "group": record["group"],
                    "expected_category": record["expected_category"],
                    "predicted_category": predicted,
                    "fusion_status": analysis.get("fusion_status", "unknown"),
                    "action_contract_passed": contract_ok,
                }
            )

    total = len(records)
    correct = sum(expected == predicted for expected, predicted in predictions)
    true_positive = sum(
        expected == ILLEGAL_CATEGORY and predicted == ILLEGAL_CATEGORY
        for expected, predicted in predictions
    )
    false_positive = sum(
        expected != ILLEGAL_CATEGORY and predicted == ILLEGAL_CATEGORY
        for expected, predicted in predictions
    )
    false_negative = sum(
        expected == ILLEGAL_CATEGORY and predicted != ILLEGAL_CATEGORY
        for expected, predicted in predictions
    )
    safe_total = sum(expected == NORMAL_CATEGORY for expected, _ in predictions)
    true_safe = sum(
        expected == NORMAL_CATEGORY and predicted == NORMAL_CATEGORY
        for expected, predicted in predictions
    )

    precision = true_positive / max(1, true_positive + false_positive)
    recall = true_positive / max(1, true_positive + false_negative)
    specificity = true_safe / max(1, safe_total)
    accuracy = correct / max(1, total)

    formatted_groups = {}
    for group, values in group_results.items():
        values["accuracy"] = values["correct"] / max(1, values["records"])
        formatted_groups[group] = dict(values)
    minimum_group_accuracy = min(
        values["accuracy"] for values in formatted_groups.values()
    )

    gates = {
        "accuracy": accuracy >= 0.90,
        "illegal_precision": precision >= 0.90,
        "illegal_recall": recall >= 0.85,
        "safe_specificity": specificity >= 0.95,
        "minimum_group_accuracy": minimum_group_accuracy >= 0.85,
        "action_contract": action_failures == 0,
        "processing_contract": processing_errors == 0,
    }

    return {
        "version": "2026.08-illegal-activities-v1-ai-advisory-development",
        "records": total,
        "unique_texts": len({record["text"] for record in records}),
        "label_counts": dict(Counter(record["expected_category"] for record in records)),
        "accuracy": accuracy,
        "illegal_precision": precision,
        "illegal_recall": recall,
        "safe_specificity": specificity,
        "minimum_group_accuracy": minimum_group_accuracy,
        "action_contract_failures": action_failures,
        "processing_errors": processing_errors,
        "group_results": formatted_groups,
        "gates": gates,
        "passed_development_gate": all(gates.values()),
        "openrouter_used": False,
        "external_or_restricted_data_used": False,
        "actionable_harm_instructions_stored": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": True,
        "mismatches": mismatches,
    }


def write_outputs(records: list[dict[str, str]], result: dict) -> None:
    DATASET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)

    content_hash = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    report = {**result, "dataset_sha256": content_hash}
    report.pop("mismatches", None)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    MISMATCH_PATH.write_text(
        json.dumps(result["mismatches"], indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    records = build_records()
    result = evaluate(records)
    write_outputs(records, result)

    print("ILLEGAL ACTIVITIES V1 AI-ADVISORY DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {result['records']}")
    print(f"Unique texts: {result['unique_texts']}")
    print(f"Accuracy: {result['accuracy']:.2%}")
    print(f"Illegal precision: {result['illegal_precision']:.2%}")
    print(f"Illegal recall: {result['illegal_recall']:.2%}")
    print(f"Safe specificity: {result['safe_specificity']:.2%}")
    print(f"Minimum group accuracy: {result['minimum_group_accuracy']:.2%}")
    print(f"Action-contract failures: {result['action_contract_failures']}")
    print(f"Processing errors: {result['processing_errors']}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, values in result["group_results"].items():
        print(
            f"{group}: {values['correct']}/{values['records']} "
            f"({values['accuracy']:.2%})"
        )
    print()
    print(f"Passed development gate: {result['passed_development_gate']}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("OpenRouter used for bulk development evaluation: False")
    print("External or restricted data used: False")
    print("Automatic enforcement allowed: False")
    print("This is development policy evidence, not independent accuracy.")

    if not result["passed_development_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
