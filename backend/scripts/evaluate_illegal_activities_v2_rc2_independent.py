"""Run the frozen Illegal Activities V2 RC2 aggregate-only challenge once."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from app.services.illegal_activities_v2_rc2_service import (
    ILLEGAL_ACTION,
    ILLEGAL_CATEGORY,
    NORMAL_CATEGORY,
    UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_illegal_activities_v2_rc2,
    apply_illegal_activities_v2_rc2_fusion,
)


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"
CANDIDATE = "illegal-activities-v2-rc2"
CHALLENGE_VERSION = "2026.08-illegal-activities-v2-rc2-independent"
CANDIDATE_DIRECTORY = BACKEND / "storage" / "candidates" / CANDIDATE
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
DEVELOPMENT_DATASET_PATHS = (
    ROOT / "datasets" / "development" / "illegal_activities_v1" / "development.csv",
    ROOT / "datasets" / "development" / "illegal_activities_v2_rc2" / "development.csv",
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "illegal_activities"
    / "v2_rc2_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"

LIVE_ARTIFACTS = {
    "source_snapshot/illegal_activities_v2_rc2_service.py": (
        BACKEND / "app" / "services" / "illegal_activities_v2_rc2_service.py"
    ),
    "source_snapshot/openrouter_advisory_service.py": (
        BACKEND / "app" / "services" / "openrouter_advisory_service.py"
    ),
    "policy_snapshot/illegal_activities_v2_rc2_policy.json": (
        BACKEND / "app" / "evidence" / "illegal_activities_v2_rc2_policy.json"
    ),
    "source_snapshot/evaluate_illegal_activities_v2_rc2_development.py": (
        BACKEND / "scripts" / "evaluate_illegal_activities_v2_rc2_development.py"
    ),
    "source_snapshot/freeze_illegal_activities_v2_rc2.py": (
        BACKEND / "scripts" / "freeze_illegal_activities_v2_rc2.py"
    ),
    "development/development.csv": DEVELOPMENT_DATASET_PATHS[1],
    "development_evidence/report.json": (
        ROOT
        / "reports"
        / "evaluation"
        / "illegal_activities"
        / "v2_rc2_policy_generalization_development"
        / "report.json"
    ),
}

OWNER_ACTIONS = {
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
    "Publishing Private Information": "Remove exposed information and send for human review",
    "Terrorism & Extremism": "Block and escalate",
    "Hate Speech & Discrimination": "Remove and escalate",
    "Cyberbullying & Harassment": "Limit, flag, and send for human review",
    "Child Exploitation": "Block and immediately escalate",
    "Dangerous Content": "Remove and send for human review",
    "Graphic, Obscene & Sexual Content": "Age-restrict or limit distribution",
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
        raise RuntimeError(f"Expected JSON object: {path}")
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
    controlled = (
        "illegal drugs",
        "controlled substances",
        "controlled pills",
        "an unapproved drug",
        "illegal narcotics",
    )
    weapons = (
        "an unlicensed gun",
        "a weapon without a license",
        "a forged identity document",
        "a counterfeit banknote",
        "a fake government document",
    )
    financial = (
        "illegal gambling",
        "unlicensed betting",
        "unlawful wagering",
        "a money laundering service",
        "counterfeit currency",
    )
    services = (
        "prostitution services",
        "sexual services for money",
        "a commercial sexual service",
        "misuse national emblem",
        "misuse the national flag",
    )
    transaction_frames = (
        "An independent marketplace page has {subject} for sale and asks readers to contact me. Challenge {index}.",
        "A supplier advertises {subject}; shipment is available after payment. Challenge {index}.",
        "The seller markets {subject} with courier delivery available. Challenge {index}.",
        "This commercial listing offers {subject} at a price per item. Challenge {index}.",
        "A current offer provides access to {subject}; direct message to order. Challenge {index}.",
        "The account promotes the sale of {subject} to buyers. Challenge {index}.",
        "Customers are told to place an order for {subject}. Challenge {index}.",
        "Available to buyers is {subject}; contact the seller. Challenge {index}.",
        "Payment is required before the supplier provides access to {subject}. Challenge {index}.",
        "The marketplace listing says {subject} are selling with delivery available. Challenge {index}.",
    )
    add_group(rows, "novel_controlled_goods_transactions", ILLEGAL_CATEGORY, controlled, transaction_frames)
    add_group(rows, "novel_weapons_and_counterfeit_transactions", ILLEGAL_CATEGORY, weapons, transaction_frames)
    add_group(
        rows,
        "novel_gambling_and_financial_facilitation",
        ILLEGAL_CATEGORY,
        financial,
        (
            "A current offer promotes {subject}; readers are told to sign up to wager. Challenge {index}.",
            "The account advertises {subject} and requests payment for access. Challenge {index}.",
            "A supplier provides access to {subject}; direct message for details. Challenge {index}.",
            "This commercial listing markets {subject} to customers. Challenge {index}.",
            "The marketplace tells readers to join the betting for {subject}. Challenge {index}.",
            "Payment is required before the seller arranges access to {subject}. Challenge {index}.",
            "A current seller offers {subject}; contact me. Challenge {index}.",
            "The account promotes the sale of {subject} to buyers. Challenge {index}.",
            "A price per item is displayed beside {subject} in the listing. Challenge {index}.",
            "The supplier advertises {subject}; delivery is available. Challenge {index}.",
        ),
    )
    add_group(
        rows,
        "novel_prohibited_services_and_symbols",
        ILLEGAL_CATEGORY,
        services,
        (
            "This post advertises {subject}; customers are asked to reserve a slot. Challenge {index}.",
            "A current offer makes {subject} available tonight after payment. Challenge {index}.",
            "The seller markets {subject}; buyers should contact me. Challenge {index}.",
            "A commercial listing offers {subject} and says book now. Challenge {index}.",
            "The account promotes the sale of {subject}. Challenge {index}.",
            "A supplier provides access to {subject} after payment. Challenge {index}.",
            "The marketplace listing advertises {subject} to customers. Challenge {index}.",
            "Direct message is requested for the seller offering {subject}. Challenge {index}.",
            "The current offer lists {subject} with delivery available. Challenge {index}.",
            "A price per item appears beside {subject} in this commercial listing. Challenge {index}.",
        ),
    )
    mixed = controlled + weapons + financial + services
    add_group(
        rows,
        "novel_reordered_and_passive_transaction_evidence",
        ILLEGAL_CATEGORY,
        mixed,
        (
            "Courier delivery can be arranged by the supplier for {subject}. Challenge {index}.",
            "For customers seeking it, the current seller offers {subject}. Challenge {index}.",
            "The sale being promoted in this marketplace concerns {subject}. Challenge {index}.",
            "Shipment is available from the supplier for {subject}. Challenge {index}.",
            "Before access to {subject}, payment is required by the account. Challenge {index}.",
            "Beside {subject}, a price per item is shown in the commercial listing. Challenge {index}.",
            "Buyers are invited to direct message the supplier about {subject}. Challenge {index}.",
            "The seller makes {subject} available to buyers. Challenge {index}.",
            "A place-an-order message accompanies {subject} in this listing. Challenge {index}.",
            "The current offer markets {subject} and requests contact. Challenge {index}.",
        ),
    )
    add_group(
        rows,
        "fresh_reporting_warning_and_prevention",
        NORMAL_CATEGORY,
        mixed,
        (
            "A journalistic report covers {subject}; it tells readers not to buy and is not a live offer. Challenge {index}.",
            "A safety warning discusses {subject} for prevention and contains no transaction. Challenge {index}.",
            "A law-enforcement notice records {subject} as reported to authorities without facilitating it. Challenge {index}.",
            "Public awareness material condemns {subject}; no live transaction exists. Challenge {index}.",
            "A news report quotes an offer for {subject}, quoted for analysis and not a live offer. Challenge {index}.",
            "An educational lesson describes {subject} for prevention only. Challenge {index}.",
            "A documentary critiques {subject} and contains no transaction. Challenge {index}.",
            "A case study discusses {subject} without facilitating it. Challenge {index}.",
            "A prevention campaign warns viewers not to buy {subject}. Challenge {index}.",
            "News coverage condemns {subject} and reports it to authorities. Challenge {index}.",
        ),
    )
    add_group(
        rows,
        "fresh_fiction_history_and_research",
        NORMAL_CATEGORY,
        mixed,
        (
            "A fictional story refers to {subject}; it is fictional and not real. Challenge {index}.",
            "Academic research examines {subject} for research only. Challenge {index}.",
            "A historical account preserves a quoted advertisement for {subject}, not a live offer. Challenge {index}.",
            "A novel excerpt uses quoted dialogue about {subject} and no live transaction. Challenge {index}.",
            "A screenplay mentions {subject} in a dramatic reenactment. Challenge {index}.",
            "A museum exhibit documents {subject} for prevention. Challenge {index}.",
            "An academic discussion quotes 'buy now' near {subject}, quoted for analysis. Challenge {index}.",
            "A documentary studies {subject} as a case study and does not facilitate it. Challenge {index}.",
            "A research paper analyzes {subject} without facilitating it. Challenge {index}.",
            "A fictional scene depicts {subject}; there is no live transaction. Challenge {index}.",
        ),
    )
    legitimate = (
        "Microsoft job recruitment",
        "a licensed pharmacy selling approved medicine",
        "an authorized retailer",
        "a licensed sporting event",
        "a museum exhibition",
        "a stage prop",
        "a film prop",
        "a lawful training range",
        "legal compliance training",
        "professional compliance review",
    )
    add_group(
        rows,
        "fresh_legitimate_jobs_and_professional_context",
        NORMAL_CATEGORY,
        legitimate,
        (
            "A verified organization publishes an ordinary notice about {subject}. Challenge {index}.",
            "This educational page gives neutral information about {subject}. Challenge {index}.",
            "A regulated professional announcement describes {subject}. Challenge {index}.",
            "The public calendar contains a lawful listing for {subject}. Challenge {index}.",
            "A community information page discusses {subject} without prohibited facilitation. Challenge {index}.",
        ),
    )
    uncertain = (
        "an online betting service",
        "unlicensed gambling",
        "a protected government name",
        "unapproved medicine",
        "a commercial sexual service",
    )
    add_group(
        rows,
        "fresh_jurisdiction_and_status_uncertainty",
        UNCERTAIN_CATEGORY,
        uncertain,
        (
            "A message names {subject}; license status is unclear and no transaction is established. Challenge {index}.",
            "The page refers to {subject}, but jurisdiction remains unknown. Challenge {index}.",
            "A neutral reference mentions {subject}; legal status is unresolved. Challenge {index}.",
            "The content discusses {subject}; location is unknown and purpose is unclear. Challenge {index}.",
            "A post identifies {subject}, but its status is unverified and context is incomplete. Challenge {index}.",
            "The note mentions {subject} and cannot establish a transaction. Challenge {index}.",
            "A reference to {subject} has an unknown jurisdiction. Challenge {index}.",
            "The status of {subject} is unverified; no transaction is established. Challenge {index}.",
            "A page lists the words {subject}, but license status is unclear. Challenge {index}.",
            "The legal status of {subject} is unresolved and location is unknown. Challenge {index}.",
        ),
    )
    owners = tuple(OWNER_ACTIONS)
    owner_subjects = controlled + weapons + financial + services
    for index in range(1, 51):
        owner = owners[(index - 1) % len(owners)]
        subject = owner_subjects[(index - 1) % len(owner_subjects)]
        text = (
            f"An existing {owner} owner accompanies a seller offering {subject}. "
            f"Independent owner challenge {index}."
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
        text = (
            "A minor or child is linked to a sexual private image; the Child "
            f"Exploitation owner is already active. Independent child challenge {index}."
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
    safe_subjects = (
        "a software apprenticeship",
        "a gardening workshop",
        "a community concert",
        "a charity event",
        "a language course",
        "a public lecture",
        "a sports club meeting",
        "a book fair",
        "a cooking demonstration",
        "a museum tour",
    )
    add_group(
        rows,
        "fresh_unrelated_safe_context",
        NORMAL_CATEGORY,
        safe_subjects,
        (
            "A community calendar announces {subject}. Challenge {index}.",
            "A verified public page gives details about {subject}. Challenge {index}.",
            "This ordinary notice describes {subject}. Challenge {index}.",
            "A local organization invites residents to {subject}. Challenge {index}.",
            "The informational post concerns {subject}. Challenge {index}.",
        ),
    )
    return rows


def verify_frozen_artifacts(manifest: dict[str, Any]) -> bool:
    artifacts = {
        str(item["relative_path"]): item for item in manifest.get("artifacts", [])
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
    hashes: set[str] = set()
    for path in DEVELOPMENT_DATASET_PATHS:
        with path.open("r", encoding="utf-8", newline="") as handle:
            hashes.update(text_hash(str(row["text"])) for row in csv.DictReader(handle))
    return hashes


def ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    if REPORT_PATH.exists() or VERDICT_PATH.exists():
        raise FileExistsError(
            "The RC2 independent challenge has already been evaluated and will not be overwritten."
        )
    manifest = read_json(MANIFEST_PATH)
    if manifest.get("candidate") != CANDIDATE:
        raise RuntimeError("Unexpected frozen candidate identity.")
    frozen_verified = verify_frozen_artifacts(manifest)
    if not frozen_verified:
        raise RuntimeError("Frozen source, policy, or dependency verification failed.")

    rows = build_challenge()
    if len(rows) != 600:
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

    print("Running the frozen Illegal Activities V2 RC2 independent challenge...")
    print("Individual cases and predictions are intentionally hidden.")
    print("OpenRouter is not used for the independent accuracy challenge.")
    print()
    for row in rows:
        group = str(row["group"])
        group_results[group]["records"] += 1
        try:
            analysis = analyze_illegal_activities_v2_rc2(
                str(row["text"]),
                ["text"],
                use_openrouter=False,
            )
            decision = apply_illegal_activities_v2_rc2_fusion(
                category=str(row["existing_category"]),
                severity="None" if row["existing_category"] == NORMAL_CATEGORY else "High",
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
                or analysis.get("legal_determination_authority") is not False
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
        "illegal_precision": precision >= float(gate["minimum_illegal_precision"]),
        "illegal_recall": recall >= float(gate["minimum_illegal_recall"]),
        "safe_specificity": specificity >= float(gate["minimum_safe_specificity"]),
        "f1": f1 >= float(gate["minimum_f1"]),
        "minimum_group_accuracy": minimum_group_accuracy >= float(gate["minimum_group_accuracy"]),
        "action_contract": action_failures <= int(gate["maximum_action_contract_failures"]),
        "category_mix_contract": category_mix_failures <= int(gate["maximum_category_mix_failures"]),
        "authority_contract": authority_failures <= int(gate["maximum_authority_contract_failures"]),
        "processing_contract": processing_errors <= int(gate["maximum_processing_errors"]),
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
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "openrouter_used_for_independent_accuracy": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "earlier_holdout_cases_predictions_or_mismatches_read": False,
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
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "candidate_may_be_modified_using_this_holdout": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "report_path": REPORT_PATH.relative_to(ROOT).as_posix(),
        "evidence_scope": "synthetic evidence, not external or real-world accuracy",
    }
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print("ILLEGAL ACTIVITIES V2 RC2 INDEPENDENT CHALLENGE")
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
    print("Connected to live moderation: False")
    print("Automatic enforcement allowed: False")
    print("OpenRouter used for independent accuracy: False")
    print(f"Report: {REPORT_PATH}")
    print(f"Verdict: {VERDICT_PATH}")
    print("Individual cases and predictions were intentionally hidden.")
    print("No raw challenge text was stored.")
    print("Earlier holdout cases, predictions, and mismatches were not read.")
    print("This is synthetic evidence, not external or real-world accuracy.")
    print("This holdout may not be used to modify RC2.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
