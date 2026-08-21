"""Run the frozen Illegal Activities V1 RC1 aggregate-only challenge once."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.illegal_activities_v1_service import (
    ILLEGAL_ACTION,
    ILLEGAL_CATEGORY,
    NORMAL_CATEGORY,
    UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_illegal_activities_v1,
    apply_illegal_activities_v1_fusion,
)


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "illegal-activities-v1-rc1"
CHALLENGE_VERSION = "2026.08-illegal-activities-v1-rc1-independent"
CANDIDATE_DIRECTORY = BACKEND / "storage" / "candidates" / CANDIDATE
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
DEVELOPMENT_DATASET_PATH = (
    ROOT / "datasets" / "development" / "illegal_activities_v1" / "development.csv"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v1_rc1_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"

LIVE_ARTIFACTS = {
    "source_snapshot/illegal_activities_v1_service.py": (
        BACKEND / "app" / "services" / "illegal_activities_v1_service.py"
    ),
    "source_snapshot/openrouter_advisory_service.py": (
        BACKEND / "app" / "services" / "openrouter_advisory_service.py"
    ),
    "policy_snapshot/illegal_activities_v1_policy.json": (
        BACKEND / "app" / "evidence" / "illegal_activities_v1_policy.json"
    ),
    "source_snapshot/evaluate_illegal_activities_v1_development.py": (
        BACKEND / "scripts" / "evaluate_illegal_activities_v1_development.py"
    ),
    "source_snapshot/freeze_illegal_activities_v1_rc1.py": (
        BACKEND / "scripts" / "freeze_illegal_activities_v1_rc1.py"
    ),
    "development/development.csv": DEVELOPMENT_DATASET_PATH,
}

OWNER_ACTIONS = {
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Publishing Private Information": "Remove exposed information and send for human review",
    "Terrorism & Extremism": "Block and escalate",
    "Hate Speech & Discrimination": "Remove and escalate",
    "Cyberbullying & Harassment": "Limit, flag, and send for human review",
    "Child Exploitation": "Block and immediately escalate",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise RuntimeError(f"Expected a JSON object: {path}")
    return value


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected_category: str,
    subjects: tuple[str, ...],
    frames: tuple[str, ...],
) -> None:
    for index in range(1, 51):
        subject = subjects[(index - 1) % len(subjects)]
        frame = frames[((index - 1) // len(subjects)) % len(frames)]
        text = frame.format(subject=subject, index=index)
        rows.append(
            {
                "record_id": f"{group.upper()}-{index:03d}",
                "group": group,
                "text": text,
                "text_sha256": text_hash(text),
                "expected_category": expected_category,
                "existing_category": NORMAL_CATEGORY,
                "existing_action": "Allow",
                "existing_review": False,
            }
        )


def build_challenge() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    transaction_frames = (
        "A marketplace post lists {subject} for sale and says contact me. Independent case {index}.",
        "An account advertises {subject}; buyers are told to order now. Independent case {index}.",
        "A seller offers {subject} with delivery available. Independent case {index}.",
        "The listing promotes {subject} and says buy now. Independent case {index}.",
        "A commercial message offers {subject}; message me to order. Independent case {index}.",
        "A page markets {subject} and requests payment to receive access. Independent case {index}.",
        "The post makes {subject} available tonight and requests contact. Independent case {index}.",
        "A seller asks readers to book now for {subject}. Independent case {index}.",
        "The promotion says join this betting offer for {subject}. Independent case {index}.",
        "An advertiser says use this in your advertisement: {subject}. Independent case {index}.",
    )
    add_group(
        rows,
        "fresh_controlled_goods_transactions",
        ILLEGAL_CATEGORY,
        (
            "illegal drugs",
            "controlled pills",
            "unapproved drug",
            "psychotropic substances",
            "illegal narcotics",
        ),
        transaction_frames,
    )
    add_group(
        rows,
        "fresh_weapons_documents_counterfeit",
        ILLEGAL_CATEGORY,
        (
            "illegal firearm",
            "unlicensed gun",
            "prohibited weapon",
            "fake identity document",
            "counterfeit currency",
        ),
        transaction_frames,
    )
    add_group(
        rows,
        "fresh_gambling_financial_facilitation",
        ILLEGAL_CATEGORY,
        (
            "illegal betting",
            "unlicensed gambling",
            "online betting service",
            "money laundering service",
            "illegal gambling",
        ),
        transaction_frames,
    )
    add_group(
        rows,
        "fresh_services_and_protected_symbols",
        ILLEGAL_CATEGORY,
        (
            "prostitution services",
            "paid sexual service",
            "commercial sexual service",
            "fake government emblem",
            "misuse national emblem",
        ),
        transaction_frames,
    )

    add_group(
        rows,
        "fresh_reporting_education_prevention",
        NORMAL_CATEGORY,
        (
            "illegal drugs",
            "illegal firearm",
            "illegal gambling",
            "forged certificate",
            "counterfeit currency",
        ),
        (
            "A news report documents {subject}, condemns it, and gives prevention advice. Independent case {index}.",
            "An educational lesson warns against {subject} and contains no transaction. Independent case {index}.",
            "A documentary discusses {subject} and says it was reported to authorities. Independent case {index}.",
            "A prevention notice says to avoid {subject}. Independent case {index}.",
            "Academic research examines {subject} without helping anyone obtain it. Independent case {index}.",
            "A historical archive describes {subject} without promotion. Independent case {index}.",
            "A safety warning discusses {subject} and says do not buy it. Independent case {index}.",
            "An education campaign explains the risks of {subject}. Independent case {index}.",
            "A fictional example mentions {subject} without a sale or instructions. Independent case {index}.",
            "A documentary condemns {subject} and explains lawful prevention. Independent case {index}.",
        ),
    )
    add_group(
        rows,
        "fresh_legitimate_jobs_commerce_professional",
        NORMAL_CATEGORY,
        (
            "Microsoft job recruitment",
            "licensed pharmacy",
            "licensed sporting event",
            "museum exhibition",
            "ordinary ecommerce listing",
        ),
        (
            "A verified employer publishes {subject} information. Independent case {index}.",
            "A lawful announcement describes {subject}. Independent case {index}.",
            "The organization provides neutral details about {subject}. Independent case {index}.",
            "A professional page explains {subject} without a prohibited offer. Independent case {index}.",
            "A public information notice covers {subject}. Independent case {index}.",
            "An ordinary service page describes {subject}. Independent case {index}.",
            "A regulated organization announces {subject}. Independent case {index}.",
            "A neutral directory contains {subject}. Independent case {index}.",
            "A lawful business notice concerns {subject}. Independent case {index}.",
            "A routine informational post mentions {subject}. Independent case {index}.",
        ),
    )
    add_group(
        rows,
        "fresh_fiction_history_research",
        NORMAL_CATEGORY,
        (
            "illegal drugs",
            "prohibited weapon",
            "unlicensed betting",
            "fake government document",
            "misuse the national flag",
        ),
        (
            "A fictional example refers to {subject} without facilitation. Independent case {index}.",
            "Historical research discusses {subject} for education. Independent case {index}.",
            "An academic discussion studies {subject} without endorsing it. Independent case {index}.",
            "A documentary records the history of {subject} and condemns abuse. Independent case {index}.",
            "A museum exhibition provides context about {subject}. Independent case {index}.",
            "An educational archive mentions {subject} as a prevention example. Independent case {index}.",
            "A research paper analyses {subject} and provides no transaction. Independent case {index}.",
            "A historical lesson warns against {subject}. Independent case {index}.",
            "A fictional script mentions {subject} without operational help. Independent case {index}.",
            "A documentary reports {subject} to explain prevention. Independent case {index}.",
        ),
    )
    add_group(
        rows,
        "fresh_jurisdiction_licensing_uncertainty",
        UNCERTAIN_CATEGORY,
        (
            "online betting service",
            "unlicensed betting",
            "protected government name",
            "unapproved medicine",
            "commercial sexual service",
        ),
        (
            "A post mentions {subject}, but jurisdiction and licensing are unknown. Independent case {index}.",
            "The text names {subject} without a transaction or location. Independent case {index}.",
            "A message refers to {subject}; its legal status is unclear. Independent case {index}.",
            "The content discusses {subject} without enough context to establish facilitation. Independent case {index}.",
            "A neutral mention of {subject} lacks licensing evidence. Independent case {index}.",
            "The purpose of the referenced {subject} cannot be determined. Independent case {index}.",
            "A short post names {subject}, while authorization remains uncertain. Independent case {index}.",
            "No country or regulatory context is given for {subject}. Independent case {index}.",
            "A reference to {subject} provides no evidence of an offer. Independent case {index}.",
            "The status and intent of {subject} remain unresolved. Independent case {index}.",
        ),
    )

    owners = tuple(
        category
        for category in OWNER_ACTIONS
        if category != "Child Exploitation"
    )
    subjects = (
        "illegal drugs",
        "unlicensed gun",
        "illegal gambling",
        "fake identity document",
        "commercial sexual service",
    )
    for index in range(1, 51):
        owner = owners[(index - 1) % len(owners)]
        subject = subjects[(index - 1) % len(subjects)]
        text = (
            f"An established {owner} case also mentions {subject} for sale; "
            f"contact me. Ownership case {index}."
        )
        rows.append(
            {
                "record_id": f"OWNER-ISOLATION-{index:03d}",
                "group": "fresh_established_category_owner_isolation",
                "text": text,
                "text_sha256": text_hash(text),
                "expected_category": owner,
                "existing_category": owner,
                "existing_action": OWNER_ACTIONS[owner],
                "existing_review": True,
            }
        )

    for index in range(1, 51):
        subject = subjects[(index - 1) % len(subjects)]
        text = (
            "A child-safety report describes an attempt to groom a minor and "
            f"also quotes a {subject} for sale listing. Child boundary case {index}."
        )
        rows.append(
            {
                "record_id": f"CHILD-BOUNDARY-{index:03d}",
                "group": "fresh_child_safety_owner_boundary",
                "text": text,
                "text_sha256": text_hash(text),
                "expected_category": "Child Exploitation",
                "existing_category": "Child Exploitation",
                "existing_action": OWNER_ACTIONS["Child Exploitation"],
                "existing_review": True,
            }
        )
    return rows


def verify_frozen_artifacts(manifest: dict[str, Any]) -> bool:
    artifacts = {
        str(item["relative_path"]): item
        for item in manifest.get("artifacts", [])
    }
    for relative_path, live_path in LIVE_ARTIFACTS.items():
        frozen_path = CANDIDATE_DIRECTORY / relative_path
        record = artifacts.get(relative_path)
        if record is None or not frozen_path.is_file() or not live_path.is_file():
            return False
        expected_hash = str(record.get("sha256", ""))
        if sha256_file(frozen_path) != expected_hash:
            return False
        if sha256_file(live_path) != expected_hash:
            return False
    return True


def development_hashes() -> set[str]:
    with DEVELOPMENT_DATASET_PATH.open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        return {text_hash(str(row["text"])) for row in csv.DictReader(handle)}


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    if REPORT_PATH.exists() or VERDICT_PATH.exists():
        raise FileExistsError(
            "The RC1 independent challenge has already been evaluated and "
            "will not be overwritten."
        )
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("candidate") != CANDIDATE:
        raise RuntimeError("Unexpected frozen candidate identity.")
    frozen_verified = verify_frozen_artifacts(manifest)
    if not frozen_verified:
        raise RuntimeError("Frozen source, policy, or dependency verification failed.")

    rows = build_challenge()
    if len(rows) != 500:
        raise RuntimeError(f"Unexpected challenge size: {len(rows)}")
    hashes = [str(row["text_sha256"]) for row in rows]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Duplicate independent challenge text detected.")
    overlap = set(hashes) & development_hashes()
    if overlap:
        raise RuntimeError("Independent/development text overlap detected.")

    challenge_contract = [
        {
            "record_id": row["record_id"],
            "group": row["group"],
            "expected_category": row["expected_category"],
            "existing_category": row["existing_category"],
            "text_sha256": row["text_sha256"],
        }
        for row in rows
    ]
    challenge_sha256 = hashlib.sha256(
        json.dumps(
            challenge_contract,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    tp = tn = fp = fn = 0
    action_failures = category_mix_failures = authority_failures = 0
    processing_errors = 0
    group_results: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "correct": 0}
    )

    print("Running the frozen Illegal Activities V1 RC1 independent challenge...")
    print("Individual cases and predictions are intentionally hidden.")
    print("OpenRouter is not used for the independent accuracy challenge.")
    print()
    for row in rows:
        group = str(row["group"])
        group_results[group]["records"] += 1
        try:
            analysis = analyze_illegal_activities_v1(
                str(row["text"]),
                ["text"],
                use_openrouter=False,
            )
            decision = apply_illegal_activities_v1_fusion(
                category=str(row["existing_category"]),
                severity="None",
                action=str(row["existing_action"]),
                confidence=0.70,
                human_review_required=bool(row["existing_review"]),
                reason="Independent baseline owner.",
                matched_signals=[],
                analysis=analysis,
            )
            expected = str(row["expected_category"])
            predicted = str(decision["category"])
            correct = predicted == expected
            group_results[group]["correct"] += int(correct)

            expected_illegal = expected == ILLEGAL_CATEGORY
            predicted_illegal = predicted == ILLEGAL_CATEGORY
            if expected_illegal and predicted_illegal:
                tp += 1
            elif expected_illegal:
                fn += 1
            elif predicted_illegal:
                fp += 1
            else:
                tn += 1

            expected_action = str(row["existing_action"])
            expected_review = bool(row["existing_review"])
            if expected == ILLEGAL_CATEGORY:
                expected_action = ILLEGAL_ACTION
                expected_review = True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action = UNCERTAIN_ACTION
                expected_review = True
            if (
                decision.get("action") != expected_action
                or bool(decision.get("human_review_required")) != expected_review
                or decision.get("automatic_enforcement_allowed") is not False
            ):
                action_failures += 1
            if not correct:
                category_mix_failures += 1
            if (
                analysis.get("openrouter", {}).get("used") is not False
                or decision.get("automatic_enforcement_allowed") is not False
            ):
                authority_failures += 1
        except Exception:
            processing_errors += 1

    records = len(rows)
    positives = tp + fn
    negatives = tn + fp
    accuracy = ratio(tp + tn, records)
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, positives)
    specificity = ratio(tn, negatives)
    f1 = ratio(2 * precision * recall, precision + recall)
    aggregate_groups = {
        group: {
            "records": values["records"],
            "correct": values["correct"],
            "accuracy": ratio(values["correct"], values["records"]),
        }
        for group, values in sorted(group_results.items())
    }
    minimum_group_accuracy = min(
        values["accuracy"] for values in aggregate_groups.values()
    )

    gate = manifest["independent_gate_frozen_before_holdout"]
    gate_checks = {
        "frozen_source_hashes_verified": frozen_verified,
        "zero_development_overlap": not overlap,
        "accuracy": accuracy >= float(gate["minimum_accuracy"]),
        "illegal_precision": precision
        >= float(gate["minimum_illegal_precision"]),
        "illegal_recall": recall >= float(gate["minimum_illegal_recall"]),
        "safe_specificity": specificity
        >= float(gate["minimum_safe_specificity"]),
        "f1": f1 >= float(gate["minimum_f1"]),
        "minimum_group_accuracy": minimum_group_accuracy
        >= float(gate["minimum_group_accuracy"]),
        "action_contract": action_failures
        <= int(gate["maximum_action_contract_failures"]),
        "category_mix_contract": category_mix_failures
        <= int(gate["maximum_category_mix_failures"]),
        "authority_contract": authority_failures
        <= int(gate["maximum_authority_contract_failures"]),
        "processing_contract": processing_errors
        <= int(gate["maximum_processing_errors"]),
    }
    passed = all(gate_checks.values())

    report = {
        "candidate": CANDIDATE,
        "challenge_version": CHALLENGE_VERSION,
        "challenge_sha256": challenge_sha256,
        "records": records,
        "unique_texts": len(set(hashes)),
        "positive_records": positives,
        "negative_records": negatives,
        "development_overlap": len(overlap),
        "accuracy": accuracy,
        "illegal_precision": precision,
        "illegal_recall": recall,
        "safe_specificity": specificity,
        "f1": f1,
        "minimum_group_accuracy": minimum_group_accuracy,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "authority_contract_failures": authority_failures,
        "processing_errors": processing_errors,
        "group_results": aggregate_groups,
        "gate_checks": gate_checks,
        "passed_synthetic_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "connected_to_live_moderation": True,
        "automatic_enforcement_allowed": False,
        "openrouter_used_for_independent_accuracy": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "evidence_scope": "synthetic evidence, not external or real-world accuracy",
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=False)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    verdict = {
        "candidate": CANDIDATE,
        "status": (
            "Passed synthetic independent readiness gate"
            if passed
            else "Failed synthetic independent readiness gate"
        ),
        "challenge_version": CHALLENGE_VERSION,
        "challenge_sha256": challenge_sha256,
        "passed_synthetic_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "connected_to_live_moderation": True,
        "automatic_enforcement_allowed": False,
        "candidate_may_be_modified_using_this_holdout": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "report_path": REPORT_PATH.relative_to(ROOT).as_posix(),
        "evidence_scope": "synthetic evidence, not external or real-world accuracy",
    }
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print("ILLEGAL ACTIVITIES V1 RC1 INDEPENDENT CHALLENGE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE}")
    print(f"Challenge version: {CHALLENGE_VERSION}")
    print(f"Challenge SHA-256: {challenge_sha256}")
    print(f"Records: {records}")
    print(f"Unique texts: {len(set(hashes))}")
    print(f"Positive records: {positives}")
    print(f"Negative records: {negatives}")
    print(f"Development overlap: {len(overlap)}")
    print(f"Accuracy: {accuracy:.2%}")
    print(f"Illegal precision: {precision:.2%}")
    print(f"Illegal recall: {recall:.2%}")
    print(f"Safe specificity: {specificity:.2%}")
    print(f"F1: {f1:.2%}")
    print(f"Minimum group accuracy: {minimum_group_accuracy:.2%}")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Authority-contract failures: {authority_failures}")
    print(f"Processing errors: {processing_errors}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, values in aggregate_groups.items():
        print(
            f"{group}: {values['correct']}/{values['records']} "
            f"({values['accuracy']:.2%})"
        )
    print()
    print("INDEPENDENT GATE CHECKS")
    print("-" * 60)
    for key, value in gate_checks.items():
        print(f"{key}: {value}")
    print()
    print(f"Passed synthetic independent readiness gate: {passed}")
    print(f"Eligible for guarded live integration: {passed}")
    print("Connected to live moderation: True")
    print("Automatic enforcement allowed: False")
    print("OpenRouter used for independent accuracy: False")
    print(f"Report: {REPORT_PATH}")
    print(f"Verdict: {VERDICT_PATH}")
    print("Individual cases and predictions were intentionally hidden.")
    print("No raw challenge text was stored.")
    print("This is synthetic evidence, not external or real-world accuracy.")
    print("This holdout may not be used to modify RC1.")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
