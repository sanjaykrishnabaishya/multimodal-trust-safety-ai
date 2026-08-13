from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.moderation_service import moderate_text


ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = ROOT / "datasets" / "development" / "terrorism_extremism_v1"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "development_v1"
)
DATASET_PATH = DATA_DIRECTORY / "development.csv"
REPORT_PATH = REPORT_DIRECTORY / "baseline_report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "baseline_mismatches.csv"

TERRORISM_CATEGORY = "Terrorism & Extremism"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
HATE_CATEGORY = "Hate Speech & Discrimination"
VIOLENCE_CATEGORY = "Violent Content"
SPAM_CATEGORY = "Spam, Scam & Phishing"
PRIVATE_CATEGORY = "Publishing Private Information"

MINIMUM_ACCURACY = 0.85
MINIMUM_TERRORISM_RECALL = 0.85
MINIMUM_SAFE_SPECIFICITY = 0.90
MINIMUM_BOUNDARY_ACCURACY = 0.85
MAXIMUM_ACTION_CONTRACT_FAILURES = 0
MAXIMUM_CATEGORY_MIX_FAILURES = 0


def add_cases(
    rows: list[dict[str, Any]],
    *,
    group: str,
    expected_category: str,
    texts: list[str],
    terrorism_violation: bool = False,
) -> None:
    start = len(rows) + 1
    for offset, text in enumerate(texts):
        rows.append(
            {
                "case_id": f"TERROR-V1-{start + offset:03d}",
                "group": group,
                "text": text,
                "expected_category": expected_category,
                "terrorism_violation": terrorism_violation,
            }
        )


