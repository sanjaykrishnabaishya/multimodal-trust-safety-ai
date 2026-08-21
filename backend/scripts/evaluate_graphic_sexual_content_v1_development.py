from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.moderation_service import moderate_text


ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = (
    ROOT / "datasets" / "development" / "graphic_sexual_content_v1"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "development_v1"
)
DATASET_PATH = DATA_DIRECTORY / "development.csv"
REPORT_PATH = REPORT_DIRECTORY / "baseline_report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "baseline_mismatches.csv"

SEXUAL_CATEGORY = "Graphic, Obscene & Sexual Content"
SEXUAL_HARASSMENT_CATEGORY = "Sexual Harassment"
NORMAL_CATEGORY = "Normal/Ignore"

MINIMUM_ACCURACY = 0.85
MINIMUM_RECALL = 0.85
MINIMUM_SPECIFICITY = 0.90
MINIMUM_GROUP_ACCURACY = 0.85


def combine(frames: list[str], contexts: list[str]) -> list[str]:
    return [f"{frame} {context}" for frame in frames for context in contexts]


def add_cases(
    rows: list[dict[str, Any]],
    *,
    group: str,
    expected_category: str,
    texts: list[str],
    sexual_violation: bool = False,
) -> None:
    start = len(rows) + 1
    for offset, text in enumerate(texts):
        rows.append(
            {
                "case_id": f"GSC-V1-{start + offset:03d}",
                "group": group,
                "text": text,
                "expected_category": expected_category,
                "sexual_violation": sexual_violation,
            }
        )


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    add_cases(
        rows,
        group="adult_explicit_content",
        expected_category=SEXUAL_CATEGORY,
        sexual_violation=True,
        texts=combine(
            [
                "The post contains uncensored adult sexual activity.",
                "The upload is described as explicit pornography involving adults.",
                "The clip presents clearly explicit adult-only sexual material.",
                "The animation depicts explicit sexual activity between adults.",
                "The image set contains visible adult nudity presented sexually.",
            ],
            [
                "It is presented for sexual viewing rather than education.",
                "No medical, artistic, or documentary context is provided.",
                "The description identifies the material as adult explicit content.",
                "The primary policy issue is explicit sexual presentation.",
            ],
        ),
    )
    add_cases(
        rows,
        group="commercial_morphed_and_synthetic_explicit_content",
        expected_category=SEXUAL_CATEGORY,
        sexual_violation=True,
        texts=combine(
            [
                "The account promotes paid access to explicit adult material.",
                "The message advertises the sale of uncensored pornography.",
                "The post distributes morphed explicit sexual imagery of an adult.",
                "The upload contains synthetic adult sexual imagery made for arousal.",
                "The page invites users to view an explicit adult-content collection.",
            ],
            [
                "The purpose is commercial or sexual rather than educational.",
                "It contains no health, news, or recognized artistic context.",
                "The sexual nature of the material is stated directly.",
                "The content is promoted as explicit viewing material.",
            ],
        ),
    )
    add_cases(
        rows,
        group="medical_health_and_education_context",
        expected_category=NORMAL_CATEGORY,
        texts=combine(
            [
                "A hospital publishes a clinical sexual-health lesson for adults.",
                "A medical textbook discusses human reproductive anatomy.",
                "A public-health organization explains adult sexual wellbeing.",
                "A licensed clinician presents a non-erotic anatomy diagram.",
                "A university course covers consent and sexual health.",
            ],
            [
                "The legitimate educational purpose is clear.",
                "The responsible medical or educational organization is identified.",
                "The material is clinical and is not presented for arousal.",
                "The context is health education rather than explicit entertainment.",
            ],
        ),
    )
    add_cases(
        rows,
        group="recognized_art_and_nonexplicit_media_context",
        expected_category=NORMAL_CATEGORY,
        texts=combine(
            [
                "A museum catalog discusses a recognized classical nude sculpture.",
                "An art-history class studies a well-known Renaissance painting.",
                "A film review shows a non-explicit adult-rated poster.",
                "A gallery notice describes established figurative artwork.",
                "A documentary discusses changing standards in historical art.",
            ],
            [
                "No explicit sexual detail is presented.",
                "The context is clearly artistic or historical.",
                "The material is not promoted for sexual viewing.",
                "The recognized work is discussed for cultural education.",
            ],
        ),
    )
    add_cases(
        rows,
        group="nonsexual_romance_clothing_and_body_boundary",
        expected_category=NORMAL_CATEGORY,
        texts=combine(
            [
                "Two adults hold hands during a romantic dinner.",
                "A fashion catalog shows adults wearing ordinary swimwear.",
                "A fitness lesson demonstrates a standard exercise pose.",
                "A family photograph shows a parent feeding an infant.",
                "A relationship article discusses affection without sexual detail.",
            ],
            [
                "The presentation is nonsexual.",
                "There is no explicit activity or sexualized framing.",
                "The ordinary context is clear from the description.",
                "Nothing is promoted for arousal or explicit viewing.",
            ],
        ),
    )
    add_cases(
        rows,
        group="sexual_harassment_category_boundary",
        expected_category=SEXUAL_HARASSMENT_CATEGORY,
        texts=combine(
            [
                "A coworker repeatedly sends unwanted sexual remarks to one person.",
                "The sender continues requesting sexual favors after being refused.",
                "A user sends unwanted explicit messages to a named recipient.",
                "The supervisor makes persistent unwelcome sexual comments.",
                "Someone repeatedly pressures a target to discuss sexual activity.",
            ],
            [
                "The conduct is directed at a person and is clearly unwelcome.",
                "The primary issue is targeted sexual harassment.",
                "The recipient has stated that the contact must stop.",
                "This is interpersonal misconduct rather than general explicit media.",
            ],
        ),
    )

    boundary_cases = [
        ("Spam, Scam & Phishing", "A fake prize message asks the recipient to pay a processing fee."),
        ("Spam, Scam & Phishing", "A phishing page impersonates a bank and requests a password."),
        ("Spam, Scam & Phishing", "An unsolicited promotion promises guaranteed investment returns."),
        ("Spam, Scam & Phishing", "A scammer asks for an OTP to release a fictional reward."),
        ("Publishing Private Information", "The post exposes the synthetic address test.user@example.com."),
        ("Publishing Private Information", "A message publishes a person's private account identifier."),
        ("Publishing Private Information", "The upload reveals a private residential location without consent."),
        ("Publishing Private Information", "A user shares another person's confidential contact details."),
        ("Cyberbullying & Harassment", "A group coordinates repeated humiliation of one identified target."),
        ("Cyberbullying & Harassment", "The sender keeps contacting a person after being told to stop."),
        ("Cyberbullying & Harassment", "A user posts intimidating messages about the same target every day."),
        ("Cyberbullying & Harassment", "Several accounts organize persistent harassment of one individual."),
        ("Child Exploitation", "A safety report flags suspected child sexual exploitation for immediate review."),
        ("Child Exploitation", "The moderation notice reports possible sexual exploitation of a minor."),
        ("Child Exploitation", "A child-safety team escalates suspected grooming of a minor."),
        ("Child Exploitation", "The report identifies possible child sexual abuse material without describing it."),
        ("Violent Content", "The footage graphically depicts severe physical violence against a person."),
        ("Violent Content", "The image shows the bloody aftermath of an assault."),
        ("Dangerous Content", "The post encourages viewers to attempt a hazardous stunt without safeguards."),
        ("Dangerous Content", "A creator promotes a reckless act around energized equipment."),
    ]
    for expected, text in boundary_cases:
        add_cases(
            rows,
            group="unrelated_category_isolation",
            expected_category=expected,
            texts=[text],
        )

    if len(rows) != 140:
        raise RuntimeError(f"Expected 140 development records; found {len(rows)}")
    return rows


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    rows = build_rows()
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    confusion = Counter()
    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    action_contract_failures = 0
    category_mix_failures = 0
    results: list[dict[str, Any]] = []
    for row in rows:
        decision = moderate_text(row["text"], source_context="user")
        predicted = str(decision.get("category", ""))
        expected = str(row["expected_category"])
        expected_positive = bool(row["sexual_violation"])
        predicted_positive = predicted == SEXUAL_CATEGORY
        if expected_positive and predicted_positive:
            confusion["tp"] += 1
        elif expected_positive:
            confusion["fn"] += 1
        elif predicted_positive:
            confusion["fp"] += 1
        else:
            confusion["tn"] += 1

        exact = predicted == expected
        group = str(row["group"])
        group_totals[group] += 1
        group_correct[group] += int(exact)
        action_failure = predicted_positive and (
            decision.get("action") != "Block or age-restrict"
            or decision.get("human_review_required") is not True
        )
        mix_failure = not expected_positive and predicted_positive
        action_contract_failures += int(action_failure)
        category_mix_failures += int(mix_failure)
        results.append(
            {
                **row,
                "predicted_category": predicted,
                "predicted_action": decision.get("action"),
                "confidence": decision.get("confidence"),
                "human_review_required": decision.get("human_review_required"),
                "exact_correct": exact,
                "action_contract_failure": action_failure,
                "category_mix_failure": mix_failure,
            }
        )

    records = len(results)
    tp, tn = confusion["tp"], confusion["tn"]
    fp, fn = confusion["fp"], confusion["fn"]
    accuracy = ratio(sum(bool(row["exact_correct"]) for row in results), records)
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    f1 = ratio(2 * precision * recall, precision + recall)
    group_results = {
        group: {
            "correct": group_correct[group],
            "records": total,
            "accuracy": ratio(group_correct[group], total),
        }
        for group, total in sorted(group_totals.items())
    }
    minimum_group_accuracy = min(
        item["accuracy"] for item in group_results.values()
    )
    gate_checks = {
        "overall_accuracy": accuracy >= MINIMUM_ACCURACY,
        "sexual_content_recall": recall >= MINIMUM_RECALL,
        "safe_specificity": specificity >= MINIMUM_SPECIFICITY,
        "minimum_group_accuracy": minimum_group_accuracy >= MINIMUM_GROUP_ACCURACY,
        "action_contract": action_contract_failures == 0,
        "category_mix_contract": category_mix_failures == 0,
    }
    passed = all(gate_checks.values())

    report = {
        "component": "Graphic, Obscene & Sexual Content V1 development baseline",
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
        "action_contract_failures": action_contract_failures,
        "category_mix_failures": category_mix_failures,
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": group_results,
        "gate_checks": gate_checks,
        "passed_development_gate": passed,
        "external_or_restricted_data_used": False,
        "explicit_descriptions_stored": False,
        "child_exploitation_examples_are_high_level_only": True,
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

    print("GRAPHIC, OBSCENE & SEXUAL CONTENT V1 DEVELOPMENT BASELINE")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Precision: {precision * 100:.2f}%")
    print(f"Recall: {recall * 100:.2f}%")
    print(f"Safe specificity: {specificity * 100:.2f}%")
    print(f"F1: {f1 * 100:.2f}%")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"Action-contract failures: {action_contract_failures}")
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
    print("Explicit sexual descriptions stored: False")
    print("Child-exploitation examples are high-level safety labels only: True")
    print("Live moderation changed: False")
    print("This is development data, not independent accuracy.")


if __name__ == "__main__":
    main()
