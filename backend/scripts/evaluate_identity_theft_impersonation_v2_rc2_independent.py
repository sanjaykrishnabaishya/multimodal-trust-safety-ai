"""Aggregate-only independent challenge for frozen Identity V2 RC2."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.identity_theft_impersonation_v2_rc2_service import (
    IDENTITY_ACTION, IDENTITY_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_identity_theft_impersonation_v2_rc2,
    apply_identity_theft_impersonation_v2_rc2_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "identity-theft-impersonation-v2-rc2"
CDIR = BACKEND / "storage" / "candidates" / CANDIDATE
MANIFEST = CDIR / "manifest.json"
VERDICT = CDIR / "independent_evaluation_verdict.json"
RC1_DEV = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc1" / "development.csv"
RC2_DEV = ROOT / "datasets" / "development" / "identity_theft_impersonation_v2_rc2" / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "identity_theft_impersonation" / "v2_rc2_independent"
REPORT = REPORT_DIR / "aggregate_report.json"
LIVE = {
    "source_snapshot/identity_theft_impersonation_v2_rc2_service.py": BACKEND / "app" / "services" / "identity_theft_impersonation_v2_rc2_service.py",
    "policy_snapshot/identity_theft_impersonation_v2_rc2_policy.json": BACKEND / "app" / "evidence" / "identity_theft_impersonation_v2_rc2_policy.json",
    "dependency_snapshot/identity_theft_impersonation_v2_rc1_service.py": BACKEND / "app" / "services" / "identity_theft_impersonation_v2_rc1_service.py",
    "dependency_snapshot/identity_theft_impersonation_v2_rc1_policy.json": BACKEND / "app" / "evidence" / "identity_theft_impersonation_v2_rc1_policy.json",
    "source_snapshot/evaluate_identity_theft_impersonation_v2_rc2_development.py": BACKEND / "scripts" / "evaluate_identity_theft_impersonation_v2_rc2_development.py",
    "source_snapshot/freeze_identity_theft_impersonation_v2_rc2.py": BACKEND / "scripts" / "freeze_identity_theft_impersonation_v2_rc2.py",
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


def add(
    rows: list[dict[str, Any]], group: str, expected: str,
    subjects: tuple[str, ...], templates: tuple[str, ...], *,
    owner: str = NORMAL_CATEGORY, action: str = "Allow", review: bool = False,
) -> None:
    for index in range(80):
        rows.append({
            "group": group,
            "text": templates[index % len(templates)].format(
                subject=subjects[index % len(subjects)], index=index + 1),
            "expected_category": expected,
            "existing_category": owner,
            "existing_action": action,
            "existing_review": review,
        })


def build() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    people = ("a customer", "a tenant", "a patient", "a voter")
    add(rows, "fresh_natural_first_person_impersonation", IDENTITY_CATEGORY, people, (
        "Someone is impersonating me using a cloned account and sends messages to friends; independent RC2 {index} for {subject}.",
        "This person is pretending to be me, created a fake profile, and contacts customers; independent RC2 {index} for {subject}.",
        "The profile is posing as me and using my photograph to request account access; independent RC2 {index} for {subject}.",
        "Someone has copied my profile and opened a fake account to contact colleagues; independent RC2 {index} for {subject}.",
    ))
    add(rows, "fresh_natural_person_and_company_impersonation", IDENTITY_CATEGORY, people, (
        "This account is impersonating her, created a fake account, and sends messages to {subject}; independent RC2 {index}.",
        "The profile is pretending to be him and using his photo to collect payments from {subject}; independent RC2 {index}.",
        "They are impersonating our company using the cloned account to solicit {subject}; independent RC2 {index}.",
        "This profile is posing as our company and created a fake profile to request access from {subject}; independent RC2 {index}.",
    ))
    add(rows, "fresh_natural_identity_theft_transactions", IDENTITY_CATEGORY, people, (
        "Someone has stolen my identity and opened an account in my name; independent RC2 {index} for {subject}.",
        "The fraudster committed identity fraud and made purchases in my name; independent RC2 {index} for {subject}.",
        "The attacker used a stolen identity and ran up charges in my name; independent RC2 {index} for {subject}.",
        "Someone is committing identity theft and claimed benefits in my name; independent RC2 {index} for {subject}.",
    ))
    add(rows, "fresh_canonical_identity_evidence", IDENTITY_CATEGORY, people, (
        "This profile is impersonating another person and currently sends messages to contacts; independent RC2 {index} for {subject}.",
        "Evidence indicates this user uses personal information without permission and opened a new account; independent RC2 {index} for {subject}.",
        "This caller is falsely posing as a government officer and requests account access; independent RC2 {index} for {subject}.",
        "A verified victim report says this user uses stolen credentials and accessed the account; independent RC2 {index} for {subject}.",
    ))
    add(rows, "fresh_natural_identity_uncertainty", UNCERTAIN_CATEGORY, people, (
        "This person may be impersonating me, but identity remains unverified; independent RC2 {index} for {subject}.",
        "The profile might be impersonating her and could be authorized; independent RC2 {index} for {subject}.",
        "Someone is possibly impersonating our company, but authenticity is uncertain; independent RC2 {index} for {subject}.",
        "This account is pretending to be him, but there is not enough evidence to verify; independent RC2 {index} for {subject}.",
    ))
    add(rows, "fresh_incomplete_identity_evidence", UNCERTAIN_CATEGORY, people, (
        "Only a screenshot is available; this account is posing as another person and identity evidence is incomplete; independent RC2 {index} for {subject}.",
        "A cloned social media account is described, but authorization cannot be verified; independent RC2 {index} for {subject}.",
        "The source profile is unavailable while an account may be impersonating the victim; independent RC2 {index} for {subject}.",
        "A fake profile may be posing as a business, while account provenance is unknown; independent RC2 {index} for {subject}.",
    ))
    add(rows, "fresh_authorized_and_verified_identity", NORMAL_CATEGORY, people, (
        "Written authorization confirms the representative acts for {subject}; independent RC2 safe {index}.",
        "The account holder approved this authorized agent for {subject}; independent RC2 safe {index}.",
        "This is a platform-verified official account for {subject}; independent RC2 safe {index}.",
        "Identity proofing completed and consent is documented for {subject}; independent RC2 safe {index}.",
    ))
    add(rows, "fresh_parody_reporting_training_and_recovery", NORMAL_CATEGORY, people, (
        "A clearly labelled parody says it is pretending to be me and claims no official affiliation; independent RC2 safe {index} for {subject}.",
        "A news report discusses someone impersonating her and describes no active account; independent RC2 safe {index} for {subject}.",
        "Security training explains using a cloned account and contains no real credentials; independent RC2 safe {index} for {subject}.",
        "A victim recovery guide discusses identity theft and does not contact victims; independent RC2 safe {index} for {subject}.",
    ))
    add(rows, "fresh_weak_and_ordinary_identity_context", NORMAL_CATEGORY, people, (
        "The profile has the same name, but no current misuse act is described; independent RC2 weak {index} for {subject}.",
        "A page uses a company logo, but no deception, contact, access, or transaction is established; independent RC2 weak {index} for {subject}.",
        "A support article documents identity settings for {subject}; independent RC2 ordinary {index}.",
        "A workshop reviews digital identity guidelines for {subject}; independent RC2 ordinary {index}.",
    ))
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(80):
        owner, action = owners[index % len(owners)]
        rows.append({
            "group": "fresh_established_owner_isolation",
            "text": f"Someone is impersonating me using a cloned account, while an existing {owner} owner controls this case; independent RC2 owner {index + 1}.",
            "expected_category": owner,
            "existing_category": owner,
            "existing_action": action,
            "existing_review": True,
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
    frozen = all(
        live.is_file() and (CDIR / relative).is_file()
        and artifacts.get(relative) == sha(live) == sha(CDIR / relative)
        for relative, live in LIVE.items()
    )
    if not frozen:
        raise RuntimeError("Frozen source or dependency hash verification failed")

    development_hashes: set[str] = set()
    for path in (RC1_DEV, RC2_DEV):
        with path.open("r", encoding="utf-8", newline="") as handle:
            development_hashes.update(text_hash(row["text"]) for row in csv.DictReader(handle))
    challenge = build()
    hashes = [text_hash(str(row["text"])) for row in challenge]
    if len(challenge) != 800 or len(set(hashes)) != 800:
        raise RuntimeError("Challenge size or uniqueness failed")
    overlap = set(hashes) & development_hashes
    if overlap:
        raise RuntimeError("Development overlap detected")

    tp = tn = fp = fn = 0
    action_fail = category_fail = data_fail = authority_fail = errors = 0
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "correct": 0})
    for row in challenge:
        group = str(row["group"])
        expected = str(row["expected_category"])
        groups[group]["records"] += 1
        try:
            analysis = analyze_identity_theft_impersonation_v2_rc2(str(row["text"]), ["text"])
            decision = apply_identity_theft_impersonation_v2_rc2_fusion(
                category=str(row["existing_category"]), severity="None",
                action=str(row["existing_action"]), confidence=0.71,
                human_review_required=bool(row["existing_review"]),
                reason="Independent baseline.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action = str(row["existing_action"])
            expected_review = bool(row["existing_review"])
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
        except Exception:
            errors += 1

    total = len(challenge)
    accuracy = ratio(tp + tn, total)
    precision = ratio(tp, tp + fp)
    recall = ratio(tp, tp + fn)
    specificity = ratio(tn, tn + fp)
    f1 = ratio(2 * precision * recall, precision + recall)
    group_results = {
        group: {**values, "accuracy": ratio(values["correct"], values["records"])}
        for group, values in sorted(groups.items())
    }
    minimum = min(values["accuracy"] for values in group_results.values())
    gate = manifest["independent_gate_frozen_before_holdout"]
    gates = {
        "frozen_source_hashes_verified": frozen,
        "zero_development_overlap": not overlap,
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
        "challenge_version": "2026.09-identity-theft-impersonation-v2-rc2-independent",
        "challenge_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
        "records": total,
        "unique_texts": len(set(hashes)),
        "positive_records": sum(row["expected_category"] == IDENTITY_CATEGORY for row in challenge),
        "negative_or_boundary_records": sum(row["expected_category"] != IDENTITY_CATEGORY for row in challenge),
        "development_overlap": len(overlap),
        "accuracy": accuracy,
        "identity_precision": precision,
        "identity_recall": recall,
        "safe_specificity": specificity,
        "f1": f1,
        "minimum_group_accuracy": minimum,
        "false_positives": fp,
        "false_negatives": fn,
        "action_contract_failures": action_fail,
        "category_mix_failures": category_fail,
        "data_contract_failures": data_fail,
        "authority_contract_failures": authority_fail,
        "processing_errors": errors,
        "group_results": group_results,
        "gates": gates,
        "passed_synthetic_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_account_suspension_allowed": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "real_identity_documents_used": False,
        "raw_credentials_used": False,
        "complete_personal_identifiers_used": False,
        "external_provider_used": False,
        "candidate_may_be_modified_using_this_holdout": False,
        "rc1_independent_examples_used": False,
        "rc1_individual_predictions_used": False,
        "synthetic_evidence_only": True,
        "external_real_world_accuracy": False,
    }
    verdict = {key: value for key, value in report.items()
               if key not in {"group_results", "positive_records", "negative_or_boundary_records",
                              "false_positives", "false_negatives"}}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    VERDICT.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print("IDENTITY THEFT & IMPERSONATION V2 RC2 INDEPENDENT CHALLENGE\n" + "=" * 60)
    print(f"Candidate: {CANDIDATE}\nRecords: {total}")
    print(f"Positive records: {report['positive_records']}")
    print(f"Negative/boundary records: {report['negative_or_boundary_records']}")
    print(f"Development overlap: {len(overlap)}")
    for label, value in (
        ("Accuracy", accuracy), ("Identity precision", precision),
        ("Identity recall", recall), ("Safe specificity", specificity),
        ("F1", f1), ("Minimum group accuracy", minimum),
    ):
        print(f"{label}: {value:.2%}")
    print(f"Action failures: {action_fail}\nCategory failures: {category_fail}")
    print(f"Data-contract failures: {data_fail}\nAuthority failures: {authority_fail}")
    print(f"Processing errors: {errors}\n\nGROUP RESULTS\n" + "-" * 60)
    for group, values in group_results.items():
        print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
    print(f"\nPassed synthetic independent readiness gate: {passed}")
    print(f"Eligible for guarded live integration: {passed}")
    print("Automatic enforcement allowed: False\nConnected to live moderation: False")
    print(f"Report: {REPORT}\nVerdict: {VERDICT}")
    print("No raw challenge text, identity documents, credentials, or individual predictions were stored or printed.")
    print("This holdout may not be used to modify V2 RC2.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
