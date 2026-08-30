"""Evaluate RC2 using new development data and only RC1 aggregate signals."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.malicious_programs_v1_rc1_service import (
    MALICIOUS_ACTION,
    MALICIOUS_CATEGORY,
    NORMAL_CATEGORY,
    UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
)
from app.services.malicious_programs_v2_rc2_service import (
    analyze_malicious_programs_v2_rc2,
    apply_malicious_programs_v2_rc2_fusion,
)


ROOT = Path(__file__).resolve().parents[2]
PRIOR_DEVELOPMENT_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "malicious_programs_v1_rc1"
    / "development.csv"
)
DATASET_DIRECTORY = (
    ROOT
    / "datasets"
    / "development"
    / "malicious_programs_v2_rc2"
)
DATASET_PATH = DATASET_DIRECTORY / "development.csv"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "malicious_programs"
    / "v2_rc2_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.json"
OWNER_ACTIONS = {
    "Child Exploitation": "Block and immediately escalate",
    "Illegal Activities": "Restrict and send for human review",
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Identity Theft & Impersonation": "Refer to human review",
    "Publishing Private Information": "Refer to human review",
    "Invasion of Privacy": "Restrict and send for human review",
    "Terrorism & Extremism": "Block and escalate",
    "Dangerous Content": "Remove and send for human review",
}


def _text_hash(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected: str,
    templates: tuple[str, ...],
) -> None:
    for index in range(60):
        rows.append(
            {
                "record_id": f"{group.upper()}-{index + 1:03d}",
                "group": group,
                "text": templates[index % len(templates)].format(
                    index=index + 1
                ),
                "expected_category": expected,
                "existing_category": NORMAL_CATEGORY,
                "existing_action": "Allow",
                "existing_review": False,
            }
        )


def build_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _add_group(
        rows,
        "reordered_ransomware_and_wiper_actions",
        MALICIOUS_CATEGORY,
        (
            "A hostile account installs ransomware on unrelated endpoints; RC2 development {index}.",
            "The operator deployed a destructive wiper to unrelated systems; RC2 development {index}.",
            "An untrusted post uploads malware for use on victim devices; RC2 development {index}.",
            "The campaign hosted a computer virus for download by targets; RC2 development {index}.",
        ),
    )
    _add_group(
        rows,
        "passive_and_object_first_delivery",
        MALICIOUS_CATEGORY,
        (
            "Ransomware is distributed by this account to victim devices; RC2 development {index}.",
            "A destructive wiper was delivered through this download to targets; RC2 development {index}.",
            "The malicious payload is being hosted for installation on user systems; RC2 development {index}.",
            "A trojan program was uploaded by the account for deployment on endpoints; RC2 development {index}.",
        ),
    )
    _add_group(
        rows,
        "separated_action_and_capability_evidence",
        MALICIOUS_CATEGORY,
        (
            "The account uploads an attachment for victims. Evidence identifies the attachment as malware; RC2 development {index}.",
            "The campaign delivers a program to targets. The program is ransomware; RC2 development {index}.",
            "The post hosts a binary for installation. Analysis identifies a credential stealer; RC2 development {index}.",
            "The user deploys an attachment across endpoints. It is a remote access trojan; RC2 development {index}.",
        ),
    )
    _add_group(
        rows,
        "safe_defensive_action_word_context",
        NORMAL_CATEGORY,
        (
            "A defensive malware analysis reports that attackers installed ransomware; it contains no executable payload; RC2 development {index}.",
            "An incident response report says a wiper was deployed; indicators are redacted; RC2 development {index}.",
            "A threat intelligence summary explains that spyware was distributed and contains no downloadable program; RC2 development {index}.",
            "Security awareness training says a trojan was uploaded and describes prevention only; RC2 development {index}.",
        ),
    )
    _add_group(
        rows,
        "benign_deployment_and_encryption",
        NORMAL_CATEGORY,
        (
            "Software deployment by administrators installs an operating system update; RC2 development {index}.",
            "Approved backup encryption protects authorized archives; RC2 development {index}.",
            "A package manager installation loads an approved library; RC2 development {index}.",
            "A device management agent deploys a signed configuration; RC2 development {index}.",
        ),
    )
    _add_group(
        rows,
        "uncertain_uninspected_artifacts",
        UNCERTAIN_CATEGORY,
        (
            "This attachment is an unverified binary attachment and its purpose is unknown; RC2 development {index}.",
            "This upload contains a password-protected archive whose capability is unclear; RC2 development {index}.",
            "This attachment has an obfuscated script attachment and cannot be inspected safely; RC2 development {index}.",
            "This post includes an unknown executable attachment with incomplete evidence; RC2 development {index}.",
        ),
    )
    _add_group(
        rows,
        "lexical_and_nonoperational_boundaries",
        NORMAL_CATEGORY,
        (
            "A library index files ransomware under cybersecurity history; RC2 development {index}.",
            "A glossary lists destructive wiper as a security term; RC2 development {index}.",
            "A conference schedule names malware analysis as a session; RC2 development {index}.",
            "A fictional title contains remote access trojan but no software; RC2 development {index}.",
        ),
    )
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(60):
        owner, action = owners[index % len(owners)]
        rows.append(
            {
                "record_id": f"RC2-OWNER-{index + 1:03d}",
                "group": "established_owner_isolation",
                "text": (
                    "The account deploys ransomware, but an existing "
                    f"{owner} decision owns the case; RC2 development "
                    f"{index + 1}."
                ),
                "expected_category": owner,
                "existing_category": owner,
                "existing_action": action,
                "existing_review": True,
            }
        )
    return rows


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    records = build_records()
    if len(records) != 480:
        raise RuntimeError(f"Unexpected development size: {len(records)}")
    with PRIOR_DEVELOPMENT_PATH.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        prior_hashes = {
            _text_hash(row["text"]) for row in csv.DictReader(handle)
        }
    hashes = [_text_hash(str(record["text"])) for record in records]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Duplicate RC2 development text detected.")
    overlap = len(set(hashes) & prior_hashes)
    if overlap:
        raise RuntimeError("Prior development text overlap detected.")

    true_positive = true_negative = false_positive = false_negative = 0
    action_failures = category_failures = processing_errors = 0
    non_execution_failures = payload_storage_failures = 0
    authority_failures = 0
    groups: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "correct": 0}
    )
    mismatches: list[dict[str, Any]] = []

    for record in records:
        group = str(record["group"])
        expected = str(record["expected_category"])
        groups[group]["records"] += 1
        try:
            analysis = analyze_malicious_programs_v2_rc2(
                str(record["text"]), ["text"]
            )
            decision = apply_malicious_programs_v2_rc2_fusion(
                category=str(record["existing_category"]),
                severity=(
                    "None"
                    if record["existing_category"] == NORMAL_CATEGORY
                    else "High"
                ),
                action=str(record["existing_action"]),
                confidence=0.70,
                human_review_required=bool(record["existing_review"]),
                reason="RC2 development baseline.",
                matched_signals=[],
                analysis=analysis,
            )
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action = str(record["existing_action"])
            expected_review = bool(record["existing_review"])
            if expected == MALICIOUS_CATEGORY:
                expected_action = MALICIOUS_ACTION
                expected_review = True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action = UNCERTAIN_ACTION
                expected_review = True
            action_ok = (
                decision["action"] == expected_action
                and bool(decision["human_review_required"])
                == expected_review
                and decision["automatic_enforcement_allowed"] is False
            )
            action_failures += int(not action_ok)
            category_failures += int(not correct)
            non_execution_failures += int(
                analysis["code_executed"] is not False
                or analysis["archive_unpacked"] is not False
            )
            payload_storage_failures += int(
                analysis["payload_stored"] is not False
                or analysis["credentials_stored"] is not False
                or analysis["live_infrastructure_stored"] is not False
            )
            authority_failures += int(
                analysis["external_provider_used"] is not False
                or analysis["external_transmission_allowed"] is not False
                or analysis["automatic_enforcement_allowed"] is not False
            )
            expected_positive = expected == MALICIOUS_CATEGORY
            predicted_positive = predicted == MALICIOUS_CATEGORY
            if expected_positive and predicted_positive:
                true_positive += 1
            elif expected_positive:
                false_negative += 1
            elif predicted_positive:
                false_positive += 1
            else:
                true_negative += 1
            if not correct or not action_ok:
                mismatches.append(
                    {
                        "record_id": record["record_id"],
                        "group": group,
                        "expected": expected,
                        "predicted": predicted,
                        "status": analysis["fusion_status"],
                    }
                )
        except Exception as error:
            processing_errors += 1
            mismatches.append(
                {
                    "record_id": record["record_id"],
                    "error": type(error).__name__,
                }
            )

    accuracy = _ratio(true_positive + true_negative, len(records))
    precision = _ratio(
        true_positive, true_positive + false_positive
    )
    recall = _ratio(true_positive, true_positive + false_negative)
    specificity = _ratio(
        true_negative, true_negative + false_positive
    )
    f1 = _ratio(2 * precision * recall, precision + recall)
    group_results = {
        group: {
            **values,
            "accuracy": _ratio(values["correct"], values["records"]),
        }
        for group, values in sorted(groups.items())
    }
    minimum_group_accuracy = min(
        values["accuracy"] for values in group_results.values()
    )
    gates = {
        "accuracy": accuracy >= 0.95,
        "malicious_precision": precision >= 0.97,
        "malicious_recall": recall >= 0.95,
        "safe_specificity": specificity >= 0.99,
        "f1": f1 >= 0.96,
        "minimum_group_accuracy": minimum_group_accuracy >= 0.92,
        "action_contract": action_failures == 0,
        "category_mix_contract": category_failures == 0,
        "non_execution_contract": non_execution_failures == 0,
        "payload_storage_contract": payload_storage_failures == 0,
        "authority_contract": authority_failures == 0,
        "processing_contract": processing_errors == 0,
    }
    report = {
        "version": "2026.08-malicious-programs-v2-rc2-development",
        "records": len(records),
        "unique_texts": len(set(hashes)),
        "prior_development_overlap": overlap,
        "accuracy": accuracy,
        "malicious_precision": precision,
        "malicious_recall": recall,
        "safe_specificity": specificity,
        "f1": f1,
        "minimum_group_accuracy": minimum_group_accuracy,
        "false_positives": false_positive,
        "false_negatives": false_negative,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_failures,
        "non_execution_failures": non_execution_failures,
        "payload_storage_failures": payload_storage_failures,
        "authority_contract_failures": authority_failures,
        "processing_errors": processing_errors,
        "group_results": group_results,
        "gates": gates,
        "passed_development_gate": all(gates.values()),
        "rc1_aggregate_result_used": True,
        "rc1_holdout_cases_read": False,
        "rc1_individual_predictions_read": False,
        "rc1_mismatches_read": False,
        "executable_payloads_used": False,
        "code_executed": False,
        "archives_unpacked": False,
        "payloads_stored": False,
        "credentials_used": False,
        "live_infrastructure_used": False,
        "external_provider_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    DATASET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    report["dataset_sha256"] = hashlib.sha256(
        DATASET_PATH.read_bytes()
    ).hexdigest()
    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    MISMATCH_PATH.write_text(
        json.dumps(mismatches, indent=2) + "\n", encoding="utf-8"
    )

    print("MALICIOUS PROGRAMS V2 RC2 DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {len(records)}")
    print(f"Prior development overlap: {overlap}")
    for label, value in (
        ("Accuracy", accuracy),
        ("Malicious precision", precision),
        ("Malicious recall", recall),
        ("Safe specificity", specificity),
        ("F1", f1),
        ("Minimum group accuracy", minimum_group_accuracy),
    ):
        print(f"{label}: {value:.2%}")
    print(f"Action failures: {action_failures}")
    print(f"Category failures: {category_failures}")
    print(f"Non-execution failures: {non_execution_failures}")
    print(f"Payload-storage failures: {payload_storage_failures}")
    print(f"Authority failures: {authority_failures}")
    print(f"Processing errors: {processing_errors}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, values in group_results.items():
        print(
            f"{group}: {values['correct']}/{values['records']} "
            f"({values['accuracy']:.2%})"
        )
    print(
        "\nPassed development gate: "
        f"{report['passed_development_gate']}"
    )
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("RC1 aggregate result used: True")
    print("RC1 holdout cases or predictions read: False")
    print("Executable payloads used or executed: False")
    print("Connected to live moderation: False")
    print("This is synthetic policy evidence, not real-world accuracy.")
    if not report["passed_development_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
