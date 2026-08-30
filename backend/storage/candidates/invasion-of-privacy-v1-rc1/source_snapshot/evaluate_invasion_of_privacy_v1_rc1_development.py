"""Build/evaluate 600 safe synthetic privacy-policy fixtures."""

from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.invasion_of_privacy_v1_rc1_service import (
    NORMAL_CATEGORY, PRIVACY_ACTION, PRIVACY_CATEGORY, UNCERTAIN_ACTION,
    UNCERTAIN_CATEGORY, analyze_invasion_of_privacy_v1_rc1,
    apply_invasion_of_privacy_v1_rc1_fusion,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "datasets" / "development" / "invasion_of_privacy_v1_rc1"
DATASET_PATH = DATASET_DIR / "development.csv"
REPORT_DIR = ROOT / "reports" / "evaluation" / "invasion_of_privacy" / "v1_rc1_development"
REPORT_PATH = REPORT_DIR / "report.json"
MISMATCH_PATH = REPORT_DIR / "mismatches.json"
OWNER_ACTIONS = {
    "Child Exploitation": "Block and immediately escalate",
    "Sexual Harassment": "Remove and escalate",
    "Publishing Private Information": "Refer to human review",
    "Cyberbullying & Harassment": "Refer to human review",
    "Terrorism & Extremism": "Block and escalate",
    "Spam, Scam & Phishing": "Block, warn, or limit distribution",
}


def text_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.casefold().split()).encode()).hexdigest()


def add_group(rows: list[dict[str, Any]], group: str, expected: str,
              subjects: tuple[str, ...], templates: tuple[str, ...], *,
              owner: str = NORMAL_CATEGORY, action: str = "Allow", review: bool = False) -> None:
    for index in range(50):
        rows.append({
            "record_id": f"{group.upper()}-{index+1:03d}", "group": group,
            "text": templates[index % len(templates)].format(subject=subjects[index % len(subjects)], index=index+1),
            "expected_category": expected, "existing_category": owner,
            "existing_action": action, "existing_review": review,
        })


