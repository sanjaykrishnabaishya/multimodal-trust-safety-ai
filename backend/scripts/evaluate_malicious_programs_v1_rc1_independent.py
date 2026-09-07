"""Run one aggregate-only independent challenge against frozen RC1."""

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
    analyze_malicious_programs_v1_rc1,
    apply_malicious_programs_v1_rc1_fusion,
)


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "malicious-programs-v1-rc1"
CANDIDATE_DIRECTORY = (
    BACKEND / "storage" / "candidates" / CANDIDATE
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = (
    CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
)
DEVELOPMENT_PATH = (
    ROOT
    / "datasets"
    / "development"
    / "malicious_programs_v1_rc1"
    / "development.csv"
)
DEVELOPMENT_REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "malicious_programs"
    / "v1_rc1_development"
    / "report.json"
)
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "malicious_programs"
    / "v1_rc1_independent"
    / "aggregate_report.json"
)
LIVE_ARTIFACTS = {
    "source_snapshot/malicious_programs_v1_rc1_service.py": (
        BACKEND
        / "app"
        / "services"
        / "malicious_programs_v1_rc1_service.py"
    ),
    "policy_snapshot/malicious_programs_v1_rc1_policy.json": (
        BACKEND
        / "app"
        / "evidence"
        / "malicious_programs_v1_rc1_policy.json"
    ),
    "source_snapshot/evaluate_malicious_programs_v1_rc1_development.py": (
        BACKEND
        / "scripts"
        / "evaluate_malicious_programs_v1_rc1_development.py"
    ),
    "source_snapshot/freeze_malicious_programs_v1_rc1.py": (
        BACKEND / "scripts" / "freeze_malicious_programs_v1_rc1.py"
    ),
    "development/development.csv": DEVELOPMENT_PATH,
    "development_evidence/report.json": DEVELOPMENT_REPORT_PATH,
}
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


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(chunk)
    return digest.hexdigest()


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
    for index in range(60):
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


