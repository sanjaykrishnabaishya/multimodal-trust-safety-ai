from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.moderation_service import moderate_text


ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = ROOT / "datasets" / "development" / "dangerous_content_v1"
REPORT_DIRECTORY = (
    ROOT / "reports" / "evaluation" / "dangerous_content" / "development_v1"
)
DATASET_PATH = DATA_DIRECTORY / "development.csv"
REPORT_PATH = REPORT_DIRECTORY / "baseline_report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "baseline_mismatches.csv"

DANGEROUS_CATEGORY = "Dangerous Content"
NORMAL_CATEGORY = "Normal/Ignore"
VIOLENCE_CATEGORY = "Violent Content"
SPAM_CATEGORY = "Spam, Scam & Phishing"
PRIVATE_CATEGORY = "Publishing Private Information"
HATE_CATEGORY = "Hate Speech & Discrimination"
RELIGIOUS_CATEGORY = "Religiously Offensive Content"
CYBER_CATEGORY = "Cyberbullying & Harassment"

MINIMUM_ACCURACY = 0.85
MINIMUM_RECALL = 0.85
MINIMUM_SPECIFICITY = 0.90
MINIMUM_GROUP_ACCURACY = 0.85
MAXIMUM_ACTION_CONTRACT_FAILURES = 0
MAXIMUM_CATEGORY_MIX_FAILURES = 0


def add_cases(
    rows: list[dict[str, Any]],
    *,
    group: str,
    expected_category: str,
    texts: list[str],
    dangerous_violation: bool = False,
) -> None:
    start = len(rows) + 1
    for offset, text in enumerate(texts):
        rows.append(
            {
                "case_id": f"DANGER-V1-{start + offset:03d}",
                "group": group,
                "text": text,
                "expected_category": expected_category,
                "dangerous_violation": dangerous_violation,
            }
        )


def combine(frames: list[str], contexts: list[str]) -> list[str]:
    return [f"{frame} {context}" for frame in frames for context in contexts]


