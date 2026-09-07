"""Run a new aggregate-only independent challenge against frozen RC2."""

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
BACKEND = ROOT / "backend"
CANDIDATE = "malicious-programs-v2-rc2"
CANDIDATE_DIRECTORY = (
    BACKEND / "storage" / "candidates" / CANDIDATE
)
RC1_DIRECTORY = (
    BACKEND
    / "storage"
    / "candidates"
    / "malicious-programs-v1-rc1"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = (
    CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
)
DEVELOPMENT_PATHS = (
    ROOT
    / "datasets"
    / "development"
    / "malicious_programs_v1_rc1"
    / "development.csv",
    ROOT
    / "datasets"
    / "development"
    / "malicious_programs_v2_rc2"
    / "development.csv",
)
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "malicious_programs"
    / "v2_rc2_independent"
    / "aggregate_report.json"
)
LIVE_ARTIFACTS = {
    "source_snapshot/malicious_programs_v2_rc2_service.py": (
        BACKEND
        / "app"
        / "services"
        / "malicious_programs_v2_rc2_service.py"
    ),
    "policy_snapshot/malicious_programs_v2_rc2_policy.json": (
        BACKEND
        / "app"
        / "evidence"
        / "malicious_programs_v2_rc2_policy.json"
    ),
    "source_snapshot/evaluate_malicious_programs_v2_rc2_development.py": (
        BACKEND
        / "scripts"
        / "evaluate_malicious_programs_v2_rc2_development.py"
    ),
    "source_snapshot/freeze_malicious_programs_v2_rc2.py": (
        BACKEND / "scripts" / "freeze_malicious_programs_v2_rc2.py"
    ),
    "development/development.csv": DEVELOPMENT_PATHS[1],
    "development_evidence/report.json": (
        ROOT
        / "reports"
        / "evaluation"
        / "malicious_programs"
        / "v2_rc2_development"
        / "report.json"
    ),
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
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _text_hash(text: str) -> str:
    normalized = " ".join(text.casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected: str,
    templates: tuple[str, ...],
) -> None:
    for index in range(80):
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


def _build_challenge() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    _add_group(
        rows,
        "novel_inflected_malware_delivery",
        MALICIOUS_CATEGORY,
        (
            "An account is hosting malware so unrelated users can obtain it; RC2 challenge {index}.",
            "A trojan program is delivered by the upload to victim endpoints; RC2 challenge {index}.",
            "The post published a computer virus for installation by targets; RC2 challenge {index}.",
            "Malicious payload files were uploaded for deployment on other devices; RC2 challenge {index}.",
        ),
    )
    _add_group(
        rows,
        "novel_passive_ransomware_and_wipers",
        MALICIOUS_CATEGORY,
        (
            "Ransomware was published by the operator for victim systems; RC2 challenge {index}.",
            "A destructive wiper is hosted for installation on unrelated machines; RC2 challenge {index}.",
            "The campaign is distributing malware that wipes device data; RC2 challenge {index}.",
            "Ransomware files are being delivered to selected endpoints; RC2 challenge {index}.",
        ),
    )
    _add_group(
        rows,
        "novel_credential_theft_delivery",
        MALICIOUS_CATEGORY,
        (
            "A keylogger was sent by the account to victim devices; RC2 challenge {index}.",
            "The credential stealer is hosted for download by unrelated users; RC2 challenge {index}.",
            "An information stealer was uploaded for installation on endpoints; RC2 challenge {index}.",
            "The post delivers spyware that captures passwords from victims; RC2 challenge {index}.",
        ),
    )
    _add_group(
        rows,
        "novel_remote_control_and_evasion",
        MALICIOUS_CATEGORY,
        (
            "A rootkit is installed by this campaign to disable security tools; RC2 challenge {index}.",
            "The botnet agent was distributed for deployment across user devices; RC2 challenge {index}.",
            "A malicious backdoor is being hosted for unauthorized remote control; RC2 challenge {index}.",
            "The remote access trojan was delivered to unrelated workstations; RC2 challenge {index}.",
        ),
    )
    _add_group(
        rows,
        "novel_uncertain_artifacts",
        UNCERTAIN_CATEGORY,
        (
            "This upload has an encrypted archive attachment whose provenance is unknown; RC2 challenge {index}.",
            "This attachment contains an untrusted macro-enabled document and the evidence is incomplete; RC2 challenge {index}.",
            "This post has a suspicious executable attachment whose intent cannot be established; RC2 challenge {index}.",
            "This attachment includes an obfuscated script attachment with unavailable contents; RC2 challenge {index}.",
        ),
    )
    _add_group(
        rows,
        "novel_defensive_action_context",
        NORMAL_CATEGORY,
        (
            "A defensive malware analysis says ransomware was installed; it contains no executable payload; RC2 challenge {index}.",
            "An incident response report states a wiper was delivered; indicators are redacted; RC2 challenge {index}.",
            "A sandbox analysis report notes spyware was uploaded and contains no downloadable program; RC2 challenge {index}.",
            "Detection engineering records that malware was distributed and describes prevention only; RC2 challenge {index}.",
        ),
    )
    _add_group(
        rows,
        "novel_benign_action_context",
        NORMAL_CATEGORY,
        (
            "An operating system update is distributed by approved administrators; RC2 challenge {index}.",
            "A device management agent was installed on company-owned machines; RC2 challenge {index}.",
            "Approved backup encryption is deployed for authorized records; RC2 challenge {index}.",
            "An accessibility automation script was uploaded to a personal workspace; RC2 challenge {index}.",
        ),
    )
    _add_group(
        rows,
        "novel_reporting_fiction_and_history",
        NORMAL_CATEGORY,
        (
            "A news report says malware was hosted and contains no downloadable program; RC2 challenge {index}.",
            "A historical account says a computer virus was distributed and uses an inert text-only example; RC2 challenge {index}.",
            "A fictional story says ransomware was installed and contains no executable payload; RC2 challenge {index}.",
            "A public safety warning says spyware was uploaded and describes prevention only; RC2 challenge {index}.",
        ),
    )
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(80):
        owner, action = owners[index % len(owners)]
        rows.append(
            {
                "record_id": f"NOVEL-OWNER-{index + 1:03d}",
                "group": "novel_established_owner_isolation",
                "text": (
                    "Ransomware was distributed, but a verified "
                    f"{owner} decision already owns this case; RC2 "
                    f"challenge {index + 1}."
                ),
                "expected_category": owner,
                "existing_category": owner,
                "existing_action": action,
                "existing_review": True,
            }
        )
    _add_group(
        rows,
        "novel_lexical_and_title_boundaries",
        NORMAL_CATEGORY,
        (
            "A museum exhibition title includes Computer Virus without software; RC2 challenge {index}.",
            "A bibliography heading says Ransomware Studies without a file; RC2 challenge {index}.",
            "A dictionary page contains the term credential stealer without operational evidence; RC2 challenge {index}.",
            "A board-game character is named Botnet Agent and no program is present; RC2 challenge {index}.",
        ),
    )
    return rows


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _verify_frozen_artifacts(manifest: dict[str, Any]) -> bool:
    artifacts = {
        str(item["relative_path"]): str(item["sha256"])
        for item in manifest.get("artifacts", [])
    }
    own_hashes = all(
        live_path.is_file()
        and (CANDIDATE_DIRECTORY / relative_path).is_file()
        and artifacts.get(relative_path) == _sha256(live_path)
        and artifacts.get(relative_path)
        == _sha256(CANDIDATE_DIRECTORY / relative_path)
        for relative_path, live_path in LIVE_ARTIFACTS.items()
    )
    dependency = manifest["dependencies"]["malicious-programs-v1-rc1"]
    return own_hashes and all(
        (
            (
                dependency["manifest_sha256"]
                == _sha256(RC1_DIRECTORY / "manifest.json")
            ),
            (
                dependency["verdict_sha256"]
                == _sha256(
                    RC1_DIRECTORY
                    / "independent_evaluation_verdict.json"
                )
            ),
            (
                dependency["service_snapshot_sha256"]
                == _sha256(
                    RC1_DIRECTORY
                    / "source_snapshot"
                    / "malicious_programs_v1_rc1_service.py"
                )
            ),
        )
    )


def main() -> None:
    if VERDICT_PATH.exists():
        raise FileExistsError(
            f"Independent verdict already exists: {VERDICT_PATH}"
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    frozen_verified = _verify_frozen_artifacts(manifest)
    development_hashes: set[str] = set()
    for path in DEVELOPMENT_PATHS:
        with path.open("r", encoding="utf-8", newline="") as handle:
            development_hashes.update(
                _text_hash(row["text"])
                for row in csv.DictReader(handle)
            )

    challenge = _build_challenge()
    if len(challenge) != 800:
        raise RuntimeError(f"Unexpected challenge size: {len(challenge)}")
    hashes = [_text_hash(str(record["text"])) for record in challenge]
    unique_texts = len(set(hashes))
    overlap = len(set(hashes) & development_hashes)
    challenge_digest = hashlib.sha256(
        json.dumps(
            [
                {
                    "text_hash": text_hash,
                    "expected": record["expected_category"],
                    "group": record["group"],
                }
                for text_hash, record in zip(
                    hashes, challenge, strict=True
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
                reason="RC2 independent baseline.",
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

    accuracy = _ratio(true_positive + true_negative, len(challenge))
    precision = _ratio(true_positive, true_positive + false_positive)
    recall = _ratio(true_positive, true_positive + false_negative)
    specificity = _ratio(true_negative, true_negative + false_positive)
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
    gate = manifest["independent_gate_frozen_before_holdout"]
    gates = {
        "frozen_source_and_dependencies_verified": frozen_verified,
        "zero_development_overlap": overlap == 0,
        "unique_challenge_records": unique_texts == len(challenge),
        "accuracy": accuracy >= gate["minimum_accuracy"],
        "malicious_precision": (
            precision >= gate["minimum_malicious_precision"]
        ),
        "malicious_recall": recall >= gate["minimum_malicious_recall"],
        "safe_specificity": (
            specificity >= gate["minimum_safe_specificity"]
        ),
        "f1": f1 >= gate["minimum_f1"],
        "minimum_group_accuracy": (
            minimum_group_accuracy >= gate["minimum_group_accuracy"]
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
            "2026.08-malicious-programs-v2-rc2-independent"
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
        "earlier_holdout_files_read": False,
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
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    verdict = {
        key: value
        for key, value in report.items()
        if key != "group_results"
    }
    VERDICT_PATH.write_text(
        json.dumps(verdict, indent=2) + "\n", encoding="utf-8"
    )

    print("MALICIOUS PROGRAMS V2 RC2 INDEPENDENT CHALLENGE")
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
    print("Earlier holdout files, cases, and predictions were not read.")
    print("No executable payload was used, opened, unpacked, or run.")
    print("This is synthetic evidence, not external accuracy.")
    print("This holdout may not be used to modify RC2.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