def build_development_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    recruitment_frames = [
        "The account asks users to join a designated terrorist organization.",
        "The channel is recruiting volunteers for a banned extremist organization.",
        "The post urges followers to become members of a designated terrorist group.",
        "The message invites readers to enlist with a banned extremist network.",
        "The page directs supporters to register as recruits for a terrorist organization.",
    ]
    recruitment_contexts = [
        "It presents recruitment as a serious call to action.",
        "It asks interested people to respond privately.",
        "It encourages immediate participation.",
        "It is presented as genuine organizational outreach.",
    ]
    add_cases(
        rows,
        group="recruitment_and_membership",
        expected_category=TERRORISM_CATEGORY,
        terrorism_violation=True,
        texts=[
            f"{frame} {context}"
            for frame in recruitment_frames
            for context in recruitment_contexts
        ],
    )

    praise_frames = [
        "The post praises a designated terrorist organization and celebrates its attacks.",
        "The video caption glorifies a banned extremist organization as heroic.",
        "The message expresses support for a terrorist group and applauds its violence.",
        "The account promotes propaganda that celebrates a banned terrorist network.",
        "The page endorses a designated extremist organization and honors its attackers.",
    ]
    praise_contexts = [
        "The praise is direct and approving.",
        "There is no reporting or condemnation context.",
        "The message asks others to share the praise.",
        "The content presents the organization positively.",
    ]
    add_cases(
        rows,
        group="praise_glorification_and_propaganda",
        expected_category=TERRORISM_CATEGORY,
        terrorism_violation=True,
        texts=[
            f"{frame} {context}"
            for frame in praise_frames
            for context in praise_contexts
        ],
    )

    support_frames = [
        "The message requests donations for a designated terrorist organization.",
        "The post distributes recruitment propaganda for a banned extremist group.",
        "The account offers logistical assistance to a designated terrorist network.",
        "The page shares resources intended to support a banned extremist organization.",
        "The channel coordinates material support for a designated terrorist group.",
    ]
    support_contexts = [
        "It explicitly says the support is for the organization.",
        "The assistance is presented as intentional.",
        "It asks supporters to participate immediately.",
        "There is no educational or journalistic purpose.",
    ]
    add_cases(
        rows,
        group="funding_resources_and_operational_support",
        expected_category=TERRORISM_CATEGORY,
        terrorism_violation=True,
        texts=[
            f"{frame} {context}"
            for frame in support_frames
            for context in support_contexts
        ],
    )

    uncertain_frames = [
        "The post praises an organization, but its identity and legal status are unknown.",
        "The message asks users to join an unnamed group that may be extremist.",
        "The page requests donations for an organization whose designation cannot be verified.",
        "The account shares a symbol that might belong to a banned organization, but the match is uncertain.",
        "The content claims to represent an extremist network, but the organization cannot be authenticated.",
    ]
    uncertain_contexts = [
        "No official designation source is available.",
        "The evidence is insufficient for automatic classification.",
        "A qualified reviewer must verify the organization.",
        "The name could refer to an unrelated lawful group.",
    ]
    add_cases(
        rows,
        group="unknown_or_unverified_organization",
        expected_category=UNCERTAIN_CATEGORY,
        texts=[
            f"{frame} {context}"
            for frame in uncertain_frames
            for context in uncertain_contexts
        ],
    )

    safe_frames = [
        "A news report describes recruitment by a banned extremist organization and condemns it.",
        "An academic paper studies propaganda produced by a terrorist organization without endorsing it.",
        "A documentary explains the history of an extremist movement in a neutral manner.",
        "A public-safety message warns people not to donate to terrorist organizations.",
        "A court report records allegations of support for a banned organization without praising it.",
    ]
    safe_contexts = [
        "The purpose is reporting or public education.",
        "It contains no recruitment, praise, or assistance.",
        "The organization is discussed critically.",
        "The content explicitly opposes extremist violence.",
    ]
    add_cases(
        rows,
        group="reporting_education_history_and_condemnation",
        expected_category=NORMAL_CATEGORY,
        texts=[f"{frame} {context}" for frame in safe_frames for context in safe_contexts],
    )

    boundary_cases = [
        (
            HATE_CATEGORY,
            "People of that protected religion are inferior and should be expelled.",
        ),
        (
            HATE_CATEGORY,
            "Every member of that ethnic group should be excluded from public life.",
        ),
        (
            HATE_CATEGORY,
            "That protected community is subhuman and should lose its rights.",
        ),
        (
            HATE_CATEGORY,
            "Workers of that nationality should be denied employment.",
        ),
        (
            HATE_CATEGORY,
            "Followers of that faith are parasites and must be driven away.",
        ),
        (VIOLENCE_CATEGORY, "The footage graphically shows a decapitated victim."),
        (VIOLENCE_CATEGORY, "The image depicts severe visible blood and bodily injury."),
        (VIOLENCE_CATEGORY, "The video shows a person being tortured and mutilated."),
        (VIOLENCE_CATEGORY, "The scene contains burned human remains and exposed organs."),
        (VIOLENCE_CATEGORY, "The recording shows graphic physical violence against a victim."),
        (
            SPAM_CATEGORY,
            "Congratulations, send your OTP now to claim a cash reward.",
        ),
        (
            SPAM_CATEGORY,
            "Your bank account is blocked; share your password immediately.",
        ),
        (
            SPAM_CATEGORY,
            "Transfer a processing fee to unlock your lottery prize.",
        ),
        (
            SPAM_CATEGORY,
            "Click this suspicious link and provide your card details.",
        ),
        (
            SPAM_CATEGORY,
            "You won a prize; verify the claim by sending your banking credentials.",
        ),
        (
            PRIVATE_CATEGORY,
            "His private email address is john.smith@gmail.com.",
        ),
        (
            PRIVATE_CATEGORY,
            "The post publishes her personal mobile number without permission.",
        ),
        (
            PRIVATE_CATEGORY,
            "This message exposes a person's residential address.",
        ),
        (
            PRIVATE_CATEGORY,
            "The document shares private banking information belonging to another person.",
        ),
        (
            PRIVATE_CATEGORY,
            "The account posts someone's identity document number publicly.",
        ),
    ]
    grouped_boundary: dict[str, list[str]] = defaultdict(list)
    for category, text in boundary_cases:
        grouped_boundary[category].append(text)
    for category, texts in grouped_boundary.items():
        add_cases(
            rows,
            group="unrelated_category_isolation",
            expected_category=category,
            texts=texts,
        )
    return rows


