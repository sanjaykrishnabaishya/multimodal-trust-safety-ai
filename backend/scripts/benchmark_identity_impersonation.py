from __future__ import annotations

import json
import random
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.identity_impersonation_service import (
    IDENTITY_CATEGORY,
    NORMAL_CATEGORY,
    analyze_identity_impersonation,
)


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent

REPORT_DIRECTORY = (
    PROJECT_DIRECTORY
    / "reports"
    / "evaluation"
    / "identity_impersonation"
)

REPORT_PATH = (
    REPORT_DIRECTORY
    / "synthetic_benchmark.json"
)


POSITIVE_TEMPLATES = (
    "Someone is impersonating me using a cloned account.",
    "This person is impersonating me on social media.",
    "This account is pretending to be me.",
    "Someone is posing as me using my photograph.",
    "They created a fake profile pretending to be me.",
    "A cloned social media profile is using my identity.",
    "They are using someone else's identity.",
    "They copied another person's identity documents.",
    "This is a fake identity used to deceive customers.",
    "The account uses stolen identity documents.",
    "They created a duplicate account pretending to be {name}.",
    "Someone made a fake profile using {name}'s photograph.",
    "This profile is posing as an official {organization} account.",
    "They stole her identity and opened a fake account.",
    "They copied his profile and are pretending to be him.",
    "This is an identity theft complaint involving a cloned account.",
    "The attacker used another person's credentials and identity.",
    "Someone has been impersonating our company.",
    "This profile is impersonating my organization.",
    "The fraudster created a fabricated identity.",
    "I am the official bank support agent. Send your OTP immediately.",
    "We are the authorized support team. Provide your password.",
    "This is the official account department. Verify your login immediately.",
    "I am the verified bank representative. Transfer the fee now.",
    "We are calling from technical support. Share your credentials.",
    "This account is posing as {organization} support and requesting passwords.",
    "The fake customer support profile asked me to send money.",
    "Someone is impersonating {organization} and requesting account details.",
    "The cloned account claims to be official support and requests an OTP.",
    "A fake government officer asked for my banking details.",
)

NEGATIVE_TEMPLATES = (
    "This is a clearly marked parody account.",
    "This is an unofficial fan page.",
    "The profile is clearly labelled as satire.",
    "This fictional example is used for impersonation awareness.",
    "This is an educational example about identity theft.",
    "The seminar explains how to prevent identity theft.",
    "Here is how to report impersonation safely.",
    "Security training teaches users how to recognize fake accounts.",
    "Never impersonate another person online.",
    "Identity theft is a crime.",
    "Beware of fake accounts and protect your credentials.",
    "Never share your credentials with anyone.",
    "Microsoft opened a new office in London.",
    "{name} attended a public event yesterday.",
    "{organization} published its quarterly results.",
    "The customer contacted the official support department.",
    "I work for {organization} as a software engineer.",
    "This is the official company newsletter.",
    "The verified account announced a new product.",
    "The government department published a public notice.",
    "The police officer gave a public safety presentation.",
    "The bank representative explained its new savings product.",
    "The article reports an increase in identity theft.",
    "The documentary discusses historical identity fraud.",
    "The report describes how account takeover attacks work.",
    "The researcher studies online impersonation.",
    "The company warned customers about cloned accounts.",
    "The help page contains impersonation prevention advice.",
    "The news article mentions a fake account investigation.",
    "The guide explains how parody accounts should be labelled.",
)


NAMES = (
    "Aarav Sharma",
    "Ananya Singh",
    "Rahul Das",
    "Priya Patel",
    "Vikram Rao",
    "Meera Gupta",
    "Arjun Kumar",
    "Neha Verma",
    "Rohan Bose",
    "Kavya Iyer",
)

ORGANIZATIONS = (
    "Example Bank",
    "Example Telecom",
    "Example Marketplace",
    "Example University",
    "Example Airlines",
    "Example Insurance",
    "Example Technologies",
    "Example Foundation",
    "Example Hospital",
    "Example Retail",
)


