"""Aggregate-only independent challenge for frozen Identity V2 RC1."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc1_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc1,
    apply_identity_theft_impersonation_v2_rc1_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "identity-theft-impersonation-v2-rc1"
CDIR = BACKEND / "storage" / "candidates" / CANDIDATE
MANIFEST = CDIR / "manifest.json"
VERDICT = CDIR / "independent_evaluation_verdict.json"
DEV = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc1" / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "identity_theft_impersonation" / "v2_rc1_independent"
REPORT = REPORT_DIR / "aggregate_report.json"
LIVE = {
    "source_snapshot/identity_theft_impersonation_v2_rc1_service.py": BACKEND / "app" / "services" / "identity_theft_impersonation_v2_rc1_service.py",
    "policy_snapshot/identity_theft_impersonation_v2_rc1_policy.json": BACKEND / "app" / "evidence" / "identity_theft_impersonation_v2_rc1_policy.json",
    "source_snapshot/evaluate_identity_theft_impersonation_v2_rc1_development.py": BACKEND / "scripts" / "evaluate_identity_theft_impersonation_v2_rc1_development.py",
    "source_snapshot/freeze_identity_theft_impersonation_v2_rc1.py": BACKEND / "scripts" / "freeze_identity_theft_impersonation_v2_rc1.py",
}
OWNER_ACTIONS = {
    "Child Exploitation": "Block and immediately escalate",
    "Publishing Private Information": "Refer to human review",
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Illegal Activities": "Block or restrict and escalate",
    "Malicious Programs": "Block and send for security review",
}


def sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def add(rows: list[dict[str, Any]], group: str, expected: str,
        subjects: tuple[str, ...], templates: tuple[str, ...], *,
        owner: str = NORMAL_CATEGORY, action: str = "Allow", review: bool = False) -> None:
    for index in range(60):
        rows.append({
            "group": group,
            "text": templates[index % len(templates)].format(
                subject=subjects[index % len(subjects)], index=index + 1),
            "expected_category": expected, "existing_category": owner,
            "existing_action": action, "existing_review": review,
        })


def build() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    people = ("an applicant", "a subscriber", "a shopper", "a resident")
    add(rows, "fresh_person_profile_impersonation", IDENTITY_CATEGORY, people, (
        "Victim reports this profile is impersonating the victim and currently sends messages to contacts; independent {index} for {subject}.",
        "This account uses a duplicate profile pretending to be the victim and contacts the victim's friends; independent {index} for {subject}.",
        "Evidence indicates this profile is posing as another person and publishes posts as the victim; independent {index} for {subject}.",
        "A verified victim report says this account cloned the victim's profile and solicits customers; independent {index} for {subject}.",
    ))
    add(rows, "fresh_entity_and_official_impersonation", IDENTITY_CATEGORY,
        ("a public office", "a payment company", "a shop", "a transport service"), (
        "This message is falsely posing as a government officer and requests account access for {subject}; independent {index}.",
        "Evidence indicates this caller is falsely posing as a business representative and collects payments for {subject}; independent {index}.",
        "This profile deceptively claims to represent {subject} and currently solicits customers; independent {index}.",
        "A verified victim report says this account pretends to be official support and requested account access for {subject}; independent {index}.",
    ))
    add(rows, "fresh_personal_information_misuse", IDENTITY_CATEGORY, people, (
        "This applicant uses personal information without permission and opened a new account; independent {index} for {subject}.",
        "Evidence indicates this transaction uses another person's identity fraudulently and made purchases; independent {index} for {subject}.",
        "This user uses financial information without authorization and applied for a loan; independent {index} for {subject}.",
        "A documented account record says this applicant uses a medical identity without consent and obtained medical care; independent {index} for {subject}.",
    ))
    add(rows, "fresh_account_access_and_takeover", IDENTITY_CATEGORY, people, (
        "This user has stolen credentials for an online account and accessed the account; independent {index} for {subject}.",
        "Evidence indicates this account uses account credentials without authorization and took over the account; independent {index} for {subject}.",
        "A verified victim report says this user uses login credentials without permission and changed the account email; independent {index} for {subject}.",
        "This account uses a customer account against the victim's wishes and sent messages to contacts; independent {index} for {subject}.",
    ))
    add(rows, "fresh_authenticity_consent_and_intent_uncertainty", UNCERTAIN_CATEGORY, people, (
        "This profile is impersonating another person, but account authenticity is unclear; independent {index} for {subject}.",
        "This current account may be posing as the victim, while consent is unknown; independent {index} for {subject}.",
        "Evidence indicates a cloned social media account, but authorization cannot be verified; independent {index} for {subject}.",
        "This profile is a fake profile pretending to be another person, while intent cannot be established; independent {index} for {subject}.",
    ))
    add(rows, "fresh_incomplete_media_and_account_evidence", UNCERTAIN_CATEGORY, people, (
        "Only a screenshot is available; this account is posing as another person and identity evidence is incomplete; independent {index} for {subject}.",
        "Unsupported media format; metadata describes a fake profile pretending to be another person and account provenance is unknown; independent {index} for {subject}.",
        "The source account is unavailable for a cloned social media account, and identity cannot be verified; independent {index} for {subject}.",
        "Only a profile photograph is available; this profile may be impersonating the victim and the victim report is unverified; independent {index} for {subject}.",
    ))
    add(rows, "fresh_verified_and_authorized_accounts", NORMAL_CATEGORY,
        ("a financial service", "a government agency", "a marketplace", "a school"), (
        "Written authorization confirms the authorized agent for {subject}; independent safe {index}.",
        "The account holder approved an authorized representative for {subject}; independent safe {index}.",
        "This is a platform-verified official account for {subject}; independent safe {index}.",
        "Identity proofing completed and consent is documented for {subject}; independent safe {index}.",
    ))
    add(rows, "fresh_parody_satire_fan_and_fiction", NORMAL_CATEGORY,
        ("a celebrity", "an imaginary brand", "a football club", "a novel character"), (
        "A clearly labeled parody of {subject} does not claim official affiliation; independent safe {index}.",
        "This fan account for {subject} clearly discloses it is unofficial; independent safe {index}.",
        "A fictional scene about {subject} is fictional and not real; independent safe {index}.",
        "A role-play exercise featuring {subject} does not contact real victims; independent safe {index}.",
    ))
    add(rows, "fresh_awareness_reporting_research_and_help", NORMAL_CATEGORY,
        ("identity theft", "online impersonation", "fake accounts", "account recovery"), (
        "A documentary examines {subject} and no active account is described; independent safe {index}.",
        "Academic research discusses {subject} and contains no real credentials; independent safe {index}.",
        "An impersonation awareness guide explains {subject} and links to the official reporting service; independent safe {index}.",
        "A victim recovery guide covers {subject} and does not contact real victims; independent safe {index}.",
    ))
    add(rows, "fresh_weak_resemblance_name_logo_and_self_claim", NORMAL_CATEGORY,
        ("the same name", "the same profile photograph", "a company logo", "a matching display name"), (
        "A self-reported identity mentions {subject}, but no current misuse or impact is described; independent weak {index}.",
        "The account claims to be official and displays {subject}; no access, transaction, or deceptive contact is established; independent weak {index}.",
        "A person says the page resembles them because of {subject}; no active impersonation evidence exists; independent weak {index}.",
        "An unverified account badge appears with {subject}; identity is not established from this alone; independent weak {index}.",
    ))
    add(rows, "fresh_normal_identity_administration", NORMAL_CATEGORY,
        ("identity settings", "customer account settings", "digital identity guidelines", "authentication documentation"), (
        "A support article documents {subject}; independent ordinary {index}.",
        "An administrator configures {subject}; independent ordinary {index}.",
        "A workshop reviews {subject}; independent ordinary {index}.",
        "Routine product documentation explains {subject}; independent ordinary {index}.",
    ))
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(60):
        owner, action = owners[index % len(owners)]
        rows.append({
            "group": "fresh_established_owner_isolation",
            "text": f"This user uses another person's identity without permission and opened a new account, but an existing {owner} owner controls this case; independent owner {index + 1}.",
            "expected_category": owner, "existing_category": owner,
            "existing_action": action, "existing_review": True,
        })
    return rows


def ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def main() -> None:
    if VERDICT.exists():
        raise FileExistsError(VERDICT)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    artifacts = {str(item["relative_path"]): str(item["sha256"])
                 for item in manifest["artifacts"]}
    frozen = all(live.is_file() and (CDIR / relative).is_file()
                 and artifacts.get(relative) == sha(live) == sha(CDIR / relative)
                 for relative, live in LIVE.items())
    if not frozen:
        raise RuntimeError("Frozen source hash verification failed")
    with DEV.open("r", encoding="utf-8", newline="") as handle:
        development_hashes = {text_hash(row["text"]) for row in csv.DictReader(handle)}
    challenge = build()
    hashes = [text_hash(str(row["text"])) for row in challenge]
    if len(challenge) != 720 or len(set(hashes)) != 720:
        raise RuntimeError("Challenge size or uniqueness failed")
    overlap = set(hashes) & development_hashes
    if overlap:
        raise RuntimeError("Development overlap detected")

    tp = tn = fp = fn = 0
    action_fail = category_fail = data_fail = authority_fail = errors = 0
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "correct": 0})
    for row in challenge:
        group, expected = str(row["group"]), str(row["expected_category"])
        groups[group]["records"] += 1
        try:
            analysis = analyze_identity_theft_impersonation_v2_rc1(str(row["text"]), ["text"])
            decision = apply_identity_theft_impersonation_v2_rc1_fusion(
                category=str(row["existing_category"]), severity="None",
                action=str(row["existing_action"]), confidence=0.71,
                human_review_required=bool(row["existing_review"]),
                reason="Independent baseline.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["existing_action"]), bool(row["existing_review"])
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
            expected_positive, predicted_positive = expected == IDENTITY_CATEGORY, predicted == IDENTITY_CATEGORY
            if expected_positive and predicted_positive:
                tp += 1
            elif expected_positive:
                fn += 1
            elif predicted_positive:
                fp += 1
            else:
                tn += 1
        except Exception:
            errors += 1
    total = len(challenge)
    accuracy = ratio(tp + tn, total)
    precision, recall = ratio(tp, tp + fp), ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    f1 = ratio(2 * precision * recall, precision + recall)
    group_results = {group: {**values, "accuracy": ratio(values["correct"], values["records"])}
                     for group, values in sorted(groups.items())}
    minimum = min(values["accuracy"] for values in group_results.values())
    gate = manifest["independent_gate_frozen_before_holdout"]
    gates = {
        "frozen_source_hashes_verified": frozen, "zero_development_overlap": not overlap,
        "accuracy": accuracy >= gate["minimum_accuracy"],
        "identity_precision": precision >= gate["minimum_identity_precision"],
        "identity_recall": recall >= gate["minimum_identity_recall"],
        "safe_specificity": specificity >= gate["minimum_safe_specificity"],
        "f1": f1 >= gate["minimum_f1"],
        "minimum_group_accuracy": minimum >= gate["minimum_group_accuracy"],
        "action_contract": action_fail <= gate["maximum_action_contract_failures"],
        "category_mix_contract": category_fail <= gate["maximum_category_mix_failures"],
        "data_contract": data_fail <= gate["maximum_data_contract_failures"],
        "authority_contract": authority_fail <= gate["maximum_authority_contract_failures"],
        "processing_contract": errors <= gate["maximum_processing_errors"],
    }
    passed = all(gates.values())
    report = {
        "candidate": CANDIDATE,
        "challenge_version": "2026.09-identity-theft-impersonation-v2-rc1-independent",
        "challenge_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
        "records": total, "unique_texts": len(set(hashes)),
        "positive_records": sum(row["expected_category"] == IDENTITY_CATEGORY for row in challenge),
        "negative_or_boundary_records": sum(row["expected_category"] != IDENTITY_CATEGORY for row in challenge),
        "development_overlap": len(overlap), "accuracy": accuracy,
        "identity_precision": precision, "identity_recall": recall,
        "safe_specificity": specificity, "f1": f1, "minimum_group_accuracy": minimum,
        "false_positives": fp, "false_negatives": fn,
        "action_contract_failures": action_fail, "category_mix_failures": category_fail,
        "data_contract_failures": data_fail, "authority_contract_failures": authority_fail,
        "processing_errors": errors, "group_results": group_results, "gates": gates,
        "passed_synthetic_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_account_suspension_allowed": False,
        "automatic_enforcement_allowed": False, "connected_to_live_moderation": False,
        "raw_challenge_text_stored": False, "individual_predictions_stored": False,
        "real_identity_documents_used": False, "raw_credentials_used": False,
        "complete_personal_identifiers_used": False, "external_provider_used": False,
        "candidate_may_be_modified_using_this_holdout": False,
        "synthetic_evidence_only": True, "external_real_world_accuracy": False,
    }
    verdict = {key: value for key, value in report.items()
               if key not in {"group_results", "positive_records", "negative_or_boundary_records",
                              "false_positives", "false_negatives"}}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    VERDICT.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print("IDENTITY THEFT & IMPERSONATION V2 RC1 INDEPENDENT CHALLENGE\n" + "=" * 60)
    print(f"Candidate: {CANDIDATE}\nRecords: {total}\nPositive records: {report['positive_records']}\nNegative/boundary records: {report['negative_or_boundary_records']}\nDevelopment overlap: {len(overlap)}")
    for label, value in (("Accuracy", accuracy), ("Identity precision", precision),
                         ("Identity recall", recall), ("Safe specificity", specificity),
                         ("F1", f1), ("Minimum group accuracy", minimum)):
        print(f"{label}: {value:.2%}")
    print(f"Action failures: {action_fail}\nCategory failures: {category_fail}\nData-contract failures: {data_fail}\nAuthority failures: {authority_fail}\nProcessing errors: {errors}")
    print("\nGROUP RESULTS\n" + "-" * 60)
    for group, values in group_results.items():
        print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
    print(f"\nPassed synthetic independent readiness gate: {passed}\nEligible for guarded live integration: {passed}")
    print(f"Automatic enforcement allowed: False\nConnected to live moderation: False\nReport: {REPORT}\nVerdict: {VERDICT}")
    print("No raw challenge text, identity documents, credentials, or individual predictions were stored or printed.")
    print("This holdout may not be used to modify V2 RC1.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