def build_records() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    people = ("a resident", "a tenant", "an employee", "a guest")
    add_group(rows, "hidden_camera_private_space", PRIVACY_CATEGORY, people, (
        "This user placed a hidden camera in a bedroom and recorded {subject} without consent; case {index}.",
        "Evidence indicates a concealed camera inside a private home filmed {subject} without permission; case {index}.",
        "A credible allegation says {subject} was secretly recorded in a changing room without consent; case {index}.",
        "This recording used a covert camera in a hotel room against the wishes of {subject}; case {index}.",
    ))
    add_group(rows, "private_audio_and_eavesdropping", PRIVACY_CATEGORY, people, (
        "This user used a covert microphone to record a private conversation without consent from {subject}; case {index}.",
        "Evidence indicates a secret audio recording inside a private office without permission from {subject}; case {index}.",
        "A credible report says the account eavesdrops behind a closed door without consent from {subject}; case {index}.",
        "This recording wiretaps a private conversation and {subject} did not agree; case {index}.",
    ))
    add_group(rows, "stalking_and_location_tracking", PRIVACY_CATEGORY, people, (
        "This user tracks live location of {subject} without consent; case {index}.",
        "Evidence indicates a concealed gps tracker follows every movement of {subject} without permission; case {index}.",
        "A credible report describes persistent physical stalking of {subject} against their wishes; case {index}.",
        "This account monitors daily movements of {subject} without authorization; case {index}.",
    ))
    add_group(rows, "nonconsensual_private_media_sharing", PRIVACY_CATEGORY, people, (
        "This account shares a private photo of {subject} without consent; case {index}.",
        "Evidence indicates an intimate video of {subject} is distributed without permission; case {index}.",
        "This user uploads a private recording of {subject} despite refusing consent; case {index}.",
        "A credible allegation says the post leaks a private recording of {subject} against their wishes; case {index}.",
    ))
    add_group(rows, "uncertain_consent_or_location", UNCERTAIN_CATEGORY, people, (
        "A hidden camera may involve {subject}, but consent is unclear; case {index}.",
        "The record tracks live location of {subject}, but permission is unknown; case {index}.",
        "A private recording references {subject}, while ownership is unresolved; case {index}.",
        "A concealed camera shows {subject}, but location may be private; case {index}.",
    ))
    add_group(rows, "incomplete_media_evidence", UNCERTAIN_CATEGORY, people, (
        "Media could not be decoded; metadata mentions a hidden camera and {subject}; case {index}.",
        "Unsupported media format with a concealed gps tracker involving {subject}; case {index}.",
        "Only a thumbnail is available and suggests a private recording of {subject}; case {index}.",
        "Visual evidence is incomplete while the record says it tracks live location of {subject}; case {index}.",
    ))
    add_group(rows, "documented_consent_and_user_owned", NORMAL_CATEGORY, people, (
        "All participants consented to the recording and distribution involving {subject}; safe case {index}.",
        "Explicit written consent covers this user-owned recording of {subject}; safe case {index}.",
        "Permission was documented for an authorized production with {subject}; safe case {index}.",
        "The owner authorized recording and {subject} agreed to recording and distribution; safe case {index}.",
    ))
    add_group(rows, "public_and_disclosed_monitoring", NORMAL_CATEGORY, people, (
        "A disclosed security camera with a clearly posted surveillance notice records {subject}; safe case {index}.",
        "An ordinary public event includes {subject} in a public street scene; safe case {index}.",
        "A broadcast interview with consent features {subject}; safe case {index}.",
        "A doorbell camera on the owner's property records {subject} near the entrance; safe case {index}.",
    ))
    add_group(rows, "safe_reporting_education_and_fiction", NORMAL_CATEGORY, people, (
        "Privacy awareness warns about hidden camera abuse and contains no victim media; safe case {index}.",
        "Consent education discusses tracking risks and no active case is described; safe case {index}.",
        "Academic research quotes private-media terminology only for analysis and does not identify a real person; safe case {index}.",
        "A fictional story mentions a covert camera; it is fictional and not real; safe case {index}.",
    ))
    add_group(rows, "ordinary_tracking_and_technology", NORMAL_CATEGORY,
              ("package tracking", "fitness tracking", "camera settings", "browser privacy settings"), (
        "The help page explains {subject}; ordinary case {index}.",
        "A user changes {subject} on a personal device; ordinary case {index}.",
        "This is routine documentation about {subject}; ordinary case {index}.",
        "The application provides a benign {subject} feature; ordinary case {index}.",
    ))
    owners = tuple(OWNER_ACTIONS.items())
    for index in range(50):
        owner, action = owners[index % len(owners)]
        rows.append({"record_id": f"ESTABLISHED_OWNER-{index+1:03d}", "group": "established_category_owner_isolation",
            "text": f"An existing {owner} owner applies; no non-consensual surveillance evidence is present. Owner case {index+1}.",
            "expected_category": owner, "existing_category": owner, "existing_action": action, "existing_review": True})
    add_group(rows, "lexical_and_figurative_boundaries", NORMAL_CATEGORY,
              ("private variable", "camera-ready document", "tracking number", "stalking horse argument"), (
        "A technical note uses the phrase {subject}; lexical case {index}.",
        "An ordinary message contains {subject}; lexical case {index}.",
        "The documentation explains {subject} without any person being monitored; lexical case {index}.",
        "A benign article mentions {subject}; lexical case {index}.",
    ))
    return rows


def ratio(a: int, b: int) -> float:
    return a / b if b else 0.0


