"""Build and evaluate synthetic Intellectual Property V1 RC1 development evidence."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.intellectual_property_v1_rc1_service import (
    IP_ACTION, IP_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_intellectual_property_v1_rc1,
    apply_intellectual_property_v1_rc1_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "datasets" / "development" / "intellectual_property_v1_rc1"
DATASET_PATH = DATASET_DIR / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "intellectual_property" / "v1_rc1_development"
REPORT_PATH = REPORT_DIR / "report.json"
MISMATCH_PATH = REPORT_DIR / "mismatches.json"
OWNER_ACTIONS = {
    "Child Exploitation": "Block and immediately escalate",
    "Malicious Programs": "Block, quarantine, and escalate",
    "Illegal Activities": "Block or restrict and escalate",
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Publishing Private Information": "Refer to human review",
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
    add_group(rows, "unauthorized_audiovisual_distribution", IP_CATEGORY,
              ("copyrighted film", "television episode", "copyrighted song", "music album"), (
        "This account uploads the full {subject} without permission; development case {index}.",
        "Evidence indicates this site streams the full {subject} without authorization; development case {index}.",
        "This user provides unauthorized downloads of a {subject}; rights holder did not authorize it; development case {index}.",
        "A verified rights-holder notice says this post rebroadcasts the full {subject} with no distribution licence; development case {index}.",
    ))
    add_group(rows, "unauthorized_publication_distribution", IP_CATEGORY,
              ("copyrighted book", "ebook", "audiobook", "paywalled article"), (
        "This upload reproduces the entire {subject} without permission; development case {index}.",
        "This account distributes full copies of a {subject} without authorization; development case {index}.",
        "Evidence indicates this site bypasses the paywall and republishes a {subject}; rights holder did not authorize it; development case {index}.",
        "This user sells copies of a {subject} under an unlicensed copy notice; development case {index}.",
    ))
    add_group(rows, "unauthorized_software_and_assets", IP_CATEGORY,
              ("commercial software", "source code", "video game", "stock photograph"), (
        "This account redistributes the package for {subject} without permission; development case {index}.",
        "This user publishes the source code from {subject} without authorization; development case {index}.",
        "Evidence indicates this upload removes the watermark and sells a {subject} as an unauthorized copy; development case {index}.",
        "This site provides unauthorized downloads of {subject}; the licence expressly forbids redistribution; development case {index}.",
    ))
    add_group(rows, "counterfeit_trademark_sales", IP_CATEGORY,
              ("trademarked product", "branded goods", "registered trademark", "protected design"), (
        "This seller lists counterfeit {subject} and falsely presents it as genuine; development case {index}.",
        "Evidence indicates this listing sells counterfeit {subject} without authorization; development case {index}.",
        "This account applies a fake logo to {subject} and offers copies for sale without permission; development case {index}.",
        "A credible rights-holder report says this user imports counterfeit {subject}; development case {index}.",
    ))
    add_group(rows, "uncertain_rights_licence_or_evidence", UNCERTAIN_CATEGORY,
              ("copyrighted film", "source code", "branded goods", "ebook"), (
        "This upload shares full copies of {subject}, but authorization is unclear; development case {index}.",
        "This account distributes full copies of {subject}, while ownership is disputed; development case {index}.",
        "Evidence is incomplete while this site provides unauthorized downloads of {subject}; development case {index}.",
        "Only a thumbnail is available for a listing of counterfeit {subject}, and the rights-holder claim is unverified; development case {index}.",
    ))
    add_group(rows, "legal_exception_scope_uncertain", UNCERTAIN_CATEGORY,
              ("copyrighted movie", "copyrighted book", "copyrighted song", "copyrighted photograph"), (
        "This post reproduces the entire {subject} without permission for criticism, but fair use is unclear; development case {index}.",
        "This upload shares full copies of {subject} without authorization for teaching, and exception scope is unresolved; development case {index}.",
        "This account streams the full {subject} without permission as parody, while jurisdiction is unknown; development case {index}.",
        "This user distributes full copies of {subject} without authorization for academic research; fair dealing is unclear; development case {index}.",
    ))
    add_group(rows, "authorized_original_and_official", NORMAL_CATEGORY,
              ("copyrighted film", "source code", "stock photograph", "paid course"), (
        "The rights holder authorized this official publisher upload of {subject}; safe development {index}.",
        "Written permission and a valid distribution licence cover this {subject}; safe development {index}.",
        "This is a user-created original {subject} and permission is documented; safe development {index}.",
        "The official store link offers {subject} through licensed distribution; safe development {index}.",
    ))
    add_group(rows, "public_domain_and_open_licence", NORMAL_CATEGORY,
              ("copyrighted artwork", "source code", "copyrighted book", "stock photograph"), (
        "The {subject} is public domain and links to the official source; safe development {index}.",
        "The creator released this {subject} under CC0; safe development {index}.",
        "A compatible Creative Commons licence permits redistribution of this {subject}; safe development {index}.",
        "An open-source licence permits reuse of this {subject}; safe development {index}.",
    ))
    add_group(rows, "bounded_reporting_criticism_and_access", NORMAL_CATEGORY,
              ("copyrighted film", "copyrighted book", "copyrighted song", "copyrighted photograph"), (
        "A critical review uses a brief clip for review from a {subject} and does not substitute for the original; safe development {index}.",
        "News reporting includes a short attributed excerpt from a {subject} and links to the official source; safe development {index}.",
        "Teaching uses a small attributed quotation from a {subject}, only what is needed for commentary; safe development {index}.",
        "An accessibility format uses only what is needed for commentary about a {subject}; safe development {index}.",
    ))
    add_group(rows, "weak_similarity_claim_and_metadata", NORMAL_CATEGORY,
              ("same title", "contains a logo", "similar visual style", "shows a watermark"), (
        "A self-reported owner points to {subject}, but no copying or distribution act is described; weak development {index}.",
        "A post alleges infringement because it {subject}; no protected item or unauthorized act is established; weak development {index}.",
        "Two works have a {subject}; this is only a similarity claim; weak development {index}.",
        "A page has a copyright notice and {subject}; no active rights-impacting conduct is described; weak development {index}.",
    ))
    add_group(rows, "ordinary_ip_information", NORMAL_CATEGORY,
              ("copyright registration guide", "trademark application guide", "licence settings", "brand style guide"), (
        "A help page explains the {subject}; ordinary development {index}.",
        "This is routine documentation about a {subject}; ordinary development {index}.",
        "A student reads a {subject}; ordinary development {index}.",
        "The official website publishes its {subject}; ordinary development {index}.",
    ))
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(50):
        owner, action = owners[index % len(owners)]
        rows.append({
            "record_id": f"ESTABLISHED_OWNER-{index + 1:03d}",
            "group": "established_category_owner_isolation",
            "text": f"This account uploads the full copyrighted film without permission, but an existing {owner} owner controls this record; development owner {index + 1}.",
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
            analysis = analyze_intellectual_property_v1_rc1(str(row["text"]), ["text"])
            decision = apply_intellectual_property_v1_rc1_fusion(
                category=str(row["existing_category"]), severity="None",
                action=str(row["existing_action"]), confidence=0.70,
                human_review_required=bool(row["existing_review"]),
                reason="Development baseline.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["existing_action"]), bool(row["existing_review"])
            if expected == IP_CATEGORY:
                expected_action, expected_review = IP_ACTION, True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action, expected_review = UNCERTAIN_ACTION, True
            action_ok = (decision["action"] == expected_action and
                         bool(decision["human_review_required"]) == expected_review and
                         decision["automatic_enforcement_allowed"] is False)
            action_failures += int(not action_ok)
            category_failures += int(not correct)
            data_failures += int(analysis["raw_copyrighted_works_stored"] is not False or
                                 analysis["pirated_material_stored"] is not False or
                                 analysis["complainant_private_identifiers_stored"] is not False)
            authority_failures += int(any(analysis[key] is not False for key in (
                "ownership_inferred_from_appearance", "licence_validity_determined",
                "legal_exception_determined", "legal_determination_made",
                "external_provider_used", "external_transmission_allowed",
                "automatic_takedown_allowed")))
            expected_positive, predicted_positive = expected == IP_CATEGORY, predicted == IP_CATEGORY
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
        "accuracy": accuracy >= 0.95, "ip_precision": precision >= 0.97,
        "ip_recall": recall >= 0.95, "safe_specificity": specificity >= 0.99,
        "f1": f1 >= 0.96, "minimum_group_accuracy": minimum >= 0.92,
        "action_contract": action_failures == 0, "category_mix_contract": category_failures == 0,
        "data_contract": data_failures == 0, "authority_contract": authority_failures == 0,
        "processing_contract": errors == 0,
    }
    return {
        "version": "2026.09-intellectual-property-v1-rc1-development",
        "records": len(records), "unique_texts": len(set(hashes)),
        "label_counts": dict(Counter(str(row["expected_category"]) for row in records)),
        "accuracy": accuracy, "ip_precision": precision, "ip_recall": recall,
        "safe_specificity": specificity, "f1": f1, "minimum_group_accuracy": minimum,
        "false_positives": fp, "false_negatives": fn,
        "action_contract_failures": action_failures, "category_mix_failures": category_failures,
        "data_contract_failures": data_failures, "authority_contract_failures": authority_failures,
        "processing_errors": errors, "group_results": group_results, "gates": gates,
        "passed_development_gate": all(gates.values()),
        "raw_copyrighted_works_used": False, "pirated_material_used": False,
        "private_claimant_data_used": False, "external_provider_used": False,
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
    print("INTELLECTUAL PROPERTY V1 RC1 DEVELOPMENT\n" + "=" * 60)
    print(f"Records: {result['records']}\nUnique texts: {result['unique_texts']}")
    for label, key in (("Accuracy", "accuracy"), ("IP precision", "ip_precision"),
                       ("IP recall", "ip_recall"), ("Safe specificity", "safe_specificity"),
                       ("F1", "f1"), ("Minimum group accuracy", "minimum_group_accuracy")):
        print(f"{label}: {result[key]:.2%}")
    print(f"Action failures: {result['action_contract_failures']}\nCategory failures: {result['category_mix_failures']}\nData-contract failures: {result['data_contract_failures']}\nAuthority failures: {result['authority_contract_failures']}\nProcessing errors: {result['processing_errors']}")
    print("\nGROUP RESULTS\n" + "-" * 60)
    for group, values in result["group_results"].items():
        print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
    print(f"\nPassed development gate: {result['passed_development_gate']}\nDataset: {DATASET_PATH}\nReport: {REPORT_PATH}")
    print("Raw copyrighted works used: False\nExternal provider used: False\nConnected to live moderation: False")
    print("This is synthetic policy evidence, not real-world legal accuracy.")
    if not result["passed_development_gate"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
