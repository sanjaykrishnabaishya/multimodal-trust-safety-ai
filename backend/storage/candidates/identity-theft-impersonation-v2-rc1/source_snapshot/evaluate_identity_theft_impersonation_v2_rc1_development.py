"""Build and evaluate synthetic Identity Theft & Impersonation V2 RC1 development evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc1_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc1,
    apply_identity_theft_impersonation_v2_rc1_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc1"
DATASET_PATH = DATASET_DIR / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "identity_theft_impersonation" / "v2_rc1_development"
REPORT_PATH = REPORT_DIR / "report.json"
MISMATCH_PATH = REPORT_DIR / "mismatches.json"
OWNER_ACTIONS = {
    "Child Exploitation": "Block and immediately escalate",
    "Publishing Private Information": "Refer to human review",
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Illegal Activities": "Block or restrict and escalate",
    "Malicious Programs": "Block and send for security review",
}


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def add_group(rows: list[dict[str, Any]], group: str, expected: str,
              subjects: tuple[str, ...], templates: tuple[str, ...], *,
              owner: str = NORMAL_CATEGORY, action: str = "Allow",
              review: bool = False) -> None:
    for index in range(50):
        rows.append({
            "record_id": f"{group.upper()}-{index + 1:03d}", "group": group,
            "text": templates[index % len(templates)].format(
                subject=subjects[index % len(subjects)], index=index + 1),
            "expected_category": expected, "existing_category": owner,
            "existing_action": action, "existing_review": review,
        })


def build_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    people = ("a customer", "a resident", "an employee", "an account holder")
    add_group(rows, "active_profile_and_account_impersonation", IDENTITY_CATEGORY, people, (
        "This profile cloned the victim's profile and currently contacts the victim's friends; case {index} involving {subject}.",
        "A verified victim report says this account is impersonating another person and sends messages to contacts; case {index} involving {subject}.",
        "Evidence indicates this profile is a fake profile pretending to be another person and publishes posts as the victim; case {index} involving {subject}.",
        "This account uses a cloned social media account and solicits customers while pretending to be another person; case {index} involving {subject}.",
    ))
    add_group(rows, "government_and_business_impersonation", IDENTITY_CATEGORY,
              ("a government office", "a bank", "a retailer", "a delivery company"), (
        "This caller is falsely posing as a government officer and currently collects payments from {subject}; case {index}.",
        "Evidence indicates this message is falsely posing as a business representative and requests account access from {subject}; case {index}.",
        "This account deceptively claims to represent {subject} and solicits customers; case {index}.",
        "A verified victim report says this profile pretends to be official support and collects payments for {subject}; case {index}.",
    ))
    add_group(rows, "identity_misuse_for_transactions_and_benefits", IDENTITY_CATEGORY, people, (
        "This applicant uses another person's identity without permission and opens a new account; case {index} involving {subject}.",
        "Evidence indicates this transaction uses the victim's identity fraudulently and makes purchases; case {index} involving {subject}.",
        "This user uses personal information without authorization and applies for a loan; case {index} involving {subject}.",
        "A documented account record says this applicant uses a tax identity without consent and claims benefits; case {index} involving {subject}.",
    ))
    add_group(rows, "credential_and_account_takeover_misuse", IDENTITY_CATEGORY, people, (
        "This user uses stolen credentials for an online account and accesses the account; case {index} involving {subject}.",
        "Evidence indicates this account uses login credentials without authorization and takes over the account; case {index} involving {subject}.",
        "A verified victim report says this user uses account credentials without permission and changes the account email; case {index} involving {subject}.",
        "This account uses a customer account against the victim's wishes and sends messages to contacts; case {index} involving {subject}.",
    ))
    add_group(rows, "uncertain_identity_authorization_or_intent", UNCERTAIN_CATEGORY, people, (
        "This profile may be impersonating another person, but identity cannot be verified; case {index} involving {subject}.",
        "This account is posing as another person, while authorization is unclear; case {index} involving {subject}.",
        "A current account cloned the victim's profile, but account ownership is disputed; case {index} involving {subject}.",
        "Evidence indicates a fake profile pretending to be another person, while deceptive intent is unclear; case {index} involving {subject}.",
    ))
    add_group(rows, "incomplete_or_appearance_only_evidence", UNCERTAIN_CATEGORY, people, (
        "Only a profile photograph is available; this account may be posing as the victim and identity evidence is incomplete; case {index} involving {subject}.",
        "Media could not be decoded, but metadata says this profile is impersonating another person and authorization cannot be verified; case {index} involving {subject}.",
        "Only a screenshot is available for a cloned social media account, and account authenticity is unclear; case {index} involving {subject}.",
        "The source account is unavailable; a fake profile pretending to be another person is alleged and the victim report is unverified; case {index} involving {subject}.",
    ))
    add_group(rows, "documented_authorized_representation", NORMAL_CATEGORY,
              ("a bank", "a public agency", "a retailer", "a university"), (
        "Documented authorization confirms an authorized representative for {subject}; safe case {index}.",
        "The account holder approved this owner-approved representative for {subject}; safe case {index}.",
        "A platform-verified official account represents {subject}; safe case {index}.",
        "Identity proofing completed for the official organization account of {subject}; safe case {index}.",
    ))
    add_group(rows, "declared_parody_fan_fiction_and_roleplay", NORMAL_CATEGORY,
              ("a public figure", "a fictional company", "a sports team", "a story character"), (
        "This clearly labelled parody of {subject} does not claim official affiliation; safe case {index}.",
        "An unofficial fan page for {subject} clearly discloses it is unofficial; safe case {index}.",
        "A fictional story about {subject} is fictional and not real; safe case {index}.",
        "A role-play exercise involving {subject} does not contact real victims; safe case {index}.",
    ))
    add_group(rows, "reporting_education_prevention_and_recovery", NORMAL_CATEGORY,
              ("identity theft", "account impersonation", "fake support", "account recovery"), (
        "A news report discusses {subject} and no active account is described; safe case {index}.",
        "Security training explains {subject} and contains no real credentials; safe case {index}.",
        "A consumer warning covers {subject} and links to the official reporting service; safe case {index}.",
        "A victim recovery guide describes {subject} and does not contact real victims; safe case {index}.",
    ))
    add_group(rows, "weak_name_face_voice_logo_or_claim", NORMAL_CATEGORY,
              ("the same name", "a similar profile photograph", "a company logo", "a similar username"), (
        "A self-reported identity points to {subject}, but no misuse act is described; weak case {index}.",
        "The profile claims to be official and has {subject}; there is no transaction, access, or victim impact; weak case {index}.",
        "One person says the account looks like them because of {subject}; no active deception is established; weak case {index}.",
        "An unverified account badge appears beside {subject}; identity and authorization are not asserted as facts; weak case {index}.",
    ))
    add_group(rows, "ordinary_identity_and_authentication_context", NORMAL_CATEGORY,
              ("identity settings", "account profile settings", "digital identity guidelines", "authentication documentation"), (
        "A help page explains {subject}; ordinary case {index}.",
        "A user updates {subject} on a personal device; ordinary case {index}.",
        "A student reads {subject}; ordinary case {index}.",
        "Routine technical documentation covers {subject}; ordinary case {index}.",
    ))
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(50):
        owner, action = owners[index % len(owners)]
        rows.append({
            "record_id": f"ESTABLISHED_OWNER-{index + 1:03d}",
            "group": "established_category_owner_isolation",
            "text": f"This account uses another person's identity without permission and opens a new account, while an existing {owner} owner controls the record; owner case {index + 1}.",
            "expected_category": owner, "existing_category": owner,
            "existing_action": action, "existing_review": True,
        })
    return rows


def ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    hashes = [text_hash(str(row["text"])) for row in records]
    if len(set(hashes)) != len(hashes):
        raise RuntimeError("Duplicate development text detected.")
    tp = tn = fp = fn = 0
    action_failures = category_failures = data_failures = authority_failures = errors = 0
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "correct": 0})
    mismatches: list[dict[str, Any]] = []
    for row in records:
        group, expected = str(row["group"]), str(row["expected_category"])
        groups[group]["records"] += 1
        try:
            analysis = analyze_identity_theft_impersonation_v2_rc1(str(row["text"]), ["text"])
            decision = apply_identity_theft_impersonation_v2_rc1_fusion(
                category=str(row["existing_category"]), severity="None",
                action=str(row["existing_action"]), confidence=0.70,
                human_review_required=bool(row["existing_review"]),
                reason="Development baseline.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["existing_action"]), bool(row["existing_review"])
            if expected == IDENTITY_CATEGORY:
                expected_action, expected_review = IDENTITY_ACTION, True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action, expected_review = UNCERTAIN_ACTION, True
            action_ok = (decision["action"] == expected_action and
                         bool(decision["human_review_required"]) == expected_review and
                         decision["automatic_enforcement_allowed"] is False)
            action_failures += int(not action_ok)
            category_failures += int(not correct)
            data_failures += int(any(analysis[key] is not False for key in (
                "real_identity_documents_stored", "raw_credentials_stored",
                "complete_personal_identifiers_stored", "biometric_embeddings_stored")))
            authority_failures += int(any(analysis[key] is not False for key in (
                "face_recognition_used", "voice_identity_matching_used",
                "identity_inferred_from_appearance", "identity_verified",
                "authorization_verified", "deceptive_intent_determined",
                "external_provider_used", "external_transmission_allowed",
                "automatic_account_suspension_allowed")))
            expected_positive, predicted_positive = expected == IDENTITY_CATEGORY, predicted == IDENTITY_CATEGORY
            if expected_positive and predicted_positive:
                tp += 1
            elif expected_positive:
                fn += 1
            elif predicted_positive:
                fp += 1
            else:
                tn += 1
            if not correct or not action_ok:
                mismatches.append({"record_id": row["record_id"], "group": group,
                                   "expected": expected, "predicted": predicted,
                                   "status": analysis["fusion_status"]})
        except Exception as error:
            errors += 1
            mismatches.append({"record_id": row["record_id"], "error": type(error).__name__})
    accuracy = ratio(tp + tn, len(records))
    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    f1 = ratio(2 * precision * recall, precision + recall)
    group_results = {group: {**values, "accuracy": ratio(values["correct"], values["records"])}
                     for group, values in sorted(groups.items())}
    minimum = min(values["accuracy"] for values in group_results.values())
    gates = {
        "accuracy": accuracy >= 0.95, "identity_precision": precision >= 0.97,
        "identity_recall": recall >= 0.95, "safe_specificity": specificity >= 0.99,
        "f1": f1 >= 0.96, "minimum_group_accuracy": minimum >= 0.92,
        "action_contract": action_failures == 0, "category_mix_contract": category_failures == 0,
        "data_contract": data_failures == 0, "authority_contract": authority_failures == 0,
        "processing_contract": errors == 0,
    }
    return {
        "version": "2026.09-identity-theft-impersonation-v2-rc1-development",
        "records": len(records), "unique_texts": len(set(hashes)),
        "label_counts": dict(Counter(str(row["expected_category"]) for row in records)),
        "accuracy": accuracy, "identity_precision": precision, "identity_recall": recall,
        "safe_specificity": specificity, "f1": f1, "minimum_group_accuracy": minimum,
        "false_positives": fp, "false_negatives": fn,
        "action_contract_failures": action_failures, "category_mix_failures": category_failures,
        "data_contract_failures": data_failures, "authority_contract_failures": authority_failures,
        "processing_errors": errors, "group_results": group_results, "gates": gates,
        "passed_development_gate": all(gates.values()),
        "real_identity_documents_used": False, "raw_credentials_used": False,
        "complete_personal_identifiers_used": False, "external_provider_used": False,
        "automatic_enforcement_allowed": False, "connected_to_live_moderation": False,
        "mismatches": mismatches,
    }


def main() -> None:
    records = build_records()
    if len(records) != 600:
        raise RuntimeError(f"Unexpected development size: {len(records)}")
    result = evaluate(records)
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    report = {**result, "dataset_sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()}
    report.pop("mismatches")
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MISMATCH_PATH.write_text(json.dumps(result["mismatches"], indent=2) + "\n", encoding="utf-8")
    print("IDENTITY THEFT & IMPERSONATION V2 RC1 DEVELOPMENT\n" + "=" * 60)
    print(f"Records: {result['records']}\nUnique texts: {result['unique_texts']}")
    for label, key in (("Accuracy", "accuracy"), ("Identity precision", "identity_precision"),
                       ("Identity recall", "identity_recall"), ("Safe specificity", "safe_specificity"),
                       ("F1", "f1"), ("Minimum group accuracy", "minimum_group_accuracy")):
        print(f"{label}: {result[key]:.2%}")
    print(f"Action failures: {result['action_contract_failures']}\nCategory failures: {result['category_mix_failures']}\nData-contract failures: {result['data_contract_failures']}\nAuthority failures: {result['authority_contract_failures']}\nProcessing errors: {result['processing_errors']}")
    print("\nGROUP RESULTS\n" + "-" * 60)
    for group, values in result["group_results"].items():
        print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
    print(f"\nPassed development gate: {result['passed_development_gate']}\nDataset: {DATASET_PATH}\nReport: {REPORT_PATH}")
    print("Real identity documents used: False\nExternal provider used: False\nConnected to live moderation: False")
    print("This is synthetic policy evidence, not real-world identity accuracy.")
    if not result["passed_development_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
