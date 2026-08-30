"""Build and evaluate the fresh Illegal Activities V2 RC2 development set."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.illegal_activities_v2_rc2_service import (
    ILLEGAL_ACTION,
    ILLEGAL_CATEGORY,
    NORMAL_CATEGORY,
    UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_illegal_activities_v2_rc2,
    apply_illegal_activities_v2_rc2_fusion,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET_DIRECTORY = ROOT / "datasets" / "development" / "illegal_activities_v2_rc2"
DATASET_PATH = DATASET_DIRECTORY / "development.csv"
PRIOR_DATASET_PATH = (
    ROOT / "datasets" / "development" / "illegal_activities_v1" / "development.csv"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v2_rc2_policy_generalization_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.json"

OWNER_ACTIONS = {
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Publishing Private Information": "Remove exposed information and send for human review",
    "Terrorism & Extremism": "Block and escalate",
    "Hate Speech & Discrimination": "Remove and escalate",
    "Cyberbullying & Harassment": "Limit, flag, and send for human review",
    "Child Exploitation": "Block and immediately escalate",
    "Dangerous Content": "Remove and send for human review",
    "Graphic, Obscene & Sexual Content": "Age-restrict or limit distribution",
}

SUBJECTS = {
    "controlled": (
        "illegal drugs",
        "controlled substances",
        "controlled pills",
        "unapproved medicine",
        "prohibited narcotics",
    ),
    "weapons": (
        "an unlicensed firearm",
        "a prohibited weapon",
        "a forged passport",
        "a fake identity document",
        "counterfeit currency",
    ),
    "financial": (
        "illegal betting",
        "unlicensed gambling",
        "unlawful wagering",
        "a money laundering service",
        "counterfeit banknotes",
    ),
    "services": (
        "a prostitution service",
        "a paid sexual service",
        "a commercial sexual service",
        "a fake government emblem",
        "a counterfeit government seal",
    ),
}


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def prior_hashes() -> set[str]:
    if not PRIOR_DATASET_PATH.is_file():
        return set()
    with PRIOR_DATASET_PATH.open("r", encoding="utf-8", newline="") as handle:
        return {text_hash(str(row["text"])) for row in csv.DictReader(handle)}


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected_category: str,
    subjects: tuple[str, ...],
    frames: tuple[str, ...],
    *,
    existing_category: str = NORMAL_CATEGORY,
    existing_action: str = "Allow",
    existing_review: bool = False,
) -> None:
    for index in range(1, 41):
        subject = subjects[(index - 1) % len(subjects)]
        frame = frames[((index - 1) // len(subjects)) % len(frames)]
        text = frame.format(subject=subject, index=index)
        rows.append(
            {
                "record_id": f"{group.upper()}-{index:03d}",
                "group": group,
                "text": text,
                "expected_category": expected_category,
                "existing_category": existing_category,
                "existing_action": existing_action,
                "existing_review": existing_review,
            }
        )


def build_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    add_group(
        rows,
        "controlled_goods_current_transactions",
        ILLEGAL_CATEGORY,
        SUBJECTS["controlled"],
        (
            "A current marketplace listing has {subject} for sale and asks buyers to contact the seller. RC2 case {index}.",
            "The supplier offers {subject}; courier delivery is available after payment. RC2 case {index}.",
            "This post advertises {subject} and tells customers to place an order. RC2 case {index}.",
            "An account markets {subject} with a price per item and shipment available. RC2 case {index}.",
            "A seller offers {subject}; buyers should direct message to order. RC2 case {index}.",
            "The current offer makes {subject} available to buyers. RC2 case {index}.",
            "A commercial listing promotes the sale of {subject} with delivery available. RC2 case {index}.",
            "The supplier says {subject} are selling now and payment is required. RC2 case {index}.",
        ),
    )
    add_group(
        rows,
        "weapons_documents_and_counterfeit_transactions",
        ILLEGAL_CATEGORY,
        SUBJECTS["weapons"],
        (
            "The marketplace lists {subject} for sale and requests a direct message. RC2 case {index}.",
            "A seller offers {subject}; courier delivery is available. RC2 case {index}.",
            "This listing advertises {subject} with a price per item. RC2 case {index}.",
            "The supplier markets {subject} and asks customers to place an order. RC2 case {index}.",
            "A current offer provides access to {subject} after payment. RC2 case {index}.",
            "The account promotes the sale of {subject} to buyers. RC2 case {index}.",
            "An advertiser makes {subject} available and says contact me. RC2 case {index}.",
            "A commercial listing offers {subject}; shipment is available. RC2 case {index}.",
        ),
    )
    add_group(
        rows,
        "gambling_and_financial_facilitation",
        ILLEGAL_CATEGORY,
        SUBJECTS["financial"],
        (
            "This post promotes {subject} and tells readers to sign up to wager. RC2 case {index}.",
            "The account advertises {subject}; payment is required for access. RC2 case {index}.",
            "A current offer provides access to {subject} after payment. RC2 case {index}.",
            "The seller markets {subject} and asks customers to contact me. RC2 case {index}.",
            "A commercial listing offers {subject}; direct message to order. RC2 case {index}.",
            "This marketplace promotion tells buyers to join the betting for {subject}. RC2 case {index}.",
            "The supplier arranges access to {subject} and states a price per item. RC2 case {index}.",
            "An account promotes the sale of {subject}; delivery is available. RC2 case {index}.",
        ),
    )
    add_group(
        rows,
        "prohibited_services_and_symbol_facilitation",
        ILLEGAL_CATEGORY,
        SUBJECTS["services"],
        (
            "This post advertises {subject}; customers are told to book now. RC2 case {index}.",
            "A current offer makes {subject} available tonight after payment. RC2 case {index}.",
            "The account markets {subject} and asks buyers to contact the seller. RC2 case {index}.",
            "A commercial listing offers {subject}; reserve a slot by direct message. RC2 case {index}.",
            "The supplier promotes the sale of {subject} to customers. RC2 case {index}.",
            "A seller provides access to {subject} after payment. RC2 case {index}.",
            "The marketplace listing advertises {subject} and says contact me. RC2 case {index}.",
            "This current offer lists {subject} with delivery available. RC2 case {index}.",
        ),
    )
    mixed_subjects = (
        "controlled substances",
        "an unlicensed firearm",
        "illegal betting",
        "a forged passport",
        "a paid sexual service",
    )
    add_group(
        rows,
        "passive_and_mixed_order_transaction_evidence",
        ILLEGAL_CATEGORY,
        mixed_subjects,
        (
            "Available to buyers is {subject}; the marketplace requests payment. RC2 case {index}.",
            "Courier delivery can be arranged for {subject} by the supplier. RC2 case {index}.",
            "For customers seeking it, the seller offers {subject}. RC2 case {index}.",
            "Payment is required before the account provides access to {subject}. RC2 case {index}.",
            "A price per item appears beside {subject} in this commercial listing. RC2 case {index}.",
            "Direct message is requested by the seller offering {subject}. RC2 case {index}.",
            "The sale being promoted by this post concerns {subject}. RC2 case {index}.",
            "Shipment is available from the supplier for {subject}. RC2 case {index}.",
        ),
    )
    all_subjects = SUBJECTS["controlled"] + SUBJECTS["weapons"]
    add_group(
        rows,
        "reporting_warning_and_prevention",
        NORMAL_CATEGORY,
        all_subjects,
        (
            "A news report discusses {subject} and warns viewers not to buy. RC2 case {index}.",
            "A prevention campaign covers {subject}; it contains no transaction. RC2 case {index}.",
            "A law-enforcement notice reports {subject} to authorities and does not facilitate it. RC2 case {index}.",
            "Public awareness material condemns {subject} and is not a live offer. RC2 case {index}.",
        ),
    )
    add_group(
        rows,
        "fiction_history_research_and_quotation",
        NORMAL_CATEGORY,
        mixed_subjects,
        (
            "A fictional scene mentions {subject}; it is fictional and not real. RC2 case {index}.",
            "A research paper examines {subject} for research only. RC2 case {index}.",
            "A historical archive preserves a quoted advertisement for {subject}; it is not a live offer. RC2 case {index}.",
            "An academic discussion quotes 'buy now' beside {subject}, quoted for analysis and without facilitating it. RC2 case {index}.",
            "A novel excerpt contains quoted dialogue about {subject} and no live transaction. RC2 case {index}.",
            "A documentary studies {subject} as a case study and contains no transaction. RC2 case {index}.",
            "A screenplay uses {subject} in a dramatic reenactment, not a live offer. RC2 case {index}.",
            "A museum exhibit documents {subject} for prevention and does not facilitate it. RC2 case {index}.",
        ),
    )
    legitimate_subjects = (
        "Microsoft job recruitment",
        "a licensed pharmacy selling approved medicine",
        "an authorized retailer",
        "a licensed sporting event",
        "a museum exhibition",
        "a film prop",
        "a lawful training range",
        "professional compliance review",
    )
    add_group(
        rows,
        "legitimate_jobs_commerce_and_professional_context",
        NORMAL_CATEGORY,
        legitimate_subjects,
        (
            "{subject} appears in an ordinary lawful announcement. RC2 case {index}.",
            "A verified organization publishes neutral information about {subject}. RC2 case {index}.",
            "This page describes {subject} without any prohibited transaction. RC2 case {index}.",
            "The notice concerns {subject} in a regulated professional context. RC2 case {index}.",
            "An educational page explains {subject}. RC2 case {index}.",
        ),
    )
    uncertain_subjects = (
        "an online betting service",
        "unlicensed gambling",
        "a protected government name",
        "unapproved medicine",
        "a commercial sexual service",
    )
    add_group(
        rows,
        "jurisdiction_licensing_and_status_uncertainty",
        UNCERTAIN_CATEGORY,
        uncertain_subjects,
        (
            "A message merely mentions {subject}; license status is unclear and no transaction is established. RC2 case {index}.",
            "The page refers to {subject}, but jurisdiction remains unknown. RC2 case {index}.",
            "A neutral reference names {subject}; legal status is unresolved and context is incomplete. RC2 case {index}.",
            "The content mentions {subject}; location is unknown and purpose is unclear. RC2 case {index}.",
            "A post references {subject}, but its status is unverified and cannot establish a transaction. RC2 case {index}.",
        ),
    )
    owner_subjects = (
        "illegal drugs",
        "a prohibited weapon",
        "illegal betting",
        "a forged passport",
        "a paid sexual service",
    )
    owners = tuple(OWNER_ACTIONS)
    for index in range(1, 41):
        owner = owners[(index - 1) % len(owners)]
        subject = owner_subjects[(index - 1) % len(owner_subjects)]
        text = (
            f"An existing {owner} decision accompanies a current listing for "
            f"{subject}. RC2 owner case {index}."
        )
        rows.append(
            {
                "record_id": f"ESTABLISHED_OWNER-{index:03d}",
                "group": "established_category_owner_isolation",
                "text": text,
                "expected_category": owner,
                "existing_category": owner,
                "existing_action": OWNER_ACTIONS[owner],
                "existing_review": True,
            }
        )
    for index in range(1, 41):
        text = (
            "A child or minor is linked to a sexual private image; the separate "
            f"child-safety owner is already active. RC2 child case {index}."
        )
        rows.append(
            {
                "record_id": f"CHILD-OWNER-{index:03d}",
                "group": "child_safety_owner_boundary",
                "text": text,
                "expected_category": "Child Exploitation",
                "existing_category": "Child Exploitation",
                "existing_action": OWNER_ACTIONS["Child Exploitation"],
                "existing_review": True,
            }
        )
    safe_subjects = (
        "a software engineering vacancy",
        "a cooking class",
        "a charity fundraiser",
        "a music lesson",
        "a public library event",
    )
    add_group(
        rows,
        "ordinary_unrelated_safe_context",
        NORMAL_CATEGORY,
        safe_subjects,
        (
            "This community notice announces {subject}. RC2 case {index}.",
            "A local organization publishes details about {subject}. RC2 case {index}.",
            "The page contains an ordinary description of {subject}. RC2 case {index}.",
            "A verified public calendar lists {subject}. RC2 case {index}.",
        ),
    )
    return rows


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    hashes = [text_hash(str(row["text"])) for row in records]
    overlap = set(hashes) & prior_hashes()
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Duplicate RC2 development text detected.")
    if overlap:
        raise RuntimeError("Prior development text overlap detected.")

    tp = tn = fp = fn = 0
    action_failures = category_mix_failures = processing_errors = 0
    group_results: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "correct": 0}
    )
    mismatches: list[dict[str, Any]] = []

    for row in records:
        group = str(row["group"])
        expected = str(row["expected_category"])
        group_results[group]["records"] += 1
        try:
            analysis = analyze_illegal_activities_v2_rc2(
                str(row["text"]),
                ["text"],
                use_openrouter=False,
            )
            decision = apply_illegal_activities_v2_rc2_fusion(
                category=str(row["existing_category"]),
                severity="None" if row["existing_category"] == NORMAL_CATEGORY else "High",
                action=str(row["existing_action"]),
                confidence=0.70,
                human_review_required=bool(row["existing_review"]),
                reason="Development baseline owner.",
                matched_signals=[],
                analysis=analysis,
            )
            predicted = str(decision["category"])
            correct = predicted == expected
            group_results[group]["correct"] += int(correct)

            expected_action = str(row["existing_action"])
            expected_review = bool(row["existing_review"])
            if expected == ILLEGAL_CATEGORY:
                expected_action = ILLEGAL_ACTION
                expected_review = True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action = UNCERTAIN_ACTION
                expected_review = True
            contract_ok = (
                decision.get("action") == expected_action
                and bool(decision.get("human_review_required")) == expected_review
                and decision.get("automatic_enforcement_allowed") is False
            )
            action_failures += int(not contract_ok)
            category_mix_failures += int(not correct)

            expected_illegal = expected == ILLEGAL_CATEGORY
            predicted_illegal = predicted == ILLEGAL_CATEGORY
            if expected_illegal and predicted_illegal:
                tp += 1
            elif expected_illegal:
                fn += 1
            elif predicted_illegal:
                fp += 1
            else:
                tn += 1

            if not correct or not contract_ok:
                mismatches.append(
                    {
                        "record_id": row["record_id"],
                        "group": group,
                        "expected_category": expected,
                        "predicted_category": predicted,
                        "fusion_status": analysis.get("fusion_status", "unknown"),
                        "action_contract_passed": contract_ok,
                    }
                )
        except Exception as error:
            processing_errors += 1
            mismatches.append(
                {
                    "record_id": row["record_id"],
                    "group": group,
                    "error": type(error).__name__,
                }
            )

    total = len(records)
    positives = tp + fn
    negatives = tn + fp
    accuracy = ratio(tp + tn, total)
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, positives)
    specificity = ratio(tn, negatives)
    f1 = ratio(2 * precision * recall, precision + recall)
    aggregate_groups = {
        group: {
            "records": values["records"],
            "correct": values["correct"],
            "accuracy": ratio(values["correct"], values["records"]),
        }
        for group, values in sorted(group_results.items())
    }
    minimum_group_accuracy = min(
        values["accuracy"] for values in aggregate_groups.values()
    )
    gates = {
        "zero_prior_development_overlap": not overlap,
        "accuracy": accuracy >= 0.92,
        "illegal_precision": precision >= 0.95,
        "illegal_recall": recall >= 0.90,
        "safe_specificity": specificity >= 0.97,
        "f1": f1 >= 0.92,
        "minimum_group_accuracy": minimum_group_accuracy >= 0.88,
        "action_contract": action_failures == 0,
        "category_mix_contract": category_mix_failures == 0,
        "processing_contract": processing_errors == 0,
    }
    return {
        "version": "2026.08-illegal-activities-v2-rc2-development",
        "records": total,
        "unique_texts": len(set(hashes)),
        "prior_development_overlap": len(overlap),
        "label_counts": dict(Counter(str(row["expected_category"]) for row in records)),
        "accuracy": accuracy,
        "illegal_precision": precision,
        "illegal_recall": recall,
        "safe_specificity": specificity,
        "f1": f1,
        "minimum_group_accuracy": minimum_group_accuracy,
        "false_positives": fp,
        "false_negatives": fn,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "processing_errors": processing_errors,
        "group_results": aggregate_groups,
        "gates": gates,
        "passed_development_gate": all(gates.values()),
        "rc1_aggregate_failure_signals_used": [
            "transaction_family_recall",
            "safe_fiction_and_research_boundary_generalization",
            "exact_action_and_category_routing",
        ],
        "rc1_holdout_cases_predictions_or_mismatches_read": False,
        "openrouter_used": False,
        "external_or_restricted_data_used": False,
        "actionable_harm_instructions_stored": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "mismatches": mismatches,
    }


def write_outputs(records: list[dict[str, Any]], result: dict[str, Any]) -> None:
    DATASET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    report = {**result, "dataset_sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()}
    report.pop("mismatches", None)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MISMATCH_PATH.write_text(
        json.dumps(result["mismatches"], indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    records = build_records()
    if len(records) != 480:
        raise RuntimeError(f"Unexpected RC2 development size: {len(records)}")
    result = evaluate(records)
    write_outputs(records, result)

    print("ILLEGAL ACTIVITIES V2 RC2 POLICY-GENERALIZATION DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {result['records']}")
    print(f"Unique texts: {result['unique_texts']}")
    print(f"Prior development overlap: {result['prior_development_overlap']}")
    print(f"Accuracy: {result['accuracy']:.2%}")
    print(f"Illegal precision: {result['illegal_precision']:.2%}")
    print(f"Illegal recall: {result['illegal_recall']:.2%}")
    print(f"Safe specificity: {result['safe_specificity']:.2%}")
    print(f"F1: {result['f1']:.2%}")
    print(f"Minimum group accuracy: {result['minimum_group_accuracy']:.2%}")
    print(f"Action-contract failures: {result['action_contract_failures']}")
    print(f"Category-mix failures: {result['category_mix_failures']}")
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
    print("RC1 aggregate failure signals used: True")
    print("RC1 holdout cases, predictions, and mismatches read: False")
    print("OpenRouter used for bulk evaluation: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("This is development policy evidence, not independent accuracy.")
    if not result["passed_development_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