def _build_challenge() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    environments = (
        "a new office environment",
        "an independent user device",
        "a separate cloud tenant",
        "an unrelated workstation group",
    )
    _add_group(
        rows,
        group="fresh_malware_delivery",
        expected_category=MALICIOUS_CATEGORY,
        subjects=environments,
        templates=(
            "This account delivers the program to targets: malware intended for {subject}; challenge {index}.",
            "This download provides access to the trojan program for {subject}; challenge {index}.",
            "This post sends the binary containing spyware toward {subject}; challenge {index}.",
            "This attachment loads the program on victim devices: a computer virus affecting {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_ransomware_and_wipers",
        expected_category=MALICIOUS_CATEGORY,
        subjects=environments,
        templates=(
            "This download executes the ransomware that encrypts files for ransom in {subject}; challenge {index}.",
            "This post distributes the destructive wiper that destroys stored files in {subject}; challenge {index}.",
            "The incident contains malware; this attachment executes the program that wipes device data in {subject}; challenge {index}.",
            "This upload currently installs ransomware across {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_credential_and_information_theft",
        expected_category=MALICIOUS_CATEGORY,
        subjects=environments,
        templates=(
            "This post loads the program on victim devices: an information stealer for {subject}; challenge {index}.",
            "This attachment distributes the credential stealer that captures passwords in {subject}; challenge {index}.",
            "This download promotes installation of the keylogger on {subject}; challenge {index}.",
            "Evidence indicates this upload launches spyware that steals login credentials from {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_evasion_botnet_and_remote_control",
        expected_category=MALICIOUS_CATEGORY,
        subjects=environments,
        templates=(
            "This upload distributes the botnet agent that contacts command-and-control infrastructure from {subject}; challenge {index}.",
            "This download installs the rootkit that evades endpoint detection in {subject}; challenge {index}.",
            "This attachment currently deploys a malicious backdoor that opens unauthorized remote control of {subject}; challenge {index}.",
            "This account offers the program for download: a remote access trojan for {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_unresolved_artifacts",
        expected_category=UNCERTAIN_CATEGORY,
        subjects=environments,
        templates=(
            "This attachment contains a suspicious executable attachment whose capability is unclear in {subject}; challenge {index}.",
            "This upload has an encrypted archive attachment and the evidence is incomplete for {subject}; challenge {index}.",
            "This post contains an untrusted macro-enabled document whose intent cannot be established for {subject}; challenge {index}.",
            "This attachment is an unknown executable attachment and cannot be inspected safely for {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_defensive_operations",
        expected_category=NORMAL_CATEGORY,
        subjects=environments,
        templates=(
            "An incident response report for {subject} discusses a malicious payload and contains no executable payload; challenge {index}.",
            "A defensive malware analysis for {subject} says credentials are synthetic; challenge {index}.",
            "A forensic investigation of ransomware for {subject} contains no downloadable program; challenge {index}.",
            "A threat intelligence summary for {subject} says infrastructure addresses are redacted; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_authorized_research",
        expected_category=NORMAL_CATEGORY,
        subjects=environments,
        templates=(
            "Authorized security research about a rootkit uses an inert text-only example for {subject}; challenge {index}.",
            "An authorized penetration test for {subject} says no live target is involved; challenge {index}.",
            "An academic cybersecurity course about spyware contains no executable payload for {subject}; challenge {index}.",
            "Security patch validation for a malicious backdoor does not provide operational access to {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_benign_administration",
        expected_category=NORMAL_CATEGORY,
        subjects=environments,
        templates=(
            "A device management agent is approved for {subject}; challenge {index}.",
            "A package manager installation updates {subject}; challenge {index}.",
            "Approved backup encryption protects {subject}; challenge {index}.",
            "An ordinary browser extension is installed in {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_reporting_and_prevention",
        expected_category=NORMAL_CATEGORY,
        subjects=environments,
        templates=(
            "A public safety warning about ransomware describes prevention only for {subject}; challenge {index}.",
            "A court report mentions spyware and contains no downloadable program for {subject}; challenge {index}.",
            "A policy discussion names malware and uses an inert text-only example for {subject}; challenge {index}.",
            "A fictional story refers to a computer virus and contains no executable payload for {subject}; challenge {index}.",
        ),
    )
    _add_group(
        rows,
        group="fresh_dual_use_without_malicious_evidence",
        expected_category=NORMAL_CATEGORY,
        subjects=environments,
        templates=(
            "A network diagnostic utility checks connectivity in {subject}; boundary {index}.",
            "A system administrator reviews startup entries in {subject}; boundary {index}.",
            "A backup utility encrypts authorized archives in {subject}; boundary {index}.",
            "A testing framework automates browser actions in {subject}; boundary {index}.",
        ),
    )
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(60):
        owner, action = owners[index % len(owners)]
        rows.append(
            {
                "record_id": f"FRESH_OWNER-{index + 1:03d}",
                "group": "fresh_established_owner_isolation",
                "text": (
                    "This download installs the malware, while a verified "
                    f"{owner} decision already owns the case; challenge "
                    f"{index + 1}."
                ),
                "expected_category": owner,
                "existing_category": owner,
                "existing_action": action,
                "existing_review": True,
            }
        )
    _add_group(
        rows,
        group="fresh_lexical_boundaries",
        expected_category=NORMAL_CATEGORY,
        subjects=(
            "the malware section of a library index",
            "a ransomware conference title",
            "a spyware glossary heading",
            "a botnet term in a crossword",
        ),
        templates=(
            "The catalog lists {subject} without a file or operational claim; boundary {index}.",
            "A search result names {subject} without distribution evidence; boundary {index}.",
            "A benign document tag contains {subject}; boundary {index}.",
            "An ordinary index entry references {subject}; boundary {index}.",
        ),
    )
    return rows


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _verify_frozen_artifacts(
    manifest: dict[str, Any],
) -> bool:
    artifacts = {
        str(item["relative_path"]): str(item["sha256"])
        for item in manifest.get("artifacts", [])
    }
    return all(
        live_path.is_file()
        and (CANDIDATE_DIRECTORY / relative_path).is_file()
        and artifacts.get(relative_path) == _sha256(live_path)
        and artifacts.get(relative_path)
        == _sha256(CANDIDATE_DIRECTORY / relative_path)
        for relative_path, live_path in LIVE_ARTIFACTS.items()
    )


def main() -> None:
    if VERDICT_PATH.exists():
        raise FileExistsError(
            f"Independent verdict already exists: {VERDICT_PATH}"
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise RuntimeError("Candidate manifest is not an object.")
    frozen_verified = _verify_frozen_artifacts(manifest)

    with DEVELOPMENT_PATH.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as handle:
        development_hashes = {
            _text_hash(str(row["text"]))
            for row in csv.DictReader(handle)
        }
    challenge = _build_challenge()
    if len(challenge) != 720:
        raise RuntimeError(
            f"Unexpected challenge size: {len(challenge)}"
        )
    challenge_hashes = [
        _text_hash(str(record["text"])) for record in challenge
    ]
    unique_texts = len(set(challenge_hashes))
    overlap = len(set(challenge_hashes) & development_hashes)
    challenge_digest = hashlib.sha256(
        json.dumps(
            [
                {
                    "text_hash": text_hash,
                    "expected": record["expected_category"],
                    "group": record["group"],
                }
                for text_hash, record in zip(
                    challenge_hashes,
                    challenge,
                    strict=True,
                )
            ],
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    true_positive = true_negative = false_positive = false_negative = 0
    action_failures = category_failures = processing_errors = 0
    non_execution_failures = payload_storage_failures = 0
    authority_failures = 0
    groups: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "correct": 0}
    )

    for record in challenge:
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
                reason="Independent baseline.",
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
            action_failures += int(
                decision["action"] != expected_action
                or bool(decision["human_review_required"])
                != expected_review
                or decision["automatic_enforcement_allowed"] is not False
            )
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
        except Exception:
            processing_errors += 1

    accuracy = _ratio(
        true_positive + true_negative,
        len(challenge),
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
    gate = manifest["independent_gate_frozen_before_holdout"]
    gates = {
        "frozen_source_hashes_verified": frozen_verified,
        "zero_development_overlap": overlap == 0,
        "unique_challenge_records": unique_texts == len(challenge),
        "accuracy": accuracy >= gate["minimum_accuracy"],
        "malicious_precision": (
            precision >= gate["minimum_malicious_precision"]
        ),
        "malicious_recall": (
            recall >= gate["minimum_malicious_recall"]
        ),
        "safe_specificity": (
            specificity >= gate["minimum_safe_specificity"]
        ),
        "f1": f1 >= gate["minimum_f1"],
        "minimum_group_accuracy": (
            minimum_group_accuracy
            >= gate["minimum_group_accuracy"]
        ),
        "action_contract": action_failures == 0,
        "category_mix_contract": category_failures == 0,
        "non_execution_contract": non_execution_failures == 0,
        "payload_storage_contract": payload_storage_failures == 0,
        "authority_contract": authority_failures == 0,
        "processing_contract": processing_errors == 0,
    }
    passed = all(gates.values())
    report = {
        "candidate": CANDIDATE,
        "challenge_version": (
            "2026.08-malicious-programs-v1-rc1-independent"
        ),
        "challenge_sha256": challenge_digest,
        "records": len(challenge),
        "unique_texts": unique_texts,
        "positive_records": sum(
            record["expected_category"] == MALICIOUS_CATEGORY
            for record in challenge
        ),
        "negative_or_boundary_records": sum(
            record["expected_category"] != MALICIOUS_CATEGORY
            for record in challenge
        ),
        "development_overlap": overlap,
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
        "passed_synthetic_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "executable_payloads_used": False,
        "code_executed": False,
        "archives_unpacked": False,
        "payloads_stored": False,
        "credentials_stored": False,
        "live_infrastructure_stored": False,
        "external_provider_used": False,
        "candidate_may_be_modified_using_this_holdout": False,
        "synthetic_evidence_only": True,
        "external_real_world_accuracy": False,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    verdict = {
        key: value
        for key, value in report.items()
        if key != "group_results"
    }
    VERDICT_PATH.write_text(
        json.dumps(verdict, indent=2) + "\n",
        encoding="utf-8",
    )

    print("MALICIOUS PROGRAMS V1 RC1 INDEPENDENT CHALLENGE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Challenge SHA-256: {challenge_digest}")
    print(f"Records: {len(challenge)}")
    print(f"Positive records: {report['positive_records']}")
    print(
        "Negative/boundary records: "
        f"{report['negative_or_boundary_records']}"
    )
    print(f"Development overlap: {overlap}")
    for label, value in (
        ("Accuracy", accuracy),
        ("Malicious precision", precision),
        ("Malicious recall", recall),
        ("Safe specificity", specificity),
        ("F1", f1),
        ("Minimum group accuracy", minimum_group_accuracy),
    ):
        print(f"{label}: {value:.2%}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_failures}")
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
        "\nPassed synthetic independent readiness gate: "
        f"{passed}"
    )
    print(f"Eligible for guarded live integration: {passed}")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print(f"Report: {REPORT_PATH}")
    print(f"Verdict: {VERDICT_PATH}")
    print("No raw challenge text or individual predictions were stored.")
    print("No executable payload was used, opened, unpacked, or run.")
    print("This is synthetic evidence, not external accuracy.")
    print("This holdout may not be used to modify RC1.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