def build_development_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    add_cases(
        rows,
        group="dangerous_stunt_or_challenge_encouragement",
        expected_category=DANGEROUS_CATEGORY,
        dangerous_violation=True,
        texts=combine(
            [
                "The post urges viewers to try this dangerous stunt.",
                "The video tells teenagers to perform this dangerous stunt.",
                "The creator asks followers to do this dangerous challenge.",
                "The caption tells viewers to copy this life threatening stunt.",
                "The stream dares viewers to jump from the roof.",
            ],
            [
                "It encourages imitation without professional supervision.",
                "No protective controls or safety equipment are shown.",
                "The call to participate is direct and approving.",
                "The creator presents the risk as entertainment.",
            ],
        ),
    )

    add_cases(
        rows,
        group="hazardous_home_experiment_or_explosion",
        expected_category=DANGEROUS_CATEGORY,
        dangerous_violation=True,
        texts=combine(
            [
                "The tutorial encourages a dangerous experiment at home.",
                "The post advertises instructions to make an explosive.",
                "The creator tells untrained viewers to cause an explosion.",
                "The demonstration says do not use safety equipment.",
                "The post offers instructions to cause bodily harm.",
            ],
            [
                "It targets ordinary viewers rather than trained professionals.",
                "The content gives no warning or controlled setting.",
                "It asks the audience to repeat the action themselves.",
                "The behavior could cause serious injury or property damage.",
            ],
        ),
    )

    add_cases(
        rows,
        group="dangerous_self_other_or_property_action",
        expected_category=DANGEROUS_CATEGORY,
        dangerous_violation=True,
        texts=combine(
            [
                "The challenge tells a participant to set yourself on fire.",
                "The post orders a participant to harm yourself for views.",
                "The message tells a participant to hurt yourself on camera.",
                "The video encourages viewers to destroy their property dangerously.",
                "The creator admits the challenge can kill you but promotes it anyway.",
            ],
            [
                "The instruction is direct rather than educational.",
                "There is no prevention, reporting, or condemnation context.",
                "The audience is encouraged to imitate the behavior.",
                "The foreseeable result is injury, death, or destruction.",
            ],
        ),
    )

    add_cases(
        rows,
        group="safe_reporting_warning_and_prevention",
        expected_category=NORMAL_CATEGORY,
        texts=combine(
            [
                "A safety video warns people not to try this dangerous stunt.",
                "A news report describes a dangerous challenge that caused injuries.",
                "A school lesson explains why students must not perform this dangerous stunt.",
                "A public notice says never jump from the roof.",
                "An article condemns creators who promote setting oneself on fire.",
            ],
            [
                "The purpose is prevention and public education.",
                "It contains no encouragement to imitate the behavior.",
                "Clear safety advice is provided to the audience.",
                "The dangerous behavior is explicitly discouraged.",
            ],
        ),
    )

    add_cases(
        rows,
        group="professional_controlled_or_educational_context",
        expected_category=NORMAL_CATEGORY,
        texts=combine(
            [
                "A licensed stunt team performs a controlled demonstration with protective equipment.",
                "A chemistry instructor conducts a supervised experiment in a certified laboratory.",
                "Firefighters demonstrate fire safety inside a secured training area.",
                "An engineering class discusses explosion prevention without harmful instructions.",
                "A workplace trainer explains why safety equipment must always be used.",
            ],
            [
                "Qualified professionals supervise the activity.",
                "The audience is told not to imitate the demonstration.",
                "Protective controls and emergency procedures are clearly described.",
                "The purpose is safety training rather than entertainment.",
            ],
        ),
    )

    add_cases(
        rows,
        group="violent_depiction_boundary",
        expected_category=VIOLENCE_CATEGORY,
        texts=combine(
            [
                "The footage contains graphic violence against a victim.",
                "The scene shows a decapitated body.",
                "The image displays visible internal organs after an attack.",
                "The recording shows a person being tortured.",
                "The photograph shows a burned body.",
            ],
            [
                "It depicts the aftermath rather than instructing viewers to copy an action.",
                "The primary policy issue is the graphic depiction.",
                "No stunt, experiment, or challenge is promoted.",
                "The visible bodily harm requires the Violence category.",
            ],
        ),
    )

    boundary_cases = [
        (SPAM_CATEGORY, "Congratulations! You won a cash prize. Call now to claim it."),
        (SPAM_CATEGORY, "Share your OTP now to unlock the promised lottery reward."),
        (SPAM_CATEGORY, "Click this suspicious link to verify your bank password."),
        (SPAM_CATEGORY, "Transfer a processing fee to receive the fake prize."),
        (PRIVATE_CATEGORY, "His private email address is john.smith@gmail.com."),
        (PRIVATE_CATEGORY, "The post publishes her personal phone number 9876543210."),
        (PRIVATE_CATEGORY, "The message exposes PAN ABCDE1234F without consent."),
        (PRIVATE_CATEGORY, "Someone posted Aadhaar number 1234 5678 9012 publicly."),
        (HATE_CATEGORY, "People of this protected religion are inferior and should be expelled."),
        (HATE_CATEGORY, "That protected ethnic group is not human."),
        (HATE_CATEGORY, "Deny jobs to them because of their nationality."),
        (HATE_CATEGORY, "All members of that protected group are criminals."),
        (RELIGIOUS_CATEGORY, "Deliberately desecrate their sacred religious symbol."),
        (RELIGIOUS_CATEGORY, "Destroy the holy scripture specifically to insult the faith."),
        (RELIGIOUS_CATEGORY, "Deface the place of worship to mock the religion."),
        (RELIGIOUS_CATEGORY, "Use obscene insults against the community's prophet."),
        (CYBER_CATEGORY, "I will keep contacting you after you told me to stop."),
        (CYBER_CATEGORY, "Everyone should repeatedly message and humiliate this person."),
        (CYBER_CATEGORY, "I will post insults about you every day."),
        (CYBER_CATEGORY, "The group coordinates repeated harassment of one target."),
    ]
    for expected_category, text in boundary_cases:
        add_cases(
            rows,
            group="unrelated_category_isolation",
            expected_category=expected_category,
            texts=[text],
        )

    if len(rows) != 140:
        raise RuntimeError(f"Expected 140 development records; found {len(rows)}")
    return rows


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    rows = build_development_rows()
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)

    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    results: list[dict[str, Any]] = []
    confusion = Counter()
    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    action_failures = 0
    category_mix_failures = 0

    for row in rows:
        decision = moderate_text(row["text"], source_context="user")
        predicted_category = str(decision.get("category", ""))
        expected_category = str(row["expected_category"])
        expected_dangerous = bool(row["dangerous_violation"])
        predicted_dangerous = predicted_category == DANGEROUS_CATEGORY

        if expected_dangerous and predicted_dangerous:
            confusion["tp"] += 1
        elif expected_dangerous:
            confusion["fn"] += 1
        elif predicted_dangerous:
            confusion["fp"] += 1
        else:
            confusion["tn"] += 1

        exact_correct = predicted_category == expected_category
        group = str(row["group"])
        group_totals[group] += 1
        group_correct[group] += int(exact_correct)

        action_failure = predicted_dangerous and (
            decision.get("action") != "Remove and send for human review"
            or decision.get("human_review_required") is not True
        )
        category_mix_failure = not expected_dangerous and predicted_dangerous
        action_failures += int(action_failure)
        category_mix_failures += int(category_mix_failure)

        results.append(
            {
                **row,
                "predicted_category": predicted_category,
                "predicted_action": decision.get("action"),
                "confidence": decision.get("confidence"),
                "human_review_required": decision.get("human_review_required"),
                "exact_correct": exact_correct,
                "action_contract_failure": action_failure,
                "category_mix_failure": category_mix_failure,
            }
        )

    records = len(results)
    correct = sum(bool(row["exact_correct"]) for row in results)
    tp, tn = confusion["tp"], confusion["tn"]
    fp, fn = confusion["fp"], confusion["fn"]
    accuracy = safe_divide(correct, records)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    group_results = {
        group: {
            "correct": group_correct[group],
            "records": total,
            "accuracy": safe_divide(group_correct[group], total),
        }
        for group, total in sorted(group_totals.items())
    }
    minimum_group_accuracy = min(
        item["accuracy"] for item in group_results.values()
    )
    gate_checks = {
        "overall_accuracy": accuracy >= MINIMUM_ACCURACY,
        "dangerous_recall": recall >= MINIMUM_RECALL,
        "safe_specificity": specificity >= MINIMUM_SPECIFICITY,
        "minimum_group_accuracy": minimum_group_accuracy >= MINIMUM_GROUP_ACCURACY,
        "action_contract": action_failures <= MAXIMUM_ACTION_CONTRACT_FAILURES,
        "category_mix_contract": category_mix_failures <= MAXIMUM_CATEGORY_MIX_FAILURES,
    }
    passed = all(gate_checks.values())

    report = {
        "component": "Dangerous Content V1 development baseline",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": group_results,
        "gate_checks": gate_checks,
        "passed_development_gate": passed,
        "external_data_used": False,
        "actionable_harm_instructions_stored": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "dataset": str(DATASET_PATH),
    }
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    mismatch_fields = [
        "case_id",
        "group",
        "expected_category",
        "predicted_category",
        "predicted_action",
        "confidence",
        "human_review_required",
        "action_contract_failure",
        "category_mix_failure",
        "text",
    ]
    with MISMATCH_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=mismatch_fields)
        writer.writeheader()
        for row in results:
            if not row["exact_correct"] or row["action_contract_failure"]:
                writer.writerow({field: row.get(field) for field in mismatch_fields})

    print("DANGEROUS CONTENT V1 DEVELOPMENT BASELINE")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"Precision: {precision:.2%}")
    print(f"Recall: {recall:.2%}")
    print(f"Safe specificity: {specificity:.2%}")
    print(f"F1: {f1:.2%}")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, item in group_results.items():
        print(f"{group}: {item['correct']}/{item['records']}")
    print(f"\nPassed 85% development gate: {passed}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Live moderation changed: False")
    print("This is development data, not independent accuracy.")


if __name__ == "__main__":
    main()
