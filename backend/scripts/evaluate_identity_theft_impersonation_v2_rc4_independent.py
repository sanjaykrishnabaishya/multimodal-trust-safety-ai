"""Aggregate-only independent challenge for frozen Identity V2 RC4."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc4_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc4,
    apply_identity_theft_impersonation_v2_rc4_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "identity-theft-impersonation-v2-rc4"
CDIR = BACKEND / "storage/candidates" / CANDIDATE
MANIFEST = CDIR / "manifest.json"
VERDICT = CDIR / "independent_evaluation_verdict.json"
DEV_PATHS = tuple(ROOT / "datasets/development" / f"identity_theft_impersonation_v2_rc{number}" / "development.csv" for number in (1, 2, 3, 4))
REPORT_DIR = ROOT / "reports/evaluation/identity_theft_impersonation/v2_rc4_independent"
REPORT = REPORT_DIR / "aggregate_report.json"
LIVE = {
    "source_snapshot/identity_theft_impersonation_v2_rc4_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc4_service.py",
    "policy_snapshot/identity_theft_impersonation_v2_rc4_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc4_policy.json",
    "dependency_snapshot/identity_theft_impersonation_v2_rc3_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc3_service.py",
    "dependency_snapshot/identity_theft_impersonation_v2_rc3_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc3_policy.json",
    "dependency_snapshot/identity_theft_impersonation_v2_rc2_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc2_service.py",
    "dependency_snapshot/identity_theft_impersonation_v2_rc2_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc2_policy.json",
    "dependency_snapshot/identity_theft_impersonation_v2_rc1_service.py": BACKEND / "app/services/identity_theft_impersonation_v2_rc1_service.py",
    "dependency_snapshot/identity_theft_impersonation_v2_rc1_policy.json": BACKEND / "app/evidence/identity_theft_impersonation_v2_rc1_policy.json",
    "source_snapshot/evaluate_identity_theft_impersonation_v2_rc4_development.py": BACKEND / "scripts/evaluate_identity_theft_impersonation_v2_rc4_development.py",
    "source_snapshot/freeze_identity_theft_impersonation_v2_rc4.py": BACKEND / "scripts/freeze_identity_theft_impersonation_v2_rc4.py",
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
        for chunk in iter(lambda: handle.read(1024 * 1024), b""): digest.update(chunk)
    return digest.hexdigest()


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def add(rows: list[dict[str, Any]], group: str, expected: str,
        templates: tuple[str, ...]) -> None:
    subjects = ("a cardholder", "a patient", "a renter", "a subscriber", "a merchant")
    for index in range(100):
        rows.append({
            "group": group,
            "text": templates[index % len(templates)].format(subject=subjects[index % 5], index=index + 1),
            "expected_category": expected, "existing_category": NORMAL_CATEGORY,
            "existing_action": "Allow", "existing_review": False,
        })


def build() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    add(rows, "fresh_person_impersonation_with_active_misuse", IDENTITY_CATEGORY, (
        "This profile is impersonating me and sends messages to contacts; RC4 challenge {index} for {subject}.",
        "The account pretends to be her and requests payments from friends; RC4 challenge {index} for {subject}.",
        "This person is posing as him and requests account access from coworkers; RC4 challenge {index} for {subject}.",
        "Evidence indicates a fake profile pretending to be a resident and solicits customers; RC4 challenge {index} for {subject}.",
    ))
    add(rows, "fresh_entity_official_and_support_impersonation", IDENTITY_CATEGORY, (
        "This message falsely represents a company and requests credentials from {subject}; RC4 challenge {index}.",
        "The caller is pretending to be a government officer and asks for payment from {subject}; RC4 challenge {index}.",
        "This account impersonates official support and sends messages to {subject}; RC4 challenge {index}.",
        "The profile is posing as a business representative and solicits customers; RC4 challenge {index} for {subject}.",
    ))
    add(rows, "fresh_identity_theft_transactions", IDENTITY_CATEGORY, (
        "Someone has stolen my identity and made purchases in my name; RC4 challenge {index} for {subject}.",
        "The fraudster committed identity fraud and opened an account in my name; RC4 challenge {index} for {subject}.",
        "Someone is committing identity theft and ran up charges in my name; RC4 challenge {index} for {subject}.",
        "Evidence indicates this user uses personal information without permission and claimed benefits; RC4 challenge {index} for {subject}.",
    ))
    add(rows, "fresh_account_access_and_takeover", IDENTITY_CATEGORY, (
        "This user uses stolen credentials and accessed the account; RC4 challenge {index} for {subject}.",
        "Evidence indicates this account uses login credentials without authorization and changed the account email; RC4 challenge {index} for {subject}.",
        "A verified victim report says this user uses an account without permission and sent messages to contacts; RC4 challenge {index} for {subject}.",
        "This account uses financial information without authorization and applied for a loan; RC4 challenge {index} for {subject}.",
    ))
    add(rows, "fresh_plausible_identity_uncertainty", UNCERTAIN_CATEGORY, (
        "This account may be impersonating a person, but authenticity is uncertain; RC4 challenge {index} for {subject}.",
        "A fake profile might be posing as a company while consent is unknown; RC4 challenge {index} for {subject}.",
        "The caller may be pretending to be official support, but intent cannot be established; RC4 challenge {index} for {subject}.",
        "A cloned account is described while authorization cannot be verified; RC4 challenge {index} for {subject}.",
    ))
    add(rows, "fresh_incomplete_source_and_identity_evidence", UNCERTAIN_CATEGORY, (
        "The source profile is unavailable for a possible fake profile; RC4 challenge {index} for {subject}.",
        "Only a screenshot is available for a possible cloned account; RC4 challenge {index} for {subject}.",
        "A possible account takeover is reported while identity evidence is incomplete; RC4 challenge {index} for {subject}.",
        "A profile may be impersonating a person while account provenance is unknown; RC4 challenge {index} for {subject}.",
    ))
    add(rows, "fresh_authorized_and_verified_accounts", NORMAL_CATEGORY, (
        "Written authorization confirms the owner-approved representative for {subject}; RC4 challenge safe {index}.",
        "The account holder approved an authorized agent and consent is documented; RC4 challenge safe {index} for {subject}.",
        "This is a platform-verified official account for {subject}; RC4 challenge safe {index}.",
        "Identity proofing completed for this authorized account; RC4 challenge safe {index} for {subject}.",
    ))
    add(rows, "fresh_parody_reporting_research_and_help", NORMAL_CATEGORY, (
        "A clearly labeled parody pretends to be a fictional mayor and claims no official affiliation; RC4 challenge safe {index} for {subject}.",
        "A documentary reports on government impersonation and no active account is described; RC4 challenge safe {index} for {subject}.",
        "Academic research discusses fake support accounts and contains no real credentials; RC4 challenge safe {index} for {subject}.",
        "A victim recovery guide explains account takeover and does not contact real victims; RC4 challenge safe {index} for {subject}.",
    ))
    add(rows, "fresh_weak_resemblance_and_ordinary_identity", NORMAL_CATEGORY, (
        "The page has the same name, but no active misuse or victim impact is described; RC4 challenge weak {index} for {subject}.",
        "A profile shows a company logo, but no deceptive contact, access, or transaction is established; RC4 challenge weak {index} for {subject}.",
        "A photograph resembles someone, but identity is not established from appearance alone; RC4 challenge weak {index} for {subject}.",
        "A public help center explains authentication settings; RC4 challenge ordinary {index} for {subject}.",
    ))
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(100):
        owner, action = owners[index % len(owners)]
        rows.append({
            "group": "fresh_established_category_owner_isolation",
            "text": f"This account impersonates official support and requests credentials, while an existing {owner} owner controls the case; RC4 challenge owner {index + 1}.",
            "expected_category": owner, "existing_category": owner,
            "existing_action": action, "existing_review": True,
        })
    return rows


def ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def main() -> None:
    if VERDICT.exists(): raise FileExistsError(VERDICT)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    artifacts = {str(item["relative_path"]): str(item["sha256"]) for item in manifest["artifacts"]}
    frozen = all(live.is_file() and (CDIR / relative).is_file()
                 and artifacts.get(relative) == sha(live) == sha(CDIR / relative)
                 for relative, live in LIVE.items())
    if not frozen: raise RuntimeError("Frozen source or dependency hash verification failed")
    development_hashes: set[str] = set()
    for path in DEV_PATHS:
        with path.open("r", encoding="utf-8", newline="") as handle:
            development_hashes.update(text_hash(row["text"]) for row in csv.DictReader(handle))
    challenge = build()
    hashes = [text_hash(str(row["text"])) for row in challenge]
    if len(challenge) != 1000 or len(set(hashes)) != 1000: raise RuntimeError("Challenge size or uniqueness failed")
    overlap = set(hashes) & development_hashes
    if overlap: raise RuntimeError("Development overlap detected")

    tp = tn = fp = fn = 0
    action_fail = category_fail = data_fail = authority_fail = errors = 0
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "correct": 0})
    for row in challenge:
        group, expected = str(row["group"]), str(row["expected_category"])
        groups[group]["records"] += 1
        try:
            analysis = analyze_identity_theft_impersonation_v2_rc4(str(row["text"]), ["text"])
            decision = apply_identity_theft_impersonation_v2_rc4_fusion(
                category=str(row["existing_category"]), severity="None",
                action=str(row["existing_action"]), confidence=.71,
                human_review_required=bool(row["existing_review"]),
                reason="Independent baseline.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["existing_action"]), bool(row["existing_review"])
            if expected == IDENTITY_CATEGORY: expected_action, expected_review = IDENTITY_ACTION, True
            elif expected == UNCERTAIN_CATEGORY: expected_action, expected_review = UNCERTAIN_ACTION, True
            action_fail += int(decision["action"] != expected_action
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
            ep, pp = expected == IDENTITY_CATEGORY, predicted == IDENTITY_CATEGORY
            if ep and pp: tp += 1
            elif ep: fn += 1
            elif pp: fp += 1
            else: tn += 1
        except Exception: errors += 1

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
        "candidate": CANDIDATE, "challenge_version": "2026.09-identity-theft-impersonation-v2-rc4-independent",
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
        "automatic_account_suspension_allowed": False, "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False, "raw_challenge_text_stored": False,
        "individual_predictions_stored": False, "real_identity_documents_used": False,
        "raw_credentials_used": False, "complete_personal_identifiers_used": False,
        "external_provider_used": False, "candidate_may_be_modified_using_this_holdout": False,
        "prior_independent_examples_used": False, "prior_individual_predictions_used": False,
        "synthetic_evidence_only": True, "external_real_world_accuracy": False,
    }
    verdict = {key: value for key, value in report.items()
               if key not in {"group_results", "positive_records", "negative_or_boundary_records",
                              "false_positives", "false_negatives"}}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    VERDICT.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print("IDENTITY THEFT & IMPERSONATION V2 RC4 INDEPENDENT CHALLENGE\n" + "=" * 60)
    print(f"Candidate: {CANDIDATE}\nRecords: {total}\nPositive records: {report['positive_records']}\nNegative/boundary records: {report['negative_or_boundary_records']}\nDevelopment overlap: {len(overlap)}")
    for label, value in (("Accuracy", accuracy), ("Identity precision", precision),
                         ("Identity recall", recall), ("Safe specificity", specificity),
                         ("F1", f1), ("Minimum group accuracy", minimum)):
        print(f"{label}: {value:.2%}")
    print(f"Action failures: {action_fail}\nCategory failures: {category_fail}\nData-contract failures: {data_fail}\nAuthority failures: {authority_fail}\nProcessing errors: {errors}")
    print("\nGROUP RESULTS\n" + "-" * 60)
    for group, values in group_results.items(): print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
    print(f"\nPassed synthetic independent readiness gate: {passed}\nEligible for guarded live integration: {passed}")
    print(f"Automatic enforcement allowed: False\nConnected to live moderation: False\nReport: {REPORT}\nVerdict: {VERDICT}")
    print("No raw challenge rows, identity documents, credentials, or individual predictions were stored or printed.")
    print("This holdout may not be used to modify V2 RC4.")
    if not passed: raise SystemExit(1)


if __name__ == "__main__": main()