def _percentage(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return round(
        numerator / denominator * 100,
        2,
    )


def _safe_divide(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return numerator / denominator


def _create_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    for name in NAMES:
        for index, template in enumerate(
            POSITIVE_TEMPLATES
        ):
            organization = ORGANIZATIONS[
                index % len(ORGANIZATIONS)
            ]

            records.append(
                {
                    "text": template.format(
                        name=name,
                        organization=organization,
                    ),
                    "expected_category": (
                        IDENTITY_CATEGORY
                    ),
                }
            )

        for index, template in enumerate(
            NEGATIVE_TEMPLATES
        ):
            organization = ORGANIZATIONS[
                index % len(ORGANIZATIONS)
            ]

            records.append(
                {
                    "text": template.format(
                        name=name,
                        organization=organization,
                    ),
                    "expected_category": (
                        NORMAL_CATEGORY
                    ),
                }
            )

    random.Random(20260807).shuffle(
        records
    )

    return records


def main() -> None:
    records = _create_records()

    true_positives = 0
    true_negatives = 0
    false_positives = 0
    false_negatives = 0
    action_failures = 0
    review_failures = 0
    policy_confirmation_failures = 0

    mismatch_types: dict[str, int] = {}

    for record in records:
        result = analyze_identity_impersonation(
            record["text"]
        )

        expected_category = record[
            "expected_category"
        ]

        predicted_category = str(
            result.get(
                "category",
                NORMAL_CATEGORY,
            )
        )

        expected_positive = (
            expected_category
            == IDENTITY_CATEGORY
        )

        predicted_positive = (
            predicted_category
            == IDENTITY_CATEGORY
        )

        if expected_positive and predicted_positive:
            true_positives += 1

        elif (
            not expected_positive
            and not predicted_positive
        ):
            true_negatives += 1

        elif (
            not expected_positive
            and predicted_positive
        ):
            false_positives += 1

            key = (
                "safe_content_flagged"
            )

            mismatch_types[key] = (
                mismatch_types.get(key, 0)
                + 1
            )

        else:
            false_negatives += 1

            key = (
                "impersonation_missed"
            )

            mismatch_types[key] = (
                mismatch_types.get(key, 0)
                + 1
            )

        if predicted_positive:
            if (
                result.get("action")
                != "Refer to human review"
            ):
                action_failures += 1

            if (
                result.get(
                    "human_review_required"
                )
                is not True
            ):
                review_failures += 1

            if (
                result.get(
                    "policy_violation"
                )
                is not False
            ):
                policy_confirmation_failures += 1

    total = len(records)

    accuracy = _safe_divide(
        true_positives + true_negatives,
        total,
    )

    precision = _safe_divide(
        true_positives,
        true_positives + false_positives,
    )

    recall = _safe_divide(
        true_positives,
        true_positives + false_negatives,
    )

    specificity = _safe_divide(
        true_negatives,
        true_negatives + false_positives,
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    passed_target = (
        accuracy >= 0.85
        and precision >= 0.85
        and recall >= 0.85
        and specificity >= 0.85
        and action_failures == 0
        and review_failures == 0
        and policy_confirmation_failures == 0
    )

    report: dict[str, Any] = {
        "benchmark_name": (
            "Synthetic identity theft and "
            "impersonation benchmark"
        ),
        "created_at_utc": (
            datetime.now(timezone.utc).isoformat()
        ),
        "records": total,
        "positive_records": (
            true_positives + false_negatives
        ),
        "negative_records": (
            true_negatives + false_positives
        ),
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "accuracy_percent": round(
            accuracy * 100,
            2,
        ),
        "precision_percent": round(
            precision * 100,
            2,
        ),
        "recall_percent": round(
            recall * 100,
            2,
        ),
        "specificity_percent": round(
            specificity * 100,
            2,
        ),
        "f1_percent": round(
            f1 * 100,
            2,
        ),
        "action_failures": action_failures,
        "review_failures": review_failures,
        "automatic_policy_confirmation_failures": (
            policy_confirmation_failures
        ),
        "mismatch_types": mismatch_types,
        "passed_85_percent_target": (
            passed_target
        ),
        "limitations": [
            (
                "This is a synthetic benchmark and "
                "does not prove real-world accuracy."
            ),
            (
                "Identity ownership, authorization, "
                "deception, and parody status require "
                "human or platform-level verification."
            ),
            (
                "No raw identity documents, credentials, "
                "or personal information are used."
            ),
        ],
    }

    REPORT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    REPORT_PATH.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "IDENTITY IMPERSONATION BENCHMARK"
    )
    print("=" * 60)
    print(f"Records: {total:,}")

    print(
        "Positive records: "
        f"{true_positives + false_negatives:,}"
    )

    print(
        "Negative records: "
        f"{true_negatives + false_positives:,}"
    )

    print(
        "Accuracy: "
        f"{_percentage(true_positives + true_negatives, total):.2f}%"
    )

    print(
        "Precision: "
        f"{precision * 100:.2f}%"
    )

    print(
        "Recall: "
        f"{recall * 100:.2f}%"
    )

    print(
        "Specificity: "
        f"{specificity * 100:.2f}%"
    )

    print(
        "F1: "
        f"{f1 * 100:.2f}%"
    )

    print(
        f"False positives: {false_positives:,}"
    )

    print(
        f"False negatives: {false_negatives:,}"
    )

    print(
        f"Action failures: {action_failures:,}"
    )

    print(
        "Human-review failures: "
        f"{review_failures:,}"
    )

    print(
        "Automatic policy-confirmation failures: "
        f"{policy_confirmation_failures:,}"
    )

    print(
        "Passed 85% target: "
        f"{passed_target}"
    )

    print()
    print(f"Report saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()