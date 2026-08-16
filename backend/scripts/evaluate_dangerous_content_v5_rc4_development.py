from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.dangerous_content_v5_rc4_service import (
    analyze_dangerous_content_v5_rc4,
)


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v5_rc4_policy_recovery_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
DATASET_DIRECTORY = (
    ROOT_DIRECTORY / "datasets" / "development" / "dangerous_content_v5_rc4"
)
DATASET_PATH = DATASET_DIRECTORY / "development.csv"
MANIFEST_PATH = DATASET_DIRECTORY / "manifest.json"
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


ADVOCACY_TEMPLATES = [
    "The post urges ordinary users to try {concept} without safeguards.",
    "Viewers are encouraged to imitate {concept} despite the danger.",
    "A creator challenges amateurs to reproduce {concept} for entertainment.",
    "The message pressures people to attempt {concept} and ignore the physical risk.",
    "Followers are invited to copy {concept} outside professional supervision.",
]

PASSIVE_ADVOCACY_TEMPLATES = [
    "Trying {concept} is presented as something the audience should do.",
    "An amateur is dared by the uploader to perform {concept} despite the injury risk.",
    "Copy {concept}, the creator tells untrained followers while dismissing safety.",
    "The public is challenged to recreate {concept} even though it is hazardous.",
    "Participation in {concept} is encouraged as a reckless online challenge.",
]

SAFE_TEMPLATES = [
    "A safety notice warns people not to try {concept}.",
    "The report condemns {concept} and explains prevention.",
    "An educator discourages anyone from copying {concept}.",
    "A news report describes {concept} without endorsing it.",
    "The article says viewers must avoid {concept} because it is dangerous.",
]

PROFESSIONAL_TEMPLATES = [
    "A qualified team examines {concept} inside a controlled facility.",
    "Certified professionals manage {concept} during an authorized exercise.",
    "A controlled test studies {concept} behind protective barriers.",
    "Licensed operators discuss {concept} with formal safeguards in place.",
    "The documentary shows trained specialists handling {concept} under supervision.",
]

BENIGN_TEMPLATES = [
    "A teacher encourages a beginner to try {concept}.",
    "Students are challenged to practise {concept} as a harmless lesson.",
    "The club invites newcomers to repeat {concept} for skill development.",
    "A friendly creator asks viewers to copy {concept} as an ordinary hobby.",
    "Participants are encouraged to attempt {concept} at their normal learning pace.",
]

NEUTRAL_TEMPLATES = [
    "A fictional story depicts {concept} but does not encourage imitation.",
    "A historical account neutrally describes {concept}.",
    "An academic study analyzes injuries connected with {concept}.",
    "A museum exhibit explains the history of {concept} without an actionable method.",
    "An incident review discusses {concept} only to understand what occurred.",
]


def build_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    add_group(
        rows,
        "direct_policy_advocacy",
        True,
        [
            "a perilous stunt near an exposed edge",
            "unsafe interference with moving machinery",
            "a hazardous indoor fume activity",
            "reckless entry into fast water",
            "an act likely to cause major property destruction",
            "contact with energized equipment",
            "a prank that could seriously injure a bystander",
            "an uncontrolled fire activity near occupied property",
        ],
        ADVOCACY_TEMPLATES,
    )
    add_group(
        rows,
        "passive_and_mixed_order_advocacy",
        True,
        [
            "an unsafe leap at height",
            "tampering with a protective machine guard",
            "an unprotected corrosive-material activity",
            "a reckless moving-vehicle stunt",
            "standing beneath unstable debris",
            "an uncontrolled pressure experiment",
            "entering a dangerous restricted structure",
            "an act that exposes another person to bodily harm",
        ],
        PASSIVE_ADVOCACY_TEMPLATES,
    )
    add_group(
        rows,
        "warning_reporting_and_prevention",
        False,
        [
            "an unsafe electrical stunt",
            "a dangerous rooftop challenge",
            "a hazardous household experiment",
            "a reckless vehicle trend",
            "an act that could destroy property",
            "a prank that risks bodily harm",
            "entry into flood water",
            "interference with active machinery",
        ],
        SAFE_TEMPLATES,
    )
    add_group(
        rows,
        "professional_and_controlled_context",
        False,
        [
            "high-energy equipment failure",
            "hazardous vapor containment",
            "a simulated elevated rescue",
            "structural load failure",
            "electrical isolation",
            "a permitted heat test",
            "moving machinery risk",
            "an emergency transport exercise",
        ],
        PROFESSIONAL_TEMPLATES,
    )
    add_group(
        rows,
        "benign_encouragement_boundary",
        False,
        [
            "a simple handwriting exercise",
            "a normal painting technique",
            "a beginner vocabulary game",
            "an ordinary photography task",
            "a harmless theatre rehearsal",
            "a basic spreadsheet exercise",
            "a routine singing lesson",
            "a beginner chess puzzle",
        ],
        BENIGN_TEMPLATES,
    )
    add_group(
        rows,
        "neutral_history_fiction_and_research",
        False,
        [
            "a past industrial accident",
            "a character crossing an unstable bridge",
            "an old transport incident",
            "a failed stunt in a drama",
            "historical fire damage",
            "an electrical safety incident",
            "a structural collapse from the past",
            "an unsafe challenge reported by researchers",
        ],
        NEUTRAL_TEMPLATES,
    )

    owner_cases = [
        ("Violent Content", "directly threatens to assault a named person"),
        ("Publishing Private Information", "publishes a private address"),
        ("Spam, Scam & Phishing", "impersonates support and demands a secret code"),
        ("Cyberbullying & Harassment", "repeatedly intimidates one target"),
        ("Hate Speech & Discrimination", "attacks a protected identity group"),
        ("Religiously Offensive Content", "attacks a revered sacred figure"),
        ("Terrorism & Extremism", "requests support for an extremist organization"),
        ("Misinformation & Fake News", "makes a checkable public factual claim"),
    ]
    for owner_index, (owner, description) in enumerate(owner_cases, start=1):
        for template_index, template in enumerate(
            [
                "The content {description}.",
                "This established-category case {description}.",
                "The primary signal {description}.",
                "A post clearly {description}.",
                "The message {description}.",
            ],
            start=1,
        ):
            text = template.format(description=description)
            rows.append(
                {
                    "record_id": f"CATEGORY-OWNER-{owner_index:02d}-{template_index:02d}",
                    "group": "established_category_isolation",
                    "expected_dangerous": False,
                    "existing_category": owner,
                    "text": text,
                    "text_sha256": text_hash(text),
                }
            )
    return rows


