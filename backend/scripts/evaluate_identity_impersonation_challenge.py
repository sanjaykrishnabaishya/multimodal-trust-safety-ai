from __future__ import annotations

import hashlib
import json
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
    / "independent_challenge_v1.json"
)

CHALLENGE_VERSION = "2026.08-v1"


POSITIVE_CASES = (
    "An unknown account copied my name and photographs and is messaging my friends as if it were me.",
    "A lookalike page is claiming to represent {organization}, but it is not operated by us.",
    "Someone opened an online profile under {name}'s identity without permission.",
    "The account mirrors our branding and falsely claims to speak for our company.",
    "A stranger is passing themselves off as me to contact my relatives.",
    "They duplicated my profile picture, biography, and username to deceive people.",
    "An unauthorized page claims it is the genuine customer-service account for {organization}.",
    "The person assumed my identity when creating the account.",
    "A copied profile is sending messages under my name.",
    "This user falsely represents themselves as {name}.",
    "An account has taken over my online identity and is speaking on my behalf.",
    "They made a convincing copy of our company page without authorization.",
    "The sender claims to be our chief executive, but the message is not from that person.",
    "A user is masquerading as a government officer.",
    "This profile belongs to someone pretending they are {name}.",
    "The account stole my photographs and presents them as its owner.",
    "Someone registered using my identity details without my consent.",
    "The message falsely claims to come from {organization}'s finance director.",
    "A fraudulent profile is representing itself as our official business page.",
    "This person adopted another individual's identity to gain trust.",
    "The sender is impersonating our support department.",
    "Someone is posing as my manager and contacting employees.",
    "The account is pretending to be an authorized representative of {organization}.",
    "A copied account is being used to deceive customers about who operates it.",
)


NEGATIVE_CASES = (
    "I am an employee of {organization} and this is my personal opinion.",
    "The official company page announced its updated opening hours.",
    "A newspaper article examined the growth of online identity fraud.",
    "The documentary describes several historic account-takeover investigations.",
    "This page is an unofficial fan community and is clearly labelled as such.",
    "The biography clearly states that the account is fictional.",
    "This is a classroom exercise about recognizing deceptive profiles.",
    "The security guide advises users to check whether an account is authentic.",
    "The company issued a warning about people copying its branding.",
    "Police published advice about reporting accounts that misuse photographs.",
    "The researcher studies how users recognize online identity deception.",
    "The report says impersonation complaints increased during the year.",
    "This account shares news and does not claim to represent {organization}.",
    "The actor plays a government officer in a fictional television programme.",
    "The museum employee is dressed as a historical public figure.",
    "The verified support team published a general service announcement.",
    "I am the authorized representative for my own registered business.",
    "The article quotes a victim describing a copied social-media profile.",
    "The help centre explains the steps for reporting a lookalike account.",
    "The satire page clearly states that it is not the real account.",
    "The fan profile uses original artwork and does not claim official status.",
    "The training material includes a fictional identity-theft scenario.",
    "The organization discusses account security during an awareness seminar.",
    "The public notice lists the department's verified communication channels.",
)


NAMES = (
    "Aarav Sharma",
    "Ananya Singh",
    "Rahul Das",
    "Priya Patel",
)

ORGANIZATIONS = (
    "Example Bank",
    "Example Telecom",
    "Example University",
    "Example Retail",
)


def _create_records() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    case_number = 1

    for variation in range(4):
        name = NAMES[variation]
        organization = ORGANIZATIONS[
            variation
        ]

        for template in POSITIVE_CASES:
            records.append(
                {
                    "case_id": (
                        f"ID-P-{case_number:03d}"
                    ),
                    "text": template.format(
                        name=name,
                        organization=organization,
                    ),
                    "expected_category": (
                        IDENTITY_CATEGORY
                    ),
                }
            )

            case_number += 1

    case_number = 1

    for variation in range(4):
        name = NAMES[variation]
        organization = ORGANIZATIONS[
            variation
        ]

        for template in NEGATIVE_CASES:
            records.append(
                {
                    "case_id": (
                        f"ID-N-{case_number:03d}"
                    ),
                    "text": template.format(
                        name=name,
                        organization=organization,
                    ),
                    "expected_category": (
                        NORMAL_CATEGORY
                    ),
                }
            )

            case_number += 1

    return records


def _safe_divide(
    numerator: int,
    denominator: int,
) -> float:
    if denominator <= 0:
        return 0.0

    return numerator / denominator


def _challenge_hash(
    records: list[dict[str, str]],
) -> str:
    serialized_records = json.dumps(
        records,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized_records.encode("utf-8")
    ).hexdigest()


def main() -> None:
    records = _create_records()

    true_positives = 0
    true_negatives = 0
    false_positives = 0
    false_negatives = 0
    action_failures = 0
    review_failures = 0
    policy_confirmation_failures = 0

    false_positive_case_ids: list[str] = []
    false_negative_case_ids: list[str] = []

    for record in records:
        result = analyze_identity_impersonation(
            record["text"]
        )

        expected_positive = (
            record["expected_category"]
            == IDENTITY_CATEGORY
        )

        predicted_positive = (
            result.get("category")
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

            false_positive_case_ids.append(
                record["case_id"]
            )

        else:
            false_negatives += 1

            false_negative_case_ids.append(
                record["case_id"]
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

    accuracy = _safe_divide(
        true_positives + true_negatives,
        total,
    )

    f1 = (
        2 * precision * recall
        / (precision + recall)
        if precision + recall > 0
        else 0.0
    )

    passed_target = (
        precision >= 0.85
        and recall >= 0.85
        and specificity >= 0.85
        and f1 >= 0.85
        and action_failures == 0
        and review_failures == 0
        and policy_confirmation_failures == 0
    )

    report: dict[str, Any] = {
        "benchmark_name": (
            "Frozen independent identity-"
            "impersonation challenge"
        ),
        "challenge_version": (
            CHALLENGE_VERSION
        ),
        "challenge_sha256": (
            _challenge_hash(records)
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
        "false_positive_case_ids": (
            false_positive_case_ids
        ),
        "false_negative_case_ids": (
            false_negative_case_ids
        ),
        "action_failures": action_failures,
        "review_failures": review_failures,
        "automatic_policy_confirmation_failures": (
            policy_confirmation_failures
        ),
        "passed_85_percent_target": (
            passed_target
        ),
        "limitations": [
            (
                "The cases are AI-authored and are not "
                "a human-labelled real-world dataset."
            ),
            (
                "The challenge was frozen before this "
                "evaluation and must not be modified "
                "after viewing its result."
            ),
            (
                "The benchmark evaluates text signals, "
                "not actual identity ownership."
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
        "IDENTITY IMPERSONATION CHALLENGE"
    )
    print("=" * 60)

    print(
        f"Challenge version: {CHALLENGE_VERSION}"
    )

    print(
        f"Challenge SHA-256: "
        f"{report['challenge_sha256']}"
    )

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
        f"Accuracy: {accuracy * 100:.2f}%"
    )

    print(
        f"Precision: {precision * 100:.2f}%"
    )

    print(
        f"Recall: {recall * 100:.2f}%"
    )

    print(
        "Specificity: "
        f"{specificity * 100:.2f}%"
    )

    print(f"F1: {f1 * 100:.2f}%")

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
    print(
        "False-positive case IDs: "
        f"{false_positive_case_ids}"
    )

    print(
        "False-negative case IDs: "
        f"{false_negative_case_ids}"
    )

    print()
    print(f"Report saved: {REPORT_PATH}")


if __name__ == "__main__":
    main()