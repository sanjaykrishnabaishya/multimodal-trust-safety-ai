"""Build and evaluate 600 safe synthetic Malicious Programs fixtures."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.malicious_programs_v1_rc1_service import (
    MALICIOUS_ACTION,
    MALICIOUS_CATEGORY,
    NORMAL_CATEGORY,
    UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_malicious_programs_v1_rc1,
    apply_malicious_programs_v1_rc1_fusion,
)


ROOT = Path(__file__).resolve().parents[2]
DATASET_DIRECTORY = (
    ROOT / "datasets" / "development" / "malicious_programs_v1_rc1"
)
DATASET_PATH = DATASET_DIRECTORY / "development.csv"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "malicious_programs"
    / "v1_rc1_development"
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
    "Cyberbullying & Harassment": "Refer to human review",
    "Misinformation & Fake News": "Refer to human review",
}


def _text_hash(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _add_group(
    rows: list[dict[str, Any]],
    *,
    group: str,
    expected_category: str,
    subjects: tuple[str, ...],
    templates: tuple[str, ...],
) -> None:
    for index in range(50):
        rows.append(
            {
                "record_id": f"{group.upper()}-{index + 1:03d}",
                "group": group,
                "text": templates[index % len(templates)].format(
                    subject=subjects[index % len(subjects)],
                    index=index + 1,
                ),
                "expected_category": expected_category,
                "existing_category": NORMAL_CATEGORY,
                "existing_action": "Allow",
                "existing_review": False,
            }
        )


def build_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    targets = (
        "selected workstations",
        "unwitting user devices",
        "a victim account",
        "a business network",
    )
    _add_group(
        rows,
        group="malware_distribution_and_installation",
        expected_category=MALICIOUS_CATEGORY,
        subjects=targets,
        templates=(
            "This upload distributes the malware to {subject}; inert case {index}.",
            "This post offers the program for download: a trojan program for {subject}; inert case {index}.",
            "This attachment sends the binary containing spyware to {subject}; inert case {index}.",
            "This account promotes installation of the computer virus on {subject}; inert case {index}.",
        ),
    )
    _add_group(
        rows,
        group="ransomware_and_destructive_deployment",
        expected_category=MALICIOUS_CATEGORY,
        subjects=targets,
        templates=(
            "This attachment currently deploys the ransomware that encrypts files for ransom on {subject}; inert case {index}.",
            "This upload launches the destructive wiper that wipes device data on {subject}; inert case {index}.",
            "This post delivers the program to targets: malware that destroys stored files on {subject}; inert case {index}.",
            "Evidence indicates this download installs the ransomware on {subject}; inert case {index}.",
        ),
    )
    _add_group(
        rows,
        group="credential_theft_and_spyware",
        expected_category=MALICIOUS_CATEGORY,
        subjects=targets,
        templates=(
            "This download sends the binary containing a credential-stealing program to {subject}; inert case {index}.",
            "This upload distributes the keylogger that captures passwords from {subject}; inert case {index}.",
            "This account provides access to the information stealer that steals login credentials from {subject}; inert case {index}.",
            "The incident contains spyware and this attachment runs the payload against {subject}; inert case {index}.",
        ),
    )
    _add_group(
        rows,
        group="persistence_evasion_and_remote_control",
        expected_category=MALICIOUS_CATEGORY,
        subjects=targets,
        templates=(
            "This post provides access to the malicious backdoor; evidence indicates it persists after restart on {subject}; inert case {index}.",
            "This upload distributes the rootkit that disables security tools on {subject}; inert case {index}.",
            "This attachment currently installs a botnet agent that joins devices to a botnet across {subject}; inert case {index}.",
            "This download offers the program for download: a remote access trojan for unauthorized remote control of {subject}; inert case {index}.",
        ),
    )
    _add_group(
        rows,
        group="uncertain_attachments_and_archives",
        expected_category=UNCERTAIN_CATEGORY,
        subjects=targets,
        templates=(
            "This attachment is an unknown executable attachment; purpose is unknown for {subject}; review case {index}.",
            "This upload contains a password-protected archive and its contents are unavailable for {subject}; review case {index}.",
            "This attachment contains an obfuscated script attachment whose capability is unclear for {subject}; review case {index}.",
            "This post references an unverified binary attachment, but authorization cannot be verified for {subject}; review case {index}.",
        ),
    )
    _add_group(
        rows,
        group="defensive_analysis_and_incident_response",
        expected_category=NORMAL_CATEGORY,
        subjects=targets,
        templates=(
            "A defensive malware analysis for {subject} contains no executable payload; safe case {index}.",
            "An incident response report about ransomware uses an inert text-only example for {subject}; safe case {index}.",
            "A forensic investigation of spyware says indicators are redacted for {subject}; safe case {index}.",
            "A threat intelligence summary about a botnet contains no downloadable program for {subject}; safe case {index}.",
        ),
    )
    _add_group(
        rows,
        group="detection_prevention_and_sandbox_reports",
        expected_category=NORMAL_CATEGORY,
        subjects=targets,
        templates=(
            "A sandbox analysis report describes malware prevention only and contains no executable payload for {subject}; safe case {index}.",
            "Detection engineering documentation says infrastructure addresses are redacted for {subject}; safe case {index}.",
            "Security awareness training about a keylogger contains no downloadable program for {subject}; safe case {index}.",
            "A malware prevention guide for {subject} does not provide operational access; safe case {index}.",
        ),
    )
    _add_group(
        rows,
        group="authorized_research_and_training",
        expected_category=NORMAL_CATEGORY,
        subjects=targets,
        templates=(
            "Authorized security research discusses ransomware and contains no executable payload for {subject}; safe case {index}.",
            "An authorized penetration test uses synthetic credentials and no live target is involved for {subject}; safe case {index}.",
            "An academic cybersecurity course mentions a trojan program but uses an inert text-only example for {subject}; safe case {index}.",
            "Security patch validation discusses a malicious backdoor and contains no downloadable program for {subject}; safe case {index}.",
        ),
    )
    _add_group(
        rows,
        group="benign_software_and_administration",
        expected_category=NORMAL_CATEGORY,
        subjects=targets,
        templates=(
            "A legitimate remote administration tool supports {subject}; ordinary case {index}.",
            "An antivirus update is installed on {subject}; ordinary case {index}.",
            "Approved backup encryption protects {subject}; ordinary case {index}.",
            "Software deployment by administrators updates {subject}; ordinary case {index}.",
        ),
    )
    _add_group(
        rows,
        group="safe_reporting_history_and_fiction",
        expected_category=NORMAL_CATEGORY,
        subjects=targets,
        templates=(
            "A news report discusses ransomware affecting {subject} and contains no downloadable program; safe case {index}.",
            "A historical account mentions a computer virus and uses an inert text-only example for {subject}; safe case {index}.",
            "A fictional story names spyware and contains no executable payload for {subject}; safe case {index}.",
            "A public safety warning about malware describes prevention only for {subject}; safe case {index}.",
        ),
    )
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(50):
        owner, action = owners[index % len(owners)]
        rows.append(
            {
                "record_id": f"ESTABLISHED_OWNER-{index + 1:03d}",
                "group": "established_category_owner_isolation",
                "text": (
                    "This upload distributes the malware, but an existing "
                    f"{owner} owner already controls the decision; owner "
                    f"case {index + 1}."
                ),
                "expected_category": owner,
                "existing_category": owner,
                "existing_action": action,
                "existing_review": True,
            }
        )
    _add_group(
        rows,
        group="lexical_and_capability_boundaries",
        expected_category=NORMAL_CATEGORY,
        subjects=(
            "a computer virus glossary",
            "a malware dictionary entry",
            "a ransomware policy heading",
            "a fictional botnet name",
        ),
        templates=(
            "The document indexes {subject} without distribution or capability evidence; lexical case {index}.",
            "An ordinary taxonomy includes {subject}; lexical case {index}.",
            "The search page lists {subject} as a topic; lexical case {index}.",
            "A benign note quotes {subject} without any attachment; lexical case {index}.",
        ),
    )
    return rows


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    hashes = [_text_hash(str(record["text"])) for record in records]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Duplicate development text detected.")

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
            analysis = analyze_malicious_programs_v1_rc1(
                str(record["text"]),
                ["text"],
            )
            decision = apply_malicious_programs_v1_rc1_fusion(
                category=str(record["existing_category"]),
                severity=(
                    "None"
                    if record["existing_category"] == NORMAL_CATEGORY
                    else "High"
                ),
                action=str(record["existing_action"]),
                confidence=0.70,
                human_review_required=bool(record["existing_review"]),
                reason="Development baseline.",
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

    accuracy = _ratio(
        true_positive + true_negative,
        len(records),
    )
    precision = _ratio(
        true_positive,
        true_positive + false_positive,
    )
    recall = _ratio(
        true_positive,
        true_positive + false_negative,
    )
    specificity = _ratio(
        true_negative,
        true_negative + false_positive,
    )
    f1 = _ratio(2 * precision * recall, precision + recall)
    group_results = {
        group: {
            **values,
            "accuracy": _ratio(
                values["correct"],
                values["records"],
            ),
        }
        for group, values in sorted(groups.items())
    }
    minimum_group_accuracy = min(
        values["accuracy"] for values in group_results.values()
    )
    gates = {
        "accuracy": accuracy >= 0.95,
        "malicious_precision": precision >= 0.95,
        "malicious_recall": recall >= 0.90,
        "safe_specificity": specificity >= 0.97,
        "f1": f1 >= 0.92,
        "minimum_group_accuracy": minimum_group_accuracy >= 0.90,
        "action_contract": action_failures == 0,
        "category_mix_contract": category_failures == 0,
        "non_execution_contract": non_execution_failures == 0,
        "payload_storage_contract": payload_storage_failures == 0,
        "authority_contract": authority_failures == 0,
        "processing_contract": processing_errors == 0,
    }
    return {
        "version": "2026.08-malicious-programs-v1-rc1-development",
        "records": len(records),
        "unique_texts": len(set(hashes)),
        "label_counts": dict(
            Counter(
                str(record["expected_category"])
                for record in records
            )
        ),
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
        "executable_payloads_used": False,
        "code_executed": False,
        "archives_unpacked": False,
        "credentials_used": False,
        "live_infrastructure_used": False,
        "external_provider_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "mismatches": mismatches,
    }


def main() -> None:
    records = build_records()
    if len(records) != 600:
        raise RuntimeError(
            f"Unexpected development size: {len(records)}"
        )
    result = evaluate(records)
    DATASET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(records[0]),
        )
        writer.writeheader()
        writer.writerows(records)

    report = {
        **result,
        "dataset_sha256": hashlib.sha256(
            DATASET_PATH.read_bytes()
        ).hexdigest(),
    }
    report.pop("mismatches")
    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    MISMATCH_PATH.write_text(
        json.dumps(result["mismatches"], indent=2) + "\n",
        encoding="utf-8",
    )

    print("MALICIOUS PROGRAMS V1 RC1 DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {result['records']}")
    print(f"Unique texts: {result['unique_texts']}")
    for label, key in (
        ("Accuracy", "accuracy"),
        ("Malicious precision", "malicious_precision"),
        ("Malicious recall", "malicious_recall"),
        ("Safe specificity", "safe_specificity"),
        ("F1", "f1"),
        ("Minimum group accuracy", "minimum_group_accuracy"),
    ):
        print(f"{label}: {result[key]:.2%}")
    print(f"Action failures: {result['action_contract_failures']}")
    print(f"Category failures: {result['category_mix_failures']}")
    print(f"Non-execution failures: {result['non_execution_failures']}")
    print(
        "Payload-storage failures: "
        f"{result['payload_storage_failures']}"
    )
    print(f"Authority failures: {result['authority_contract_failures']}")
    print(f"Processing errors: {result['processing_errors']}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, values in result["group_results"].items():
        print(
            f"{group}: {values['correct']}/{values['records']} "
            f"({values['accuracy']:.2%})"
        )
    print(
        "\nPassed development gate: "
        f"{result['passed_development_gate']}"
    )
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("Executable payloads used: False")
    print("Code executed or archives unpacked: False")
    print("External provider used: False")
    print("Connected to live moderation: False")
    print("This is synthetic policy evidence, not real-world accuracy.")
    if not result["passed_development_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
