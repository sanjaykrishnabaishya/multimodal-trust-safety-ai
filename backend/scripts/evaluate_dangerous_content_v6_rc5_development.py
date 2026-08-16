from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.dangerous_content_v6_rc5_service import (
    analyze_dangerous_content_v6_rc5,
)


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v6_rc5_policy_generalization_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
DATASET_DIRECTORY = (
    ROOT_DIRECTORY / "datasets" / "development" / "dangerous_content_v6_rc5"
)
DATASET_PATH = DATASET_DIRECTORY / "development.csv"
MANIFEST_PATH = DATASET_DIRECTORY / "manifest.json"
RC4_CANDIDATE_DIRECTORY = (
    ROOT_DIRECTORY
    / "backend"
    / "storage"
    / "candidates"
    / "dangerous-content-v5-rc4"
)
RC3_CANDIDATE_DIRECTORY = (
    ROOT_DIRECTORY
    / "backend"
    / "storage"
    / "candidates"
    / "dangerous-content-v4-rc3"
)

DANGEROUS_CATEGORY = "Dangerous Content"
DANGEROUS_ACTION = "Remove and send for human review"


def text_hash(text: str) -> str:
    return hashlib.sha256(
        " ".join(text.lower().split()).encode("utf-8")
    ).hexdigest()


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected_dangerous: bool,
    concepts: list[str],
    templates: list[str],
    existing_category: str = "Normal/Ignore",
) -> None:
    for concept_index, concept in enumerate(concepts, start=1):
        for template_index, template in enumerate(templates, start=1):
            text = template.format(concept=concept)
            rows.append(
                {
                    "record_id": f"{group.upper()}-{concept_index:02d}-{template_index:02d}",
                    "group": group,
                    "expected_dangerous": expected_dangerous,
                    "existing_category": existing_category,
                    "text": text,
                    "text_sha256": text_hash(text),
                }
            )


PASSIVE_TEMPLATES = [
    "Participation in {concept} is promoted to ordinary users despite the danger.",
    "Imitation of {concept} is endorsed as a challenge for viewers.",
    "The performance of {concept} is presented as worthy of imitation by followers.",
    "Undertaking {concept} is recommended to amateurs without safeguards.",
    "Replication of {concept} is celebrated as something the public should attempt.",
    "Trying {concept} is framed as a dare that participants ought to perform.",
    "The audience is encouraged to take part in {concept} despite the physical risk.",
    "Recreation of {concept} is pushed to users outside a controlled setting.",
]

MIXED_ORDER_TEMPLATES = [
    "Despite the danger, {concept} is promoted and viewers are told to imitate it.",
    "The post presents {concept}; ordinary people are then called on to recreate it.",
    "Followers see {concept} celebrated before being encouraged to participate.",
    "After showing {concept}, the message recommends that the audience attempt it.",
    "The physical risk of {concept} is dismissed while users are pressed to copy it.",
    "A creator describes {concept} and then challenges amateurs to follow the example.",
    "Public participation is requested after {concept} is framed as entertainment.",
    "The message first praises {concept} and later appeals to viewers to undertake it.",
]

INDIRECT_TEMPLATES = [
    "The creator endorses attempts at {concept} for attention and asks others to take part.",
    "A post glorifies {concept} and recommends its recreation by followers.",
    "The channel celebrates {concept} as a challenge the audience should perform.",
    "The uploader promotes {concept} and appeals to ordinary users to imitate it.",
    "The message frames {concept} as an example to copy despite the warning.",
    "Viewers are told that participation in {concept} deserves endorsement.",
    "The public is pushed to replicate {concept} outside professional control.",
    "The author calls on amateurs to undertake {concept} for entertainment.",
]

SAFE_TEMPLATES = [
    "A safety bulletin warns the public not to attempt {concept}.",
    "An incident report condemns {concept} and describes prevention.",
    "Researchers discuss {concept} without endorsement or encouragement.",
    "The documentary reports {concept} but tells viewers never to imitate it.",
    "A historical account describes {concept} and discourages recreation.",
    "The message explains why people must avoid {concept}.",
    "A prevention campaign says the audience should not participate in {concept}.",
    "The article documents {concept} with no invitation to copy it.",
]

PROFESSIONAL_TEMPLATES = [
    "A qualified team studies {concept} inside a controlled facility.",
    "Licensed professionals manage {concept} during an authorized test.",
    "Trained operators examine {concept} behind protective barriers.",
    "Certified technicians handle {concept} under formal safeguards.",
    "A supervised demonstration covers {concept} with safety procedures.",
    "Professional staff assess {concept} in a controlled setting.",
    "An authorized exercise evaluates {concept} using protective equipment.",
    "A licensed team discusses {concept} during a supervised operation.",
]

