"""Evaluate RC2 on fresh synthetic development evidence after RC1's live gap."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc1_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
)
from app.services.identity_theft_impersonation_v2_rc2_service import (
    analyze_identity_theft_impersonation_v2_rc2,
    apply_identity_theft_impersonation_v2_rc2_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc2"
DATASET_PATH = DATASET_DIR / "development.csv"
PRIOR_DATA = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc1" / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "identity_theft_impersonation" / "v2_rc2_development"
REPORT_PATH = REPORT_DIR / "report.json"
MISMATCH_PATH = REPORT_DIR / "mismatches.json"
OWNERS = (("Child Exploitation", "Block and immediately escalate"),
          ("Spam, Scam & Phishing", "Block, warn, or limit distribution"),
          ("Publishing Private Information", "Refer to human review"),
          ("Illegal Activities", "Block or restrict and escalate"))


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def add(rows: list[dict[str, Any]], group: str, expected: str,
        subjects: tuple[str, ...], templates: tuple[str, ...]) -> None:
    for index in range(60):
        rows.append({"group": group,
                     "text": templates[index % len(templates)].format(
                         subject=subjects[index % len(subjects)], index=index + 1),
                     "expected": expected, "owner": NORMAL_CATEGORY,
                     "action": "Allow", "review": False})


def build() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    people = ("a shopper", "an employee", "a resident", "a subscriber")
    add(rows, "natural_first_person_impersonation", IDENTITY_CATEGORY, people, (
        "Someone is impersonating me using a cloned account; RC2 development {index} for {subject}.",
        "This person is pretending to be me and created a fake profile; RC2 development {index} for {subject}.",
        "They are posing as me while using my photograph; RC2 development {index} for {subject}.",
        "The attacker is impersonating us using the cloned account; RC2 development {index} for {subject}.",
    ))
    add(rows, "natural_third_person_and_company_impersonation", IDENTITY_CATEGORY, people, (
        "Someone has been impersonating him using his photograph; RC2 development {index} for {subject}.",
        "This account is pretending to be her and created a fake account; RC2 development {index} for {subject}.",
        "They are impersonating our company using a cloned account; RC2 development {index} for {subject}.",
        "The profile is posing as our company and created a fake profile; RC2 development {index} for {subject}.",
    ))
    add(rows, "natural_identity_theft_transactions", IDENTITY_CATEGORY, people, (
        "Someone has stolen my identity and opened an account in my name; RC2 development {index} for {subject}.",
        "The fraudster committed identity fraud and made purchases in my name; RC2 development {index} for {subject}.",
        "The attacker used a stolen identity and ran up charges in my name; RC2 development {index} for {subject}.",
        "Someone is committing identity theft and claimed benefits in my name; RC2 development {index} for {subject}.",
    ))
    add(rows, "natural_uncertain_impersonation", UNCERTAIN_CATEGORY, people, (
        "This person may be impersonating me, but identity remains unverified; RC2 development {index} for {subject}.",
        "The profile might be impersonating her and could be authorized; RC2 development {index} for {subject}.",
        "Someone is possibly impersonating our company, but authenticity is uncertain; RC2 development {index} for {subject}.",
        "The account is pretending to be him, but there is not enough evidence to verify; RC2 development {index} for {subject}.",
    ))
    add(rows, "natural_safe_reporting_parody_and_training", NORMAL_CATEGORY, people, (
        "Impersonation awareness says someone is impersonating me, but no active account is described; RC2 safe {index} for {subject}.",
        "A clearly labelled parody says it is pretending to be me and does not claim official affiliation; RC2 safe {index} for {subject}.",
        "Security training describes using a cloned account and contains no real credentials; RC2 safe {index} for {subject}.",
        "A fictional story says someone has stolen my identity; it is fictional and not real; RC2 safe {index} for {subject}.",
    ))
    add(rows, "natural_weak_claims_without_misuse", NORMAL_CATEGORY, people, (
        "The account has the same name but no misuse act is described; RC2 weak {index} for {subject}.",
        "A profile looks like me and no active deception is established; RC2 weak {index} for {subject}.",
        "The page uses a company logo, but no transaction, access, or contact is alleged; RC2 weak {index} for {subject}.",
        "A similar username appears without any identity misuse evidence; RC2 weak {index} for {subject}.",
    ))
    add(rows, "rc1_core_contract_regression", IDENTITY_CATEGORY, people, (
        "This account is impersonating another person and sends messages to contacts; RC2 core {index} for {subject}.",
        "Evidence indicates this user uses personal information without permission and opened a new account; RC2 core {index} for {subject}.",
        "This profile is falsely posing as a business representative and collects payments; RC2 core {index} for {subject}.",
        "A verified victim report says this user uses stolen credentials and accessed the account; RC2 core {index} for {subject}.",
    ))
    for index in range(60):
        owner, action = OWNERS[index % len(OWNERS)]
        rows.append({"group": "established_owner_isolation",
                     "text": f"Someone is impersonating me using a cloned account, while an existing {owner} owner controls the case; RC2 owner {index + 1}.",
                     "expected": owner, "owner": owner, "action": action, "review": True})
    return rows


def ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def main() -> None:
    rows = build()
    hashes = [text_hash(str(row["text"])) for row in rows]
    with PRIOR_DATA.open("r", encoding="utf-8", newline="") as handle:
        prior = {text_hash(row["text"]) for row in csv.DictReader(handle)}
    overlap = len(set(hashes) & prior)
    if len(rows) != 480 or len(set(hashes)) != 480 or overlap:
        raise RuntimeError("RC2 size, uniqueness, or prior-development overlap failed")
    tp = tn = fp = fn = 0
    action_fail = category_fail = data_fail = authority_fail = errors = 0
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "correct": 0})
    mismatches = []
    for row in rows:
        group, expected = str(row["group"]), str(row["expected"])
        groups[group]["records"] += 1
        try:
            analysis = analyze_identity_theft_impersonation_v2_rc2(str(row["text"]), ["text"])
            decision = apply_identity_theft_impersonation_v2_rc2_fusion(
                category=str(row["owner"]), severity="None", action=str(row["action"]),
                confidence=0.70, human_review_required=bool(row["review"]),
                reason="RC2 development.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["action"]), bool(row["review"])
            if expected == IDENTITY_CATEGORY:
                expected_action, expected_review = IDENTITY_ACTION, True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action, expected_review = UNCERTAIN_ACTION, True
            action_fail += int(decision["action"] != expected_action or
                               bool(decision["human_review_required"]) != expected_review or
                               decision["automatic_enforcement_allowed"] is not False)
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
            ep, pp = expected == IDENTITY_CATEGORY, predicted == IDENTITY_CATEGORY
            if ep and pp: tp += 1
            elif ep: fn += 1
            elif pp: fp += 1
            else: tn += 1
            if not correct:
                mismatches.append({"group": group, "expected": expected,
                                   "predicted": predicted, "status": analysis["fusion_status"]})
        except Exception as error:
            errors += 1
            mismatches.append({"group": group, "error": type(error).__name__})
    accuracy, precision, recall = ratio(tp + tn, len(rows)), ratio(tp, tp + fp), ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    f1 = ratio(2 * precision * recall, precision + recall)
    group_results = {group: {**values, "accuracy": ratio(values["correct"], values["records"])}
                     for group, values in sorted(groups.items())}
    minimum = min(value["accuracy"] for value in group_results.values())
    gates = {"accuracy": accuracy >= .95, "identity_precision": precision >= .97,
             "identity_recall": recall >= .95, "safe_specificity": specificity >= .99,
             "f1": f1 >= .96, "minimum_group_accuracy": minimum >= .92,
             "action_contract": action_fail == 0, "category_mix_contract": category_fail == 0,
             "data_contract": data_fail == 0, "authority_contract": authority_fail == 0,
             "processing_contract": errors == 0, "zero_prior_development_overlap": overlap == 0}
    report = {"version": "2026.09-identity-theft-impersonation-v2-rc2-development",
              "records": len(rows), "unique_texts": len(set(hashes)),
              "prior_development_overlap": overlap, "accuracy": accuracy,
              "identity_precision": precision, "identity_recall": recall,
              "safe_specificity": specificity, "f1": f1, "minimum_group_accuracy": minimum,
              "false_positives": fp, "false_negatives": fn,
              "action_contract_failures": action_fail, "category_mix_failures": category_fail,
              "data_contract_failures": data_fail, "authority_contract_failures": authority_fail,
              "processing_errors": errors, "group_results": group_results, "gates": gates,
              "passed_development_gate": all(gates.values()),
              "rc1_independent_examples_used": False, "rc1_individual_predictions_used": False,
              "real_identity_documents_used": False, "raw_credentials_used": False,
              "complete_personal_identifiers_used": False, "external_provider_used": False,
              "automatic_enforcement_allowed": False, "connected_to_live_moderation": False}
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    report["dataset_sha256"] = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    MISMATCH_PATH.write_text(json.dumps(mismatches, indent=2) + "\n", encoding="utf-8")
    print("IDENTITY THEFT & IMPERSONATION V2 RC2 DEVELOPMENT\n" + "=" * 60)
    print(f"Records: {len(rows)}\nUnique texts: {len(set(hashes))}\nPrior-development overlap: {overlap}")
    for label, value in (("Accuracy", accuracy), ("Identity precision", precision),
                         ("Identity recall", recall), ("Safe specificity", specificity),
                         ("F1", f1), ("Minimum group accuracy", minimum)):
        print(f"{label}: {value:.2%}")
    print(f"Action failures: {action_fail}\nCategory failures: {category_fail}\nData failures: {data_fail}\nAuthority failures: {authority_fail}\nProcessing errors: {errors}")
    print("\nGROUP RESULTS\n" + "-" * 60)
    for group, value in group_results.items(): print(f"{group}: {value['correct']}/{value['records']} ({value['accuracy']:.2%})")
    print(f"\nPassed development gate: {report['passed_development_gate']}\nDataset: {DATASET_PATH}\nReport: {REPORT_PATH}")
    print("RC1 independent examples used: False\nExternal provider used: False\nConnected to live moderation: False")
    if not report["passed_development_gate"]: raise SystemExit(1)


if __name__ == "__main__":
    main()
