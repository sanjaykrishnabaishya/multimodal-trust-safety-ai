"""Aggregate-only independent challenge for frozen Intellectual Property V1 RC1."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.intellectual_property_v1_rc1_service import (
    IP_ACTION, IP_CATEGORY, NORMAL_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_intellectual_property_v1_rc1,
    apply_intellectual_property_v1_rc1_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "intellectual-property-v1-rc1"
CDIR = BACKEND / "storage" / "candidates" / CANDIDATE
MANIFEST = CDIR / "manifest.json"
VERDICT = CDIR / "independent_evaluation_verdict.json"
DEV = ROOT / "datasets" / "development" / "intellectual_property_v1_rc1" / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "intellectual_property" / "v1_rc1_independent"
REPORT = REPORT_DIR / "aggregate_report.json"
LIVE = {
    "source_snapshot/intellectual_property_v1_rc1_service.py": BACKEND / "app" / "services" / "intellectual_property_v1_rc1_service.py",
    "policy_snapshot/intellectual_property_v1_rc1_policy.json": BACKEND / "app" / "evidence" / "intellectual_property_v1_rc1_policy.json",
    "source_snapshot/evaluate_intellectual_property_v1_rc1_development.py": BACKEND / "scripts" / "evaluate_intellectual_property_v1_rc1_development.py",
    "source_snapshot/freeze_intellectual_property_v1_rc1.py": BACKEND / "scripts" / "freeze_intellectual_property_v1_rc1.py",
}
OWNER_ACTIONS = {
    "Child Exploitation": "Block and immediately escalate",
    "Malicious Programs": "Block, quarantine, and escalate",
    "Illegal Activities": "Block or restrict and escalate",
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Invasion of Privacy": "Restrict and send for human review",
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
    add(rows, "fresh_unauthorized_screen_and_audio", IP_CATEGORY,
        ("copyrighted movie", "full episode", "copyrighted song", "music album"), (
        "A verified rights-holder notice reports that this stream uploads the full {subject}; it is an unauthorized copy; independent {index}.",
        "Currently this account streams the full {subject} without permission; independent {index}.",
        "This site mirrors the download for a {subject} without authorization; independent {index}.",
        "Evidence indicates this user provides unauthorized downloads of a {subject}; no distribution licence exists; independent {index}.",
    ))
    add(rows, "fresh_unauthorized_books_courses_and_news", IP_CATEGORY,
        ("copyrighted book", "audiobook", "paid course", "subscription publication"), (
        "This post reproduces the entire {subject} without permission; independent {index}.",
        "Currently this account shares full copies of the {subject} without authorization; independent {index}.",
        "Evidence indicates this site resells access to the {subject}; the rights holder did not authorize it; independent {index}.",
        "A credible rights-holder report says this upload distributes full copies of the {subject} with no distribution licence; independent {index}.",
    ))
    add(rows, "fresh_unauthorized_code_games_and_images", IP_CATEGORY,
        ("commercial software", "source code", "video game", "copyrighted photograph"), (
        "This user redistributes the package containing {subject} without permission; independent {index}.",
        "Evidence indicates this post publishes the source code from {subject} without authorization; independent {index}.",
        "This account removes the watermark and sells a {subject} as an unauthorized copy; independent {index}.",
        "Currently this site provides unauthorized downloads of {subject}; the licence expressly forbids redistribution; independent {index}.",
    ))
    add(rows, "fresh_counterfeit_listings", IP_CATEGORY,
        ("trademarked product", "branded goods", "registered trademark", "protected design"), (
        "Evidence indicates this seller lists counterfeit {subject} and falsely presents it as genuine; independent {index}.",
        "This listing sells counterfeit {subject} without authorization; independent {index}.",
        "Currently this account applies a fake logo to {subject} and offers copies for sale without permission; independent {index}.",
        "A verified rights-holder notice says this user imports counterfeit {subject}; independent {index}.",
    ))
    add(rows, "fresh_unknown_ownership_licence_and_provenance", UNCERTAIN_CATEGORY,
        ("copyrighted movie", "source code", "branded goods", "ebook"), (
        "This account distributes full copies of {subject}, but permission cannot be verified; independent {index}.",
        "Currently this upload shares full copies of {subject}, while licence scope is unclear; independent {index}.",
        "This site provides unauthorized downloads of {subject}, but provenance is unknown; independent {index}.",
        "A listing of counterfeit {subject} is described, while ownership is disputed; independent {index}.",
    ))
    add(rows, "fresh_exception_and_jurisdiction_boundary", UNCERTAIN_CATEGORY,
        ("copyrighted film", "copyrighted book", "copyrighted song", "copyrighted artwork"), (
        "This account uploads the full {subject} without permission for commentary, but applicable law is unclear; independent {index}.",
        "This post reproduces the entire {subject} without authorization for scholarship, while fair use is unclear; independent {index}.",
        "Currently this stream rebroadcasts the full {subject} without permission as pastiche; exception scope is unresolved; independent {index}.",
        "This user shares full copies of {subject} without authorization for library preservation; jurisdiction is unknown; independent {index}.",
    ))
    add(rows, "fresh_authorized_and_creator_owned", NORMAL_CATEGORY,
        ("copyrighted movie", "source code", "stock photograph", "paid course"), (
        "Written permission covers the official publisher upload of this {subject}; independent safe {index}.",
        "The rights holder authorized licensed distribution of the {subject}; independent safe {index}.",
        "This creator-owned original {subject} has permission documented; independent safe {index}.",
        "A valid distribution licence covers the official store link for {subject}; independent safe {index}.",
    ))
    add(rows, "fresh_public_domain_and_permissive_licences", NORMAL_CATEGORY,
        ("copyrighted artwork", "source code", "copyrighted book", "stock photograph"), (
        "This {subject} is marked public domain and links to the official source; independent safe {index}.",
        "The creator placed this {subject} under CC0; independent safe {index}.",
        "A compatible Creative Commons licence permits redistribution of this {subject}; independent safe {index}.",
        "The open-source licence permits reuse of this {subject}; independent safe {index}.",
    ))
    add(rows, "fresh_limited_commentary_news_and_teaching", NORMAL_CATEGORY,
        ("copyrighted movie", "copyrighted book", "copyrighted song", "copyrighted photograph"), (
        "Criticism includes a brief clip for review from the {subject} and does not substitute for the original; independent safe {index}.",
        "News reporting uses a short attributed excerpt from the {subject} and links to the official source; independent safe {index}.",
        "Teaching quotes a small attributed quotation from the {subject}, only what is needed for commentary; independent safe {index}.",
        "A product review page uses a thumbnail for identification of the {subject} and links to the official source; independent safe {index}.",
    ))
    add(rows, "fresh_weak_title_logo_style_and_notice", NORMAL_CATEGORY,
        ("same title", "contains a logo", "similar visual style", "shows a watermark"), (
        "A self-reported owner notes the work has the {subject}; no rights-impacting act is described; independent weak {index}.",
        "A report alleges infringement only because it {subject}; no unauthorized copying is established; independent weak {index}.",
        "The comparison points to a {subject} and nothing more; independent weak {index}.",
        "A copyright notice appears and the page {subject}; there is no active distribution claim; independent weak {index}.",
    ))
    add(rows, "fresh_routine_ip_admin", NORMAL_CATEGORY,
        ("copyright registration guide", "trademark application guide", "licence settings", "software licence documentation"), (
        "A public help centre explains the {subject}; independent ordinary {index}.",
        "An administrator updates the {subject}; independent ordinary {index}.",
        "A learner reads the {subject}; independent ordinary {index}.",
        "The official publisher hosts its {subject}; independent ordinary {index}.",
    ))
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(60):
        owner, action = owners[index % len(owners)]
        rows.append({
            "group": "fresh_established_owner_isolation",
            "text": f"This post distributes full copies of a copyrighted book without permission, while an existing {owner} owner controls the case; independent owner {index + 1}.",
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
    frozen = all(live.is_file() and (CDIR / relative).is_file() and
                 artifacts.get(relative) == sha(live) == sha(CDIR / relative)
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
            analysis = analyze_intellectual_property_v1_rc1(str(row["text"]), ["text"])
            decision = apply_intellectual_property_v1_rc1_fusion(
                category=str(row["existing_category"]), severity="None",
                action=str(row["existing_action"]), confidence=0.71,
                human_review_required=bool(row["existing_review"]),
                reason="Independent baseline.", matched_signals=[], analysis=analysis)
            predicted = str(decision["category"])
            correct = predicted == expected
            groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["existing_action"]), bool(row["existing_review"])
            if expected == IP_CATEGORY:
                expected_action, expected_review = IP_ACTION, True
            elif expected == UNCERTAIN_CATEGORY:
                expected_action, expected_review = UNCERTAIN_ACTION, True
            action_fail += int(decision["action"] != expected_action or
                               bool(decision["human_review_required"]) != expected_review or
                               decision["automatic_enforcement_allowed"] is not False)
            category_fail += int(not correct)
            data_fail += int(analysis["raw_copyrighted_works_stored"] is not False or
                             analysis["pirated_material_stored"] is not False or
                             analysis["complainant_private_identifiers_stored"] is not False)
            authority_fail += int(any(analysis[key] is not False for key in (
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
        "frozen_source_hashes_verified": frozen,
        "zero_development_overlap": not overlap,
        "accuracy": accuracy >= gate["minimum_accuracy"],
        "ip_precision": precision >= gate["minimum_ip_precision"],
        "ip_recall": recall >= gate["minimum_ip_recall"],
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
        "challenge_version": "2026.09-intellectual-property-v1-rc1-independent",
        "challenge_sha256": hashlib.sha256("".join(hashes).encode()).hexdigest(),
        "records": total, "unique_texts": len(set(hashes)),
        "positive_records": sum(row["expected_category"] == IP_CATEGORY for row in challenge),
        "negative_or_boundary_records": sum(row["expected_category"] != IP_CATEGORY for row in challenge),
        "development_overlap": len(overlap), "accuracy": accuracy,
        "ip_precision": precision, "ip_recall": recall, "safe_specificity": specificity,
        "f1": f1, "minimum_group_accuracy": minimum,
        "false_positives": fp, "false_negatives": fn,
        "action_contract_failures": action_fail, "category_mix_failures": category_fail,
        "data_contract_failures": data_fail, "authority_contract_failures": authority_fail,
        "processing_errors": errors, "group_results": group_results, "gates": gates,
        "passed_synthetic_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_takedown_allowed": False, "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_challenge_text_stored": False, "individual_predictions_stored": False,
        "raw_copyrighted_works_used": False, "pirated_material_used": False,
        "private_claimant_data_used": False, "external_provider_used": False,
        "candidate_may_be_modified_using_this_holdout": False,
        "synthetic_evidence_only": True, "external_real_world_accuracy": False,
    }
    verdict = {key: value for key, value in report.items()
               if key not in {"group_results", "positive_records", "negative_or_boundary_records",
                              "false_positives", "false_negatives"}}
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    VERDICT.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    print("INTELLECTUAL PROPERTY V1 RC1 INDEPENDENT CHALLENGE\n" + "=" * 60)
    print(f"Candidate: {CANDIDATE}\nRecords: {total}\nPositive records: {report['positive_records']}\nNegative/boundary records: {report['negative_or_boundary_records']}\nDevelopment overlap: {len(overlap)}")
    for label, value in (("Accuracy", accuracy), ("IP precision", precision),
                         ("IP recall", recall), ("Safe specificity", specificity),
                         ("F1", f1), ("Minimum group accuracy", minimum)):
        print(f"{label}: {value:.2%}")
    print(f"Action failures: {action_fail}\nCategory failures: {category_fail}\nData-contract failures: {data_fail}\nAuthority failures: {authority_fail}\nProcessing errors: {errors}")
    print("\nGROUP RESULTS\n" + "-" * 60)
    for group, values in group_results.items():
        print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
    print(f"\nPassed synthetic independent readiness gate: {passed}\nEligible for guarded live integration: {passed}")
    print(f"Automatic enforcement allowed: False\nConnected to live moderation: False\nReport: {REPORT}\nVerdict: {VERDICT}")
    print("No raw challenge text, copied work, or individual prediction was stored or printed.")
    print("This holdout may not be used to modify RC1.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
