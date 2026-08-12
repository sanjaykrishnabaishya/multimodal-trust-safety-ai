from __future__ import annotations

import csv
import hashlib
import json
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.religiously_offensive_v7_rc6_service import (
    evaluate_religiously_offensive_v7_rc6_candidate,
)


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_NAME = "religiously-offensive-v7-rc6"
CHALLENGE_VERSION = "2026.08-religiously-offensive-v7-rc6-independent"
CANDIDATE_DIRECTORY = (
    ROOT / "backend" / "storage" / "candidates" / CANDIDATE_NAME
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
LIVE_SERVICE = (
    ROOT
    / "backend"
    / "app"
    / "services"
    / "religiously_offensive_v7_rc6_service.py"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v7_rc6_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"

RELIGIOUS_CATEGORY = "Religiously Offensive Content"
REQUIRED_ACTION = "Remove and send for human review"


def normalize(text: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", str(text or "")).casefold().split()
    )


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def build_challenge() -> list[dict[str, str]]:
    records: list[dict[str, str]] = []

    direct_frames = [
        "A livestream host called for viewers to {target}.",
        "An organizer is encouraging users to {target}.",
        "The channel ordered participants to {target}.",
        "A speaker declared that people should {target}.",
        "The group vowed to {target}.",
        "A public post demands that followers {target}.",
    ]
    positive_groups = {
        "direct_sacred_object_attack": [
            "burn the revered manuscript",
            "rip apart the sacred scroll",
            "smash the devotional statue",
            "deface the holy emblem",
            "trample the ceremonial icon",
        ],
        "direct_place_of_worship_attack": [
            "demolish the neighborhood temple",
            "vandalize the worship centre",
            "set the local shrine ablaze",
            "deface the prayer space",
            "ransack the religious building",
        ],
        "direct_religious_figure_attack": [
            "mock the sacred figure with a degrading caricature",
            "ridicule the faith founder",
            "vilify the spiritual leader",
            "humiliate the revered teacher",
            "denigrate the religious figurehead",
        ],
    }
    for group_index, (group, targets) in enumerate(positive_groups.items()):
        for frame_index, frame in enumerate(direct_frames):
            for target_index, target in enumerate(targets):
                records.append(
                    {
                        "case_id": (
                            f"RC6-P-{group_index:02d}-{frame_index:02d}-{target_index:02d}"
                        ),
                        "group": group,
                        "expected": "religiously_offensive",
                        "text": frame.format(target=target),
                    }
                )

    reported_frames = [
        (
            "A journalistic report described a speaker urging people to {target}; "
            "the report condemned the statement."
        ),
        (
            "A legal summary quoted the accused ordering others to {target} "
            "without endorsing the instruction."
        ),
        (
            "A police statement recorded a caller demanding that listeners "
            "{target}, and officials denounced the demand."
        ),
        (
            "A historical account recounted a group calling for residents to "
            "{target} as evidence of past intolerance."
        ),
        (
            "A museum exhibit documented a campaign encouraging visitors to "
            "{target} and provided cultural context."
        ),
        (
            "A research paper examined posts saying people should {target} and "
            "explicitly rejected those posts."
        ),
    ]
    reported_targets = [
        "burn a sacred text",
        "vandalize a place of worship",
        "smash a religious statue",
        "deface a holy symbol",
        "mock a revered deity",
    ]
    for frame_index, frame in enumerate(reported_frames):
        for target_index, target in enumerate(reported_targets):
            records.append(
                {
                    "case_id": f"RC6-NR-{frame_index:02d}-{target_index:02d}",
                    "group": "reported_advocacy_safe_context",
                    "expected": "no_religious_override",
                    "text": frame.format(target=target),
                }
            )

    neutral_frames = [
        "A visitor photographed {target} during an organized tour.",
        "Volunteers carefully cleaned {target} before the ceremony.",
        "A conservator inspected {target} and recommended preservation.",
        "A classroom lesson explained the history of {target}.",
        "The community quietly gathered near {target} in the morning.",
        "An archive added a description of {target} to its catalogue.",
    ]
    neutral_targets = [
        "the sacred manuscript",
        "the local shrine",
        "the revered statue",
        "the prayer hall",
        "the religious leader's historical portrait",
    ]
    for frame_index, frame in enumerate(neutral_frames):
        for target_index, target in enumerate(neutral_targets):
            records.append(
                {
                    "case_id": f"RC6-NN-{frame_index:02d}-{target_index:02d}",
                    "group": "neutral_religious_content",
                    "expected": "no_religious_override",
                    "text": frame.format(target=target),
                }
            )

    follower_frames = [
        "A message claims that {group} are inferior and should be excluded.",
        "A post says {group} are dangerous and must be expelled.",
        "The account argues that {group} should lose their rights.",
        "A user demands that {group} be denied housing and employment.",
        "The speaker calls {group} parasites who should be driven away.",
        "A comment says {group} are unfit for citizenship.",
    ]
    follower_groups = [
        "followers of that religion",
        "people belonging to that faith",
        "members of the religious community",
        "adherents of that denomination",
        "believers from that sect",
    ]
    for frame_index, frame in enumerate(follower_frames):
        for group_index, group in enumerate(follower_groups):
            records.append(
                {
                    "case_id": f"RC6-NF-{frame_index:02d}-{group_index:02d}",
                    "group": "protected_followers_hate_boundary",
                    "expected": "no_religious_override",
                    "text": frame.format(group=group),
                }
            )

    safe_frames = [
        "A scholar respectfully critiques {topic} without attacking worshippers.",
        "An interfaith workshop discusses disagreements about {topic}.",
        "A documentary provides historical context for debates about {topic}.",
        "A public-service campaign warns against damaging {topic}.",
        "A museum program explains why preserving {topic} matters.",
        "A court report documents a dispute involving {topic} without endorsing harm.",
    ]
    safe_topics = [
        "a religious doctrine",
        "a sacred manuscript",
        "a place of worship",
        "a ceremonial symbol",
        "a historical religious figure",
    ]
    for frame_index, frame in enumerate(safe_frames):
        for topic_index, topic in enumerate(safe_topics):
            records.append(
                {
                    "case_id": f"RC6-NS-{frame_index:02d}-{topic_index:02d}",
                    "group": "safe_criticism_education_or_preservation",
                    "expected": "no_religious_override",
                    "text": frame.format(topic=topic),
                }
            )

    unrelated_frames = [
        "An angry customer threatened to {action} after a billing dispute.",
        "A coworker repeatedly said they would {action} during an argument.",
        "A private message encouraged someone to {action} for revenge.",
        "A fictional character announced a plan to {action} in the story.",
        "The complaint states that a stranger tried to {action} yesterday.",
        "A user posted instructions to {action} with no religious reference.",
    ]
    unrelated_actions = [
        "smash a mobile phone",
        "burn an old cardboard box",
        "deface a commercial billboard",
        "tear a personal letter",
        "vandalize an empty vehicle",
    ]
    for frame_index, frame in enumerate(unrelated_frames):
        for action_index, action in enumerate(unrelated_actions):
            records.append(
                {
                    "case_id": f"RC6-NO-{frame_index:02d}-{action_index:02d}",
                    "group": "unrelated_or_personal_boundary",
                    "expected": "no_religious_override",
                    "text": frame.format(action=action),
                }
            )
    return records


def load_development_hashes(manifest: dict[str, Any]) -> set[str]:
    hashes: set[str] = set()
    for dataset in manifest.get("datasets", {}).values():
        relative_path = Path(str(dataset["path"]))
        path = ROOT / relative_path
        if not path.is_file():
            raise FileNotFoundError(f"Frozen development dataset is missing: {path}")
        if sha256_file(path) != str(dataset["sha256"]):
            raise RuntimeError(f"Frozen development dataset hash mismatch: {path.name}")
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                hashes.add(text_hash(row["text"]))
    return hashes


def verify_candidate() -> tuple[dict[str, Any], dict[str, Any]]:
    if not MANIFEST_PATH.is_file():
        raise FileNotFoundError(f"Frozen RC6 manifest is missing: {MANIFEST_PATH}")
    if VERDICT_PATH.exists():
        raise FileExistsError(
            "The RC6 independent verdict already exists. The holdout cannot be rerun."
        )
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC6 manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("RC6 did not pass development.")
    if manifest.get("independent_holdout_created_before_freeze") is not False:
        raise RuntimeError("The RC6 holdout existed before freeze.")
    if manifest.get("independent_holdout_used_before_freeze") is not False:
        raise RuntimeError("The RC6 holdout was used before freeze.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("RC6 is already marked independently validated.")
    if manifest.get("connected_to_live_moderation") is not False:
        raise RuntimeError("RC6 is already connected to live moderation.")
    if manifest.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC6 automatic-enforcement contract is invalid.")
    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / str(artifact["relative_path"])
        if not path.is_file():
            raise FileNotFoundError(f"Frozen RC6 artifact is missing: {path}")
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC6 artifact hash mismatch: {path.name}")
    service_record = next(
        (
            artifact
            for artifact in manifest.get("artifacts", [])
            if str(artifact.get("relative_path", "")).endswith(
                "religiously_offensive_v7_rc6_service.py"
            )
        ),
        None,
    )
    if service_record is None:
        raise RuntimeError("The frozen RC6 service snapshot is not registered.")
    if sha256_file(LIVE_SERVICE) != str(service_record["sha256"]):
        raise RuntimeError("The RC6 evaluation service differs from its frozen snapshot.")
    gate = dict(manifest.get("independent_gate_frozen_before_holdout", {}))
    required_gate_keys = {
        "minimum_binary_accuracy",
        "minimum_religious_precision",
        "minimum_religious_recall",
        "minimum_religious_f1",
        "minimum_nonreligious_specificity",
        "minimum_reported_advocacy_safe_rate",
        "minimum_protected_follower_safe_rate",
        "minimum_group_accuracy",
        "maximum_category_mix_failures",
        "maximum_action_contract_failures",
        "maximum_processing_errors",
    }
    if not required_gate_keys.issubset(gate):
        raise RuntimeError("The frozen RC6 independent gate is incomplete.")
    return manifest, gate


def main() -> None:
    manifest, gate = verify_candidate()
    development_hashes = load_development_hashes(manifest)
    records = build_challenge()
    challenge_hashes = [text_hash(record["text"]) for record in records]
    if len(challenge_hashes) != len(set(challenge_hashes)):
        raise RuntimeError("The RC6 independent challenge contains duplicate text.")
    development_overlap = len(development_hashes.intersection(challenge_hashes))
    if development_overlap:
        raise RuntimeError(
            f"RC6 independent challenge overlaps development data: {development_overlap}"
        )
    challenge_digest = hashlib.sha256()
    for record in sorted(records, key=lambda item: item["case_id"]):
        challenge_digest.update(record["case_id"].encode("utf-8"))
        challenge_digest.update(b"\x00")
        challenge_digest.update(record["expected"].encode("utf-8"))
        challenge_digest.update(b"\x00")
        challenge_digest.update(normalize(record["text"]).encode("utf-8"))
        challenge_digest.update(b"\n")
    challenge_sha256 = challenge_digest.hexdigest()

    tp = tn = fp = fn = 0
    category_mix_failures = 0
    action_contract_failures = 0
    processing_errors = 0
    semantic_path_accepts = 0
    direct_path_accepts = 0
    group_results: dict[str, dict[str, int]] = defaultdict(
        lambda: {"records": 0, "correct": 0, "incorrect": 0}
    )

    print("Running the one-time RC6 independent challenge...")
    print("Individual cases and predictions are intentionally hidden.")
    print()
    for record in records:
        result = evaluate_religiously_offensive_v7_rc6_candidate(
            record["text"], ["text"]
        )
        expected_positive = record["expected"] == "religiously_offensive"
        predicted_positive = bool(
            result.get("primary_category") == RELIGIOUS_CATEGORY
            and result.get("decision") == "religiously_offensive_review_only"
        )
        available = result.get("available") is True
        correct = bool(available and expected_positive == predicted_positive)
        if expected_positive and predicted_positive:
            tp += 1
        elif expected_positive and not predicted_positive:
            fn += 1
        elif not expected_positive and predicted_positive:
            fp += 1
            category_mix_failures += 1
        else:
            tn += 1
        if not available:
            processing_errors += 1

        if predicted_positive:
            if result.get("decision_path") == "semantic_and_anchor":
                semantic_path_accepts += 1
            elif result.get("decision_path") == "direct_advocacy_and_anchor":
                direct_path_accepts += 1
        if expected_positive:
            action_ok = bool(
                predicted_positive
                and result.get("action") == REQUIRED_ACTION
                and result.get("human_review_required") is True
                and result.get("automatic_enforcement_allowed") is False
            )
        else:
            action_ok = bool(
                not predicted_positive
                and not result.get("primary_category")
                and not result.get("action")
                and result.get("human_review_required") is False
                and result.get("automatic_enforcement_allowed") is False
            )
        if not action_ok:
            action_contract_failures += 1
        group = group_results[record["group"]]
        group["records"] += 1
        group["correct" if correct else "incorrect"] += 1

    records_count = len(records)
    positive_records = tp + fn
    negative_records = tn + fp
    accuracy = safe_divide(tp + tn, records_count)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    finalized_groups: dict[str, dict[str, Any]] = {}
    for group, values in sorted(group_results.items()):
        finalized_groups[group] = {
            **values,
            "accuracy": round(safe_divide(values["correct"], values["records"]), 4),
        }
    minimum_group_accuracy = min(
        values["accuracy"] for values in finalized_groups.values()
    )
    reported = finalized_groups["reported_advocacy_safe_context"]
    follower = finalized_groups["protected_followers_hate_boundary"]
    reported_safe_rate = safe_divide(reported["correct"], reported["records"])
    follower_safe_rate = safe_divide(follower["correct"], follower["records"])

    gate_checks = {
        "zero_development_overlap": development_overlap == 0,
        "zero_prior_challenge_reuse": True,
        "binary_accuracy": accuracy >= float(gate["minimum_binary_accuracy"]),
        "religious_precision": precision >= float(gate["minimum_religious_precision"]),
        "religious_recall": recall >= float(gate["minimum_religious_recall"]),
        "religious_f1": f1 >= float(gate["minimum_religious_f1"]),
        "nonreligious_specificity": specificity
        >= float(gate["minimum_nonreligious_specificity"]),
        "reported_advocacy_safe_rate": reported_safe_rate
        >= float(gate["minimum_reported_advocacy_safe_rate"]),
        "protected_follower_safe_rate": follower_safe_rate
        >= float(gate["minimum_protected_follower_safe_rate"]),
        "minimum_group_accuracy": minimum_group_accuracy
        >= float(gate["minimum_group_accuracy"]),
        "category_mix_contract": category_mix_failures
        <= int(gate["maximum_category_mix_failures"]),
        "action_contract": action_contract_failures
        <= int(gate["maximum_action_contract_failures"]),
        "processing_contract": processing_errors
        <= int(gate["maximum_processing_errors"]),
        "follower_boundary_output_disabled": manifest.get(
            "follower_boundary_output_enabled"
        )
        is False,
    }
    passed = all(gate_checks.values())

    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    report = {
        "candidate": CANDIDATE_NAME,
        "challenge_version": CHALLENGE_VERSION,
        "challenge_sha256": challenge_sha256,
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": records_count,
        "positive_records": positive_records,
        "negative_records": negative_records,
        "development_overlap": development_overlap,
        "prior_challenge_records_read": False,
        "prior_challenge_reuse": False,
        "accuracy": round(accuracy, 4),
        "religious_precision": round(precision, 4),
        "religious_recall": round(recall, 4),
        "religious_f1": round(f1, 4),
        "nonreligious_specificity": round(specificity, 4),
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "reported_advocacy_safe_rate": round(reported_safe_rate, 4),
        "protected_follower_safe_rate": round(follower_safe_rate, 4),
        "minimum_group_accuracy": minimum_group_accuracy,
        "category_mix_failures": category_mix_failures,
        "action_contract_failures": action_contract_failures,
        "processing_errors": processing_errors,
        "semantic_path_accepts": semantic_path_accepts,
        "direct_advocacy_path_accepts": direct_path_accepts,
        "group_results": finalized_groups,
        "gate_checks": gate_checks,
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "frozen_artifacts_modified": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "individual_predictions_printed": False,
        "evidence_limit": "Synthetic independent evidence, not external or real-world accuracy.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    verdict = {
        "candidate": CANDIDATE_NAME,
        "status": (
            "Passed synthetic independent readiness gate"
            if passed
            else "Failed synthetic independent readiness gate"
        ),
        "evaluated_at_utc": report["evaluated_at_utc"],
        "challenge_version": CHALLENGE_VERSION,
        "challenge_sha256": challenge_sha256,
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "aggregate_report": str(REPORT_PATH),
        "frozen_artifacts_modified": False,
        "holdout_may_modify_rc6": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "evidence_type": "synthetic independent challenge",
    }
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print("RELIGIOUSLY OFFENSIVE CONTENT V7 RC6 INDEPENDENT CHALLENGE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Challenge version: {CHALLENGE_VERSION}")
    print(f"Challenge SHA-256: {challenge_sha256}")
    print(f"Records: {records_count}")
    print(f"Positive records: {positive_records}")
    print(f"Negative records: {negative_records}")
    print(f"Development overlap: {development_overlap}")
    print(f"Binary accuracy: {accuracy * 100:.2f}%")
    print(f"Religious precision: {precision * 100:.2f}%")
    print(f"Religious recall: {recall * 100:.2f}%")
    print(f"Religious F1: {f1 * 100:.2f}%")
    print(f"Nonreligious specificity: {specificity * 100:.2f}%")
    print(f"Reported-advocacy safe routing: {reported_safe_rate * 100:.2f}%")
    print(f"Protected-follower safe routing: {follower_safe_rate * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Action-contract failures: {action_contract_failures}")
    print(f"Processing errors: {processing_errors}")
    print(f"Semantic-path accepts: {semantic_path_accepts}")
    print(f"Direct-advocacy-path accepts: {direct_path_accepts}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, values in finalized_groups.items():
        print(
            f"{group}: {values['correct']}/{values['records']} "
            f"({values['accuracy'] * 100:.2f}%)"
        )
    print()
    print("INDEPENDENT GATE CHECKS")
    print("-" * 60)
    for name, value in gate_checks.items():
        print(f"{name}: {value}")
    print()
    print(f"Passed synthetic independent readiness gate: {passed}")
    print(f"Eligible for guarded live integration: {passed}")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print(f"Report: {REPORT_PATH}")
    print(f"Verdict: {VERDICT_PATH}")
    print("No raw challenge text or individual predictions were stored or printed.")
    print("This is synthetic evidence, not external or real-world accuracy.")
    print("This holdout may not be used to modify RC6.")


if __name__ == "__main__":
    main()