def main() -> None:
    rows = build_development_rows()
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    results: list[dict[str, Any]] = []
    for row in rows:
        decision = moderate_text(text=str(row["text"]), source_context="unknown")
        correct = decision["category"] == row["expected_category"]
        terrorism_predicted = decision["category"] == TERRORISM_CATEGORY
        action_contract_failure = bool(
            terrorism_predicted
            and (
                decision["action"] != "Block and escalate"
                or decision["human_review_required"] is not True
            )
        )
        category_mix_failure = bool(
            row["expected_category"] not in {TERRORISM_CATEGORY, UNCERTAIN_CATEGORY}
            and terrorism_predicted
        )
        results.append(
            {
                **row,
                "predicted_category": decision["category"],
                "correct": correct,
                "action": decision["action"],
                "human_review_required": decision["human_review_required"],
                "confidence": decision["confidence"],
                "action_contract_failure": action_contract_failure,
                "category_mix_failure": category_mix_failure,
            }
        )

    total = len(results)
    correct_count = sum(bool(row["correct"]) for row in results)
    positive_rows = [row for row in results if row["terrorism_violation"]]
    safe_rows = [
        row
        for row in results
        if row["expected_category"] == NORMAL_CATEGORY
    ]
    boundary_rows = [
        row
        for row in results
        if row["group"] in {
            "unknown_or_unverified_organization",
            "unrelated_category_isolation",
        }
    ]
    terrorism_recall = safe_divide(
        sum(row["predicted_category"] == TERRORISM_CATEGORY for row in positive_rows),
        len(positive_rows),
    )
    safe_specificity = safe_divide(
        sum(bool(row["correct"]) for row in safe_rows), len(safe_rows)
    )
    boundary_accuracy = safe_divide(
        sum(bool(row["correct"]) for row in boundary_rows), len(boundary_rows)
    )
    action_failures = sum(bool(row["action_contract_failure"]) for row in results)
    mix_failures = sum(bool(row["category_mix_failure"]) for row in results)
    accuracy = safe_divide(correct_count, total)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[str(row["group"])].append(row)
    group_results: dict[str, dict[str, Any]] = {}
    for group, group_rows in sorted(grouped.items()):
        group_correct = sum(bool(row["correct"]) for row in group_rows)
        group_results[group] = {
            "records": len(group_rows),
            "correct": group_correct,
            "accuracy": round(safe_divide(group_correct, len(group_rows)), 4),
        }

    passed = bool(
        accuracy >= MINIMUM_ACCURACY
        and terrorism_recall >= MINIMUM_TERRORISM_RECALL
        and safe_specificity >= MINIMUM_SAFE_SPECIFICITY
        and boundary_accuracy >= MINIMUM_BOUNDARY_ACCURACY
        and action_failures <= MAXIMUM_ACTION_CONTRACT_FAILURES
        and mix_failures <= MAXIMUM_CATEGORY_MIX_FAILURES
    )
    mismatches = [row for row in results if not row["correct"]]
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with MISMATCH_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(results[0]))
        writer.writeheader()
        writer.writerows(mismatches)
    report = {
        "candidate": "terrorism-extremism-v1-rule-baseline",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": total,
        "expected_category_counts": dict(
            Counter(str(row["expected_category"]) for row in results)
        ),
        "accuracy": round(accuracy, 4),
        "terrorism_recall": round(terrorism_recall, 4),
        "safe_specificity": round(safe_specificity, 4),
        "boundary_accuracy": round(boundary_accuracy, 4),
        "action_contract_failures": action_failures,
        "category_mix_failures": mix_failures,
        "group_results": group_results,
        "passed_development_gate": passed,
        "organization_registry_used": False,
        "live_moderation_changed": False,
        "independent_accuracy": False,
        "dataset": str(DATASET_PATH),
        "mismatches": str(MISMATCH_PATH),
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("TERRORISM & EXTREMISM V1 DEVELOPMENT BASELINE")
    print("=" * 60)
    print(f"Records: {total}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Terrorism recall: {terrorism_recall * 100:.2f}%")
    print(f"Safe specificity: {safe_specificity * 100:.2f}%")
    print(f"Boundary accuracy: {boundary_accuracy * 100:.2f}%")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {mix_failures}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, metrics in group_results.items():
        print(f"{group}: {metrics['correct']}/{metrics['records']}")
    print()
    print(f"Passed 85% development gate: {passed}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Official organization registry used: False")
    print("Live moderation changed: False")
    print("This is development data, not independent accuracy.")


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


if __name__ == "__main__":
    main()