BENIGN_TEMPLATES = [
    "A friendly instructor promotes {concept} as a harmless beginner activity.",
    "Students are encouraged to participate in {concept} for skill development.",
    "The club recommends {concept} as an ordinary hobby for newcomers.",
    "A teacher asks the class to imitate {concept} during a routine lesson.",
    "Viewers are invited to try {concept} as a safe creative practice.",
    "The group celebrates {concept} as an age-appropriate classroom activity.",
    "Beginners are challenged to repeat {concept} at a normal learning pace.",
    "The tutorial endorses {concept} as a harmless introductory exercise.",
]


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    positive_groups = [
        (
            "passive_noun_form_advocacy",
            [
                "a reckless act near an unstable elevated edge",
                "unsafe contact with energized equipment",
                "an uncontrolled fire activity near property",
                "entry into fast-moving water",
                "an unguarded moving-machine act",
            ],
            PASSIVE_TEMPLATES,
        ),
        (
            "mixed_order_dangerous_promotion",
            [
                "a hazardous stunt around falling debris",
                "a high-risk act with a pressurized container",
                "an unsafe activity that endangers bystanders",
                "a reckless act likely to cause property damage",
                "an unprotected activity above a dangerous drop",
            ],
            MIXED_ORDER_TEMPLATES,
        ),
        (
            "indirect_glorification_and_recommendation",
            [
                "a perilous activity involving hazardous fumes",
                "an unsafe act near an open flame",
                "a dangerous activity with corrosive material",
                "a reckless stunt beside deep water",
                "an act exposing another person to physical harm",
            ],
            INDIRECT_TEMPLATES,
        ),
    ]
    for group, concepts, templates in positive_groups:
        add_group(rows, group, True, concepts, templates)

    add_group(
        rows,
        "explicit_bystander_and_property_endangerment",
        True,
        [
            "an activity that exposes bystanders to falling objects",
            "an act that endangers people beside powered machinery",
            "a stunt that exposes occupied property to an uncontrolled fire",
            "an activity likely to cause serious property destruction",
            "a challenge that exposes another person to bodily harm",
        ],
        MIXED_ORDER_TEMPLATES,
    )

    add_group(
        rows,
        "warning_reporting_and_prevention",
        False,
        [
            "a dangerous elevated stunt",
            "unsafe handling of energized hardware",
            "an uncontrolled heat-source activity",
            "a reckless water challenge",
            "interference with powered machinery",
        ],
        SAFE_TEMPLATES,
    )
    add_group(
        rows,
        "professional_and_controlled_context",
        False,
        [
            "an energized-equipment hazard",
            "a pressurized-system hazard",
            "a moving-machine hazard",
            "an elevated rescue hazard",
            "a hazardous-vapor containment issue",
        ],
        PROFESSIONAL_TEMPLATES,
    )
    add_group(
        rows,
        "benign_encouragement_without_hazard",
        False,
        [
            "a beginner rhythm exercise",
            "an ordinary drawing technique",
            "a simple vocabulary puzzle",
            "a routine photography practice",
            "a harmless theatre rehearsal",
        ],
        BENIGN_TEMPLATES,
    )

    owner_cases = [
        ("Violent Content", "depicts a graphic assault"),
        ("Publishing Private Information", "publishes a private home address"),
        ("Spam, Scam & Phishing", "impersonates support to request a secret code"),
        ("Cyberbullying & Harassment", "repeatedly intimidates a named target"),
        ("Hate Speech & Discrimination", "attacks people for a protected identity"),
        ("Religiously Offensive Content", "denigrates a revered sacred figure"),
        ("Terrorism & Extremism", "requests support for extremist activity"),
        ("Misinformation & Fake News", "makes a checkable public factual claim"),
    ]
    for owner_index, (owner, description) in enumerate(owner_cases, start=1):
        for template_index, template in enumerate(
            [
                "For this RC5 ownership boundary, the material {description}.",
                "The separate specialist remains responsible because the item {description}.",
                "Dangerous Content must not take ownership when a sample {description}.",
                "The established policy owner is retained for wording that {description}.",
                "This new isolation probe preserves the primary category when it {description}.",
            ],
            start=1,
        ):
            text = template.format(description=description)
            rows.append(
                {
                    "record_id": f"OWNER-{owner_index:02d}-{template_index:02d}",
                    "group": "established_category_owner_isolation",
                    "expected_dangerous": False,
                    "existing_category": owner,
                    "text": text,
                    "text_sha256": text_hash(text),
                }
            )
    return rows