def read_development_hashes() -> set[str]:
    hashes: set[str] = set()
    for filename in ("train.csv", "validation.csv"):
        path = RC3_CANDIDATE_DIRECTORY / "development" / filename
        with path.open("r", encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                hashes.add(row["text_sha256"])
    return hashes


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    rows = build_rows()
    if len(rows) != 280:
        raise RuntimeError(f"Unexpected development record count: {len(rows)}")
    hashes = [row["text_sha256"] for row in rows]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Duplicate development text detected.")
    overlap = set(hashes) & read_development_hashes()
    if overlap:
        raise RuntimeError("RC3/RC4 development text overlap detected.")

    tp = tn = fp = fn = 0
    action_contract_failures = 0
    category_mix_failures = 0
    processing_errors = 0
    direct_recoveries = 0
    rc3_semantic_accepts = 0
    group_results: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "correct": 0}
    )

    for row in rows:
        group_results[row["group"]]["records"] += 1
        try:
            result = analyze_dangerous_content_v5_rc4(
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
            if result.get("direct_advocacy_recovery_used") is True:
                direct_recoveries += 1
            if result.get("dangerous_content_v5_rc4_status") == "rc3_semantic_path_applied":
                rc3_semantic_accepts += 1
            if result.get("automatic_enforcement_allowed") is not False:
                action_contract_failures += 1
            if predicted and (
                result.get("action") != DANGEROUS_ACTION
                or result.get("human_review_required") is not True
            ):
                action_contract_failures += 1
            if result.get("category") not in (None, DANGEROUS_CATEGORY):
                category_mix_failures += 1
            if row["existing_category"] not in ("Normal/Ignore", "Uncertain") and predicted:
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
        "candidate": "dangerous-content-v5-rc4-development",
        "records": records,
        "source": "synthetic published-policy concepts",
        "rc3_development_text_overlap": len(overlap),
        "rc3_independent_aggregate_used_as_development_signal": True,
        "rc3_independent_aggregate_signal": {
            "dangerous_precision": 0.9804,
            "dangerous_recall": 0.8333,
            "minimum_group_accuracy": 0.80,
        },
        "rc3_holdout_cases_read": False,
        "rc3_holdout_predictions_or_mismatches_read": False,
        "external_or_restricted_data_used": False,
        "actionable_harm_instructions_stored": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

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
        "rc3_semantic_accepts": rc3_semantic_accepts,
        "direct_advocacy_recoveries": direct_recoveries,
        "action_contract_failures": action_contract_failures,
        "category_mix_failures": category_mix_failures,
        "processing_errors": processing_errors,
        "group_results": aggregate_groups,
        "passed_development_gate": passed,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("DANGEROUS CONTENT V5 RC4 POLICY-RECOVERY DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"RC3 development overlap: {len(overlap)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Dangerous precision: {precision * 100:.2f}%")
    print(f"Dangerous recall: {recall * 100:.2f}%")
    print(f"Safe specificity: {specificity * 100:.2f}%")
    print(f"F1: {f1 * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"RC3 semantic accepts: {rc3_semantic_accepts}")
    print(f"Direct advocacy recoveries: {direct_recoveries}")
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
    print("RC3 independent aggregate used as a development signal: True")
    print("RC3 holdout cases, predictions, and mismatches read: False")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
