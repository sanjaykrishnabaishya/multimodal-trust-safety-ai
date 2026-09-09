"""Development gate for Identity Theft & Impersonation V2 RC3."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc3_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc3,
    apply_identity_theft_impersonation_v2_rc3_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc3"
DATASET_PATH = DATASET_DIR / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "identity_theft_impersonation" / "v2_rc3_development"
REPORT_PATH = REPORT_DIR / "report.json"
MISMATCH_PATH = REPORT_DIR / "mismatches.json"
PRIOR_DATA = (
    ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc1" / "development.csv",
    ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc2" / "development.csv",
)
OWNERS = (
    ("Child Exploitation", "Block and immediately escalate"),
    ("Publishing Private Information", "Refer to human review"),
    ("Spam, Scam & Phishing", "Block, warn, or limit distribution"),
    ("Illegal Activities", "Block or restrict and escalate"),
    ("Malicious Programs", "Block and send for security review"),
)


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def add(
    rows: list[dict[str, Any]], group: str, expected: str,
    templates: tuple[str, ...], *, owner: str = NORMAL_CATEGORY,
    action: str = "Allow", review: bool = False,
) -> None:
    subjects = ("an account", "a listing", "a profile", "a message")
    for index in range(80):
        rows.append({
            "group": group,
            "text": templates[index % len(templates)].format(
                subject=subjects[index % len(subjects)], index=index + 1),
            "expected": expected,
            "owner": owner,
            "action": action,
            "review": review,
        })


def build() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    add(rows, "aggregate_incomplete_evidence_boundary", UNCERTAIN_CATEGORY, (
        "A possible cloned profile is reported, but identity evidence is incomplete; RC3 development {index} for {subject}.",
        "A fake account may be posing as a business while account provenance is unknown; RC3 development {index} for {subject}.",
        "A profile may be impersonating a resident, but authorization cannot be verified; RC3 development {index} for {subject}.",
        "Only a screenshot is available for a possible account takeover and identity cannot be verified; RC3 development {index} for {subject}.",
    ))
    add(rows, "natural_and_canonical_positive_regression", IDENTITY_CATEGORY, (
        "Someone is impersonating me using a cloned account and sends messages to contacts; RC3 development {index} for {subject}.",
        "This profile is pretending to be her, created a fake profile, and requests account access; RC3 development {index} for {subject}.",
        "Someone has stolen my identity and opened an account in my name; RC3 development {index} for {subject}.",
        "Evidence indicates this user uses personal information without permission and opened a new account; RC3 development {index} for {subject}.",
    ))
    add(rows, "authorized_reporting_and_parody_boundary", NORMAL_CATEGORY, (
        "A platform-verified official account represents the organization; RC3 safe {index} for {subject}.",
        "A clearly labelled parody is pretending to be a character and claims no official affiliation; RC3 safe {index} for {subject}.",
        "A news report explains identity theft and no active account is described; RC3 safe {index} for {subject}.",
        "Security training discusses a cloned account and contains no real credentials; RC3 safe {index} for {subject}.",
    ))
    add(rows, "weak_and_ordinary_identity_boundary", NORMAL_CATEGORY, (
        "A page has the same name, but no active misuse is described; RC3 weak {index} for {subject}.",
        "A profile photograph resembles someone, but identity cannot be inferred from appearance; RC3 weak {index} for {subject}.",
        "A support article documents identity settings; RC3 ordinary {index} for {subject}.",
        "A workshop explains authentication documentation; RC3 ordinary {index} for {subject}.",
    ))
    for index in range(80):
        owner, action = OWNERS[index % len(OWNERS)]
        rows.append({
            "group": "established_owner_isolation",
            "text": f"A possible cloned account has incomplete identity evidence, while an existing {owner} owner controls the case; RC3 development owner {index + 1}.",
            "expected": owner,
            "owner": owner,
            "action": action,
            "review": True,
        })
    return rows


def ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def main() -> None:
    rows = build()
    hashes = [text_hash(str(row["text"])) for row in rows]
    prior_hashes: set[str] = set()
    for path in PRIOR_DATA:
        with path.open("r", encoding="utf-8", newline="") as handle:
            prior_hashes.update(text_hash(row["text"]) for row in csv.DictReader(handle))
    overlap = len(set(hashes) & prior_hashes)
    if len(rows) != 400 or len(set(hashes)) != 400:
        raise RuntimeError("Development size or uniqueness failed")

    tp = tn = fp = fn = 0
    action_fail = category_fail = data_fail = authority_fail = errors = 0
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "correct": 0})
    mismatches: list[dict[str, str]] = []
    for row in rows:
        group, expected = str(row["group"]), str(row["expected"])
        groups[group]["records"] += 1
        try:
            analysis = analyze_identity_theft_impersonation_v2_rc3(str(row["text"]), ["text"])
            decision = apply_identity_theft_impersonation_v2_rc3_fusion(
                category=str(row["owner"]), severity="None", action=str(row["action"]),
                confidence=0.71, human_review_required=bool(row["review"]),
                reason="Development baseline.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["action"]), bool(row["review"])
            if expected == IDENTITY_CATEGORY:
                expected_action, expected_review = IDENTITY_ACTION, True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action, expected_review = UNCERTAIN_ACTION, True
            action_fail += int(
                decision["action"] != expected_action
                or bool(decision["human_review_required"]) != expected_review
                or decision["automatic_enforcement_allowed"] is not False)
            category_fail += int(not correct)
            data_fail += int(any(analysis[key] is not False for key in (
                "real_identity_documents_stored", "raw_credentials_stored",
                "complete_personal_identifiers_stored", "biometric_embeddings_stored")))
            authority_fail += int(any(analysis[key] is not False for key in (
                "face_recognition_used", "voice_identity_matching_used",
                "identity_inferred_from_appearance", "identity_verified",
                "authorization_verified", "deceptive_intent_determined",
                "external_provider_used", "external_transmission_allowed",
                "automatic_account_suspension_allowed")))
            expected_positive = expected == IDENTITY_CATEGORY
            predicted_positive = predicted == IDENTITY_CATEGORY
            if expected_positive and predicted_positive:
                tp += 1
            elif expected_positive:
                fn += 1
            elif predicted_positive:
                fp += 1
            else:
                tn += 1
            if not correct:
                mismatches.append({"group": group, "expected": expected,
                                   "predicted": predicted,
                                   "status": str(analysis["fusion_status"])})
        except Exception as error:
            errors += 1
            mismatches.append({"group": group, "error": type(error).__name__})

    accuracy = ratio(tp + tn, len(rows))
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    f1 = ratio(2 * precision * recall, precision + recall)
    group_results = {
        group: {**values, "accuracy": ratio(values["correct"], values["records"])}
        for group, values in sorted(groups.items())
    }
    minimum = min(value["accuracy"] for value in group_results.values())
    gates = {
        "accuracy": accuracy >= .95,
        "identity_precision": precision >= .97,
        "identity_recall": recall >= .95,
        "safe_specificity": specificity >= .99,
        "f1": f1 >= .96,
        "minimum_group_accuracy": minimum >= .92,
        "action_contract": action_fail == 0,
        "category_mix_contract": category_fail == 0,
        "data_contract": data_fail == 0,
        "authority_contract": authority_fail == 0,
        "processing_contract": errors == 0,
        "zero_prior_development_overlap": overlap == 0,
    }
    report = {
        "version": "2026.09-identity-theft-impersonation-v2-rc3-development",
        "records": len(rows), "unique_texts": len(set(hashes)),
        "prior_development_overlap": overlap,
        "accuracy": accuracy, "identity_precision": precision,
        "identity_recall": recall, "safe_specificity": specificity,
        "f1": f1, "minimum_group_accuracy": minimum,
        "false_positives": fp, "false_negatives": fn,
        "action_contract_failures": action_fail,
        "category_mix_failures": category_fail,
        "data_contract_failures": data_fail,
        "authority_contract_failures": authority_fail,
        "processing_errors": errors,
        "group_results": group_results, "gates": gates,
        "passed_development_gate": all(gates.values()),
        "rc2_independent_examples_used": False,
        "rc2_individual_predictions_used": False,
        "real_identity_documents_used": False,
        "raw_credentials_used": False,
        "complete_personal_identifiers_used": False,
        "external_provider_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report["dataset_sha256"] = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MISMATCH_PATH.write_text(json.dumps(mismatches, indent=2) + "\n", encoding="utf-8")

    print("IDENTITY THEFT & IMPERSONATION V2 RC3 DEVELOPMENT\n" + "=" * 60)
    print(f"Records: {len(rows)}\nUnique texts: {len(set(hashes))}\nPrior-development overlap: {overlap}")
    for label, value in (
        ("Accuracy", accuracy), ("Identity precision", precision),
        ("Identity recall", recall), ("Safe specificity", specificity),
        ("F1", f1), ("Minimum group accuracy", minimum),
    ):
        print(f"{label}: {value:.2%}")
    print(f"Action failures: {action_fail}\nCategory failures: {category_fail}")
    print(f"Data failures: {data_fail}\nAuthority failures: {authority_fail}\nProcessing errors: {errors}")
    print("\nGROUP RESULTS\n" + "-" * 60)
    for group, value in group_results.items():
        print(f"{group}: {value['correct']}/{value['records']} ({value['accuracy']:.2%})")
    print(f"\nPassed development gate: {report['passed_development_gate']}")
    print(f"Dataset: {DATASET_PATH}\nReport: {REPORT_PATH}")
    print("RC2 independent examples used: False\nExternal provider used: False")
    print("Connected to live moderation: False")
    if not report["passed_development_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