def prior_development_hashes() -> set[str]:
    hashes: set[str] = set()
    paths = [
        RC4_CANDIDATE_DIRECTORY / "development" / "development.csv",
        RC3_CANDIDATE_DIRECTORY / "development" / "train.csv",
        RC3_CANDIDATE_DIRECTORY / "development" / "validation.csv",
    ]
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                hashes.add(row["text_sha256"])
    return hashes


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    rows = build_rows()
    if len(rows) != 320:
        raise RuntimeError(f"Unexpected development record count: {len(rows)}")
    hashes = [row["text_sha256"] for row in rows]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Duplicate RC5 development text detected.")
    overlap = set(hashes) & prior_development_hashes()
    if overlap:
        raise RuntimeError("Prior development text overlap detected.")

    tp = tn = fp = fn = 0
    action_contract_failures = 0
    category_mix_failures = 0
    processing_errors = 0
    frozen_rc4_accepts = 0
    rc5_recoveries = 0
    group_results: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "correct": 0}
    )

    for row in rows:
        group_results[row["group"]]["records"] += 1
        try:
            result = analyze_dangerous_content_v6_rc5(
                row["text"],
                existing_category=row["existing_category"],
            )
            predicted = result.get("category") == DANGEROUS_CATEGORY
            expected = bool(row["expected_dangerous"])
            if predicted == expected:
                group_results[row["group"]]["correct"] += 1
            if expected and predicted:
                tp += 1
            elif expected:
                fn += 1
            elif predicted:
                fp += 1
            else:
                tn += 1
            if result.get("rc5_policy_recovery_used") is True:
                rc5_recoveries += 1
            if result.get("dangerous_content_v6_rc5_status") == "frozen_rc4_path_applied":
                frozen_rc4_accepts += 1
            if result.get("automatic_enforcement_allowed") is not False:
                action_contract_failures += 1
            if predicted and (
                result.get("action") != DANGEROUS_ACTION
                or result.get("human_review_required") is not True
            ):
                action_contract_failures += 1
            if result.get("category") not in (None, DANGEROUS_CATEGORY):
                category_mix_failures += 1
            if row["existing_category"] not in (
                "Normal/Ignore",
                "Uncertain",
                "Abusive Words",
            ) and predicted:
                category_mix_failures += 1
        except Exception:
            processing_errors += 1

    records = len(rows)
    accuracy = ratio(tp + tn, records)
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    f1 = ratio(2 * precision * recall, precision + recall)
    minimum_group_accuracy = min(
        ratio(values["correct"], values["records"])
        for values in group_results.values()
    )
    passed = bool(
        accuracy >= 0.90
        and precision >= 0.92
        and recall >= 0.90
        and specificity >= 0.97
        and f1 >= 0.90
        and minimum_group_accuracy >= 0.85
        and action_contract_failures == 0
        and category_mix_failures == 0
        and processing_errors == 0
        and not overlap
    )

    DATASET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        fields = [
            "record_id",
            "group",
            "expected_dangerous",
            "existing_category",
            "text",
            "text_sha256",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "candidate": "dangerous-content-v6-rc5-development",
        "records": records,
        "source": "synthetic high-level policy concepts",
        "prior_development_text_overlap": len(overlap),
        "rc4_independent_aggregate_used_as_development_signal": True,
        "rc4_independent_aggregate_signal": {
            "dangerous_precision": 0.9930,
            "dangerous_recall": 0.8875,
            "minimum_group_accuracy": 0.8125,
            "weak_aggregate_families": [
                "novel_mixed_order_promotion",
                "novel_passive_dangerous_advocacy",
                "novel_direct_dangerous_advocacy",
            ],
        },
        "rc4_holdout_cases_read": False,
        "rc4_holdout_predictions_or_mismatches_read": False,
        "external_or_restricted_data_used": False,
        "actionable_harm_instructions_stored": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    aggregate_groups = {
        group: {
            "records": values["records"],
            "correct": values["correct"],
            "accuracy": ratio(values["correct"], values["records"]),
        }
        for group, values in sorted(group_results.items())
    }
    report = {
        **manifest,
        "accuracy": accuracy,
        "dangerous_precision": precision,
        "dangerous_recall": recall,
        "safe_specificity": specificity,
        "f1": f1,
        "minimum_group_accuracy": minimum_group_accuracy,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "frozen_rc4_accepts": frozen_rc4_accepts,
        "rc5_policy_recoveries": rc5_recoveries,
        "action_contract_failures": action_contract_failures,
        "category_mix_failures": category_mix_failures,
        "processing_errors": processing_errors,
        "group_results": aggregate_groups,
        "passed_development_gate": passed,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("DANGEROUS CONTENT V6 RC5 POLICY-GENERALIZATION DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"Prior development overlap: {len(overlap)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Dangerous precision: {precision * 100:.2f}%")
    print(f"Dangerous recall: {recall * 100:.2f}%")
    print(f"Safe specificity: {specificity * 100:.2f}%")
    print(f"F1: {f1 * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Frozen RC4 accepts: {frozen_rc4_accepts}")
    print(f"RC5 policy recoveries: {rc5_recoveries}")
    print(f"Action-contract failures: {action_contract_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Processing errors: {processing_errors}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, values in aggregate_groups.items():
        print(
            f"{group}: {values['correct']}/{values['records']} "
            f"({values['accuracy'] * 100:.2f}%)"
        )
    print()
    print(f"Passed development gate: {passed}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("RC4 independent aggregate used as a development signal: True")
    print("RC4 holdout cases, predictions, and mismatches read: False")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