def evaluate(records: list[dict[str, Any]]) -> dict[str, Any]:
    hashes = [text_hash(str(row["text"])) for row in records]
    if len(set(hashes)) != len(hashes): raise RuntimeError("Duplicate development text detected.")
    tp = tn = fp = fn = 0
    action_failures = category_failures = privacy_failures = authority_failures = processing_errors = 0
    groups: dict[str, dict[str, int]] = defaultdict(lambda: {"records": 0, "correct": 0})
    mismatches: list[dict[str, Any]] = []
    for row in records:
        group, expected = str(row["group"]), str(row["expected_category"]); groups[group]["records"] += 1
        try:
            analysis = analyze_invasion_of_privacy_v1_rc1(str(row["text"]), ["text"])
            decision = apply_invasion_of_privacy_v1_rc1_fusion(
                category=str(row["existing_category"]), severity="None" if row["existing_category"] == NORMAL_CATEGORY else "High",
                action=str(row["existing_action"]), confidence=0.70,
                human_review_required=bool(row["existing_review"]), reason="Development baseline.",
                matched_signals=[], analysis=analysis)
            predicted = str(decision["category"]); correct = predicted == expected; groups[group]["correct"] += int(correct)
            expected_action, expected_review = str(row["existing_action"]), bool(row["existing_review"])
            if expected == PRIVACY_CATEGORY: expected_action, expected_review = PRIVACY_ACTION, True
            elif expected == UNCERTAIN_CATEGORY: expected_action, expected_review = UNCERTAIN_ACTION, True
            action_ok = decision["action"] == expected_action and bool(decision["human_review_required"]) == expected_review and decision["automatic_enforcement_allowed"] is False
            action_failures += int(not action_ok); category_failures += int(not correct)
            privacy_failures += int(analysis["real_victim_media_stored"] is not False or analysis["private_identifiers_stored"] is not False)
            authority_failures += int(any(analysis[key] is not False for key in (
                "face_recognition_used", "identity_inference_from_appearance_allowed",
                "consent_inference_from_appearance_allowed", "private_location_inference_from_appearance_allowed",
                "external_provider_used", "external_transmission_allowed")))
            ep, pp = expected == PRIVACY_CATEGORY, predicted == PRIVACY_CATEGORY
            if ep and pp: tp += 1
            elif ep: fn += 1
            elif pp: fp += 1
            else: tn += 1
            if not correct or not action_ok: mismatches.append({"record_id": row["record_id"], "group": group, "expected": expected, "predicted": predicted, "status": analysis["fusion_status"]})
        except Exception as error:
            processing_errors += 1; mismatches.append({"record_id": row["record_id"], "error": type(error).__name__})
    accuracy, precision, recall, specificity = ratio(tp+tn, len(records)), ratio(tp, tp+fp), ratio(tp, tp+fn), ratio(tn, tn+fp)
    f1 = ratio(2*precision*recall, precision+recall)
    group_results = {g: {**v, "accuracy": ratio(v["correct"], v["records"])} for g, v in sorted(groups.items())}
    minimum = min(v["accuracy"] for v in group_results.values())
    gates = {"accuracy": accuracy >= .95, "privacy_precision": precision >= .97, "privacy_recall": recall >= .95,
        "safe_specificity": specificity >= .99, "f1": f1 >= .96, "minimum_group_accuracy": minimum >= .92,
        "action_contract": action_failures == 0, "category_mix_contract": category_failures == 0,
        "privacy_storage_contract": privacy_failures == 0, "authority_contract": authority_failures == 0,
        "processing_contract": processing_errors == 0}
    return {"version": "2026.08-invasion-of-privacy-v1-rc1-development", "records": len(records), "unique_texts": len(set(hashes)),
        "label_counts": dict(Counter(str(r["expected_category"]) for r in records)), "accuracy": accuracy,
        "privacy_precision": precision, "privacy_recall": recall, "safe_specificity": specificity, "f1": f1,
        "minimum_group_accuracy": minimum, "false_positives": fp, "false_negatives": fn,
        "action_contract_failures": action_failures, "category_mix_failures": category_failures,
        "privacy_storage_failures": privacy_failures, "authority_contract_failures": authority_failures,
        "processing_errors": processing_errors, "group_results": group_results, "gates": gates,
        "passed_development_gate": all(gates.values()), "real_victim_media_used": False,
        "private_identifiers_used": False, "external_provider_used": False,
        "automatic_enforcement_allowed": False, "connected_to_live_moderation": False, "mismatches": mismatches}


def main() -> None:
    records = build_records()
    if len(records) != 600: raise RuntimeError(f"Unexpected development size: {len(records)}")
    result = evaluate(records); DATASET_DIR.mkdir(parents=True, exist_ok=True); REPORT_DIR.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0])); writer.writeheader(); writer.writerows(records)
    report = {**result, "dataset_sha256": hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()}; report.pop("mismatches")
    REPORT_PATH.write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    MISMATCH_PATH.write_text(json.dumps(result["mismatches"], indent=2)+"\n", encoding="utf-8")
    print("INVASION OF PRIVACY V1 RC1 DEVELOPMENT\n" + "="*60)
    for label, key in (("Records","records"),("Unique texts","unique_texts")): print(f"{label}: {result[key]}")
    for label, key in (("Accuracy","accuracy"),("Privacy precision","privacy_precision"),("Privacy recall","privacy_recall"),("Safe specificity","safe_specificity"),("F1","f1"),("Minimum group accuracy","minimum_group_accuracy")): print(f"{label}: {result[key]:.2%}")
    print(f"Action failures: {result['action_contract_failures']}\nCategory failures: {result['category_mix_failures']}\nPrivacy-storage failures: {result['privacy_storage_failures']}\nAuthority failures: {result['authority_contract_failures']}\nProcessing errors: {result['processing_errors']}")
    print("\nGROUP RESULTS\n"+"-"*60)
    for group, values in result["group_results"].items(): print(f"{group}: {values['correct']}/{values['records']} ({values['accuracy']:.2%})")
    print(f"\nPassed development gate: {result['passed_development_gate']}\nDataset: {DATASET_PATH}\nReport: {REPORT_PATH}")
    print("Real victim media used: False\nExternal provider used: False\nConnected to live moderation: False")
    print("This is synthetic policy evidence, not real-world accuracy.")
    if not result["passed_development_gate"]: raise SystemExit(1)


if __name__ == "__main__": main()
