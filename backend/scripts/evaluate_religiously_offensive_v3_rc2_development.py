from __future__ import annotations

import csv
import hashlib
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.religiously_offensive_v3_rc2_service import (
    ACTION,
    HATE_CATEGORY,
    RELIGIOUS_CATEGORY,
    analyze_religiously_offensive_v3_rc2,
)


ROOT = Path(__file__).resolve().parents[2]
PRIOR_DEVELOPMENT_DATASET = (
    ROOT / "datasets" / "development" / "religiously_offensive_v1" / "development.csv"
)
DEVELOPMENT_DIRECTORY = (
    ROOT / "datasets" / "development" / "religiously_offensive_v3_rc2"
)
DEVELOPMENT_DATASET = DEVELOPMENT_DIRECTORY / "development.csv"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v3_rc2_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.csv"


def normalized_hash(text: str) -> str:
    normalized = " ".join(str(text).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected_decision: str,
    religious_violation: bool,
    texts: list[str],
) -> None:
    for text in texts:
        rows.append(
            {
                "case_id": f"REL-V3DEV-{len(rows) + 1:03d}",
                "group": group,
                "text": text,
                "expected_decision": expected_decision,
                "religious_violation": religious_violation,
            }
        )


def build_development_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    objects = [
        "holy book",
        "sacred text",
        "religious scripture",
        "sacred emblem",
        "religious symbol",
        "sacred image",
        "religious statue",
        "prayer beads",
        "ceremonial symbol",
        "sacred banner",
        "religious flag",
        "religious monument",
        "holy scripture",
        "sacred object",
        "religious book",
        "sacred statue",
        "religious emblem",
        "sacred symbol",
        "holy text",
        "sacred monument",
    ]
    object_actions = [
        "scorch",
        "shred",
        "deface",
        "smash",
        "break",
        "trample",
        "rip",
        "crush",
        "vandalize",
        "drag through mud",
        "burn",
        "wreck",
        "tear",
        "damage",
        "destroy",
        "mutilate",
        "desecrate",
        "cover with obscene graffiti",
        "torch",
        "dismantle",
    ]
    add_group(
        rows,
        "sacred_object_or_text_attack",
        "religiously_offensive_review_only",
        True,
        [
            f"The post tells viewers to {action} the {target} as a deliberate insult."
            for action, target in zip(object_actions, objects, strict=True)
        ],
    )

    figures = [
        "deity",
        "prophet",
        "religious figure",
        "spiritual leader",
        "revered religious teacher",
        "sacred figure",
        "religious leader",
        "god",
        "religious figurehead",
        "sacred leader",
        "prophet",
        "deity",
        "religious leader",
        "spiritual leader",
        "sacred figure",
        "revered teacher",
        "god",
        "religious figure",
        "religious figurehead",
        "prophet",
    ]
    figure_actions = [
        "mock",
        "ridicule",
        "vilify",
        "demean",
        "humiliate",
        "insult",
        "degrade",
        "revile",
        "deride",
        "abuse",
        "publish an obscene caricature of",
        "share a degrading depiction of",
        "create an abusive caricature of",
        "circulate an obscene depiction of",
        "post a morphed image to humiliate",
        "publicly mock",
        "repeatedly insult",
        "deliberately ridicule",
        "publish a degrading caricature of",
        "revile",
    ]
    add_group(
        rows,
        "deity_prophet_or_figure_attack",
        "religiously_offensive_review_only",
        True,
        [
            f"The account urges people to {action} the {target}."
            for action, target in zip(figure_actions, figures, strict=True)
        ],
    )

    places = [
        "temple",
        "church",
        "mosque",
        "gurudwara",
        "shrine",
        "chapel",
        "monastery",
        "sanctuary",
        "altar",
        "prayer hall",
        "prayer space",
        "place of worship",
        "worship building",
        "religious building",
        "sacred site",
        "gurdwara",
        "temple",
        "mosque",
        "church",
        "shrine",
    ]
    place_actions = [
        "wreck",
        "deface",
        "smash",
        "demolish",
        "vandalize",
        "damage",
        "destroy",
        "desecrate",
        "break",
        "torch",
        "burn",
        "tear down",
        "dismantle",
        "raze",
        "cover with obscene graffiti",
        "mutilate",
        "crush",
        "scorch",
        "vandalise",
        "tear apart",
    ]
    add_group(
        rows,
        "place_of_worship_attack",
        "religiously_offensive_review_only",
        True,
        [
            f"A public message calls on supporters to {action} the {target}."
            for action, target in zip(place_actions, places, strict=True)
        ],
    )

    followers = [
        "religious followers",
        "followers of the faith",
        "followers of that faith",
        "people of that religion",
        "people because of their religion",
        "religious believers",
        "worshippers",
        "faith community",
        "religious community",
        "religious group",
        "members of the religion",
        "families of that faith",
        "workers of that faith",
        "students of that faith",
        "followers of this faith",
        "people of this religion",
        "members of that religion",
        "members of this religion",
        "religious followers",
        "worshippers",
    ]
    follower_attacks = [
        "are inferior",
        "are parasites",
        "are not human",
        "are less than human",
        "are criminals by nature",
        "are inherently dangerous",
        "should not exist",
        "should be excluded",
        "should be expelled",
        "must be forced to leave",
        "must be boycotted",
        "should be denied jobs",
        "should be denied housing",
        "should be denied education",
        "must be kept out",
        "should be banned from the town",
        "must be refused employment",
        "should be removed from the neighborhood",
        "must be attacked",
        "should be harmed",
    ]
    add_group(
        rows,
        "protected_followers_hate_boundary",
        "protected_followers_hate_boundary",
        False,
        [
            f"The post says {target} {attack}."
            for target, attack in zip(followers, follower_attacks, strict=True)
        ],
    )

    safe_contexts = [
        "A news report describes vandals who burned a holy book.",
        "The article reports that a sacred statue was damaged and later restored.",
        "A documentary examines why attackers defaced a religious building.",
        "A historian discusses the destruction of a temple in historical context.",
        "A religious studies lesson explains why desecrating scripture causes harm.",
        "Researchers study reports of vandalism against places of worship.",
        "A museum exhibit documents a damaged sacred monument.",
        "The teacher explains why people must not burn religious books.",
        "An educational discussion condemns insults against a prophet.",
        "An interfaith campaign asks people not to damage sacred objects.",
        "Community leaders condemned the vandalism of a mosque.",
        "The safety campaign warns against defacing religious symbols.",
        "The author respectfully questions a religious doctrine.",
        "The scholar offers good faith criticism of a belief.",
        "A student disagrees with the doctrine without insulting believers.",
        "The museum restored a religious statue that had been broken.",
        "Volunteers repaired the prayer hall after reported vandalism.",
        "The article reported an obscene caricature and condemned it.",
        "A prevention campaign tells viewers never to desecrate a holy text.",
        "The documentary provides cultural context for the sacred emblem.",
    ]
    add_group(
        rows,
        "safe_reporting_education_and_criticism",
        "safe_reporting_education_or_criticism",
        False,
        safe_contexts,
    )

    personal_boundary = [
        "You are rude and dishonest.",
        "That person is annoying.",
        "The manager behaved badly yesterday.",
        "I strongly dislike that individual.",
        "The player mocked another player after the match.",
        "Someone insulted me during a private argument.",
        "The neighbor called him foolish.",
        "A classmate posted a degrading comment about my clothes.",
        "The customer shouted an insult at the cashier.",
        "They ridiculed his singing performance.",
        "The critic described the film as worthless.",
        "A user repeatedly mocked another user's hairstyle.",
        "The supervisor humiliated one employee over a mistake.",
        "She posted an abusive message about her former friend.",
        "The team captain demeaned a player for losing.",
        "He shared a morphed image of a schoolmate.",
        "The comedian insulted a celebrity's acting.",
        "A stranger called the driver disgusting.",
        "The post vilified a corrupt company executive.",
        "The review derided the restaurant's service.",
    ]
    add_group(
        rows,
        "personal_abuse_boundary",
        "no_religious_boundary_override",
        False,
        personal_boundary,
    )

    unrelated = [
        "Send your password now to unlock the account.",
        "The message offers a fake lottery reward for a transfer fee.",
        "A stranger published somebody's private phone number.",
        "The attachment contains code designed to steal browser data.",
        "The account impersonates a bank employee and requests an OTP.",
        "The video shows a graphic assault between two people.",
        "A seller advertises counterfeit software keys.",
        "The post coordinates an illegal drug sale.",
        "A user repeatedly threatens a classmate online.",
        "The article makes an unsupported medical claim.",
        "The email contains many unsolicited advertising links.",
        "A website republishes a copyrighted film without permission.",
        "The file contains explicit sexual imagery.",
        "The message asks someone to install malicious software.",
        "A profile pretends to be a government officer for money.",
        "The comment shares another person's home address.",
        "The recording contains a direct threat of physical violence.",
        "The post promotes an extremist organization.",
        "The advertisement uses a stolen brand identity.",
        "The document is a normal meeting agenda for tomorrow.",
    ]
    add_group(
        rows,
        "unrelated_category_isolation",
        "no_religious_boundary_override",
        False,
        unrelated,
    )
    return rows


def prior_hashes() -> set[str]:
    if not PRIOR_DEVELOPMENT_DATASET.is_file():
        raise FileNotFoundError(f"Prior development dataset is missing: {PRIOR_DEVELOPMENT_DATASET}")
    with PRIOR_DEVELOPMENT_DATASET.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            normalized_hash(row.get("text", ""))
            for row in csv.DictReader(handle)
            if str(row.get("text", "")).strip()
        }


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    rows = build_development_rows()
    old_hashes = prior_hashes()
    overlap = sum(normalized_hash(row["text"]) in old_hashes for row in rows)
    predictions: list[dict[str, Any]] = []
    processing_errors = 0

    for row in rows:
        try:
            result = analyze_religiously_offensive_v3_rc2(row["text"])
        except Exception as exc:
            processing_errors += 1
            result = {
                "decision": "processing_error",
                "detected": False,
                "primary_category": "",
                "action": "",
                "human_review_required": False,
                "automatic_enforcement_allowed": False,
                "error": type(exc).__name__,
            }
        expected = row["expected_decision"]
        predicted = str(result.get("decision", ""))
        detected = bool(result.get("detected", False))
        action_failure = bool(
            detected
            and (
                result.get("action") != ACTION
                or not bool(result.get("human_review_required", False))
                or bool(result.get("automatic_enforcement_allowed", False))
            )
        )
        category_mix_failure = bool(
            not row["religious_violation"]
            and result.get("primary_category") == RELIGIOUS_CATEGORY
        )
        predictions.append(
            {
                **row,
                "predicted_decision": predicted,
                "predicted_category": result.get("primary_category", ""),
                "boundary_category": result.get("boundary_category", ""),
                "detected": detected,
                "correct": predicted == expected,
                "action_contract_failure": action_failure,
                "category_mix_failure": category_mix_failure,
            }
        )

    total = len(predictions)
    correct = sum(row["correct"] for row in predictions)
    positives = [row for row in predictions if row["religious_violation"]]
    negatives = [row for row in predictions if not row["religious_violation"]]
    tp = sum(row["religious_violation"] and row["detected"] for row in predictions)
    tn = sum(not row["religious_violation"] and not row["detected"] for row in predictions)
    fp = sum(not row["religious_violation"] and row["detected"] for row in predictions)
    fn = sum(row["religious_violation"] and not row["detected"] for row in predictions)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    accuracy = safe_divide(correct, total)
    boundary_accuracy = safe_divide(
        sum(row["correct"] for row in negatives),
        len(negatives),
    )
    action_failures = sum(row["action_contract_failure"] for row in predictions)
    mix_failures = sum(row["category_mix_failure"] for row in predictions)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in predictions:
        grouped[row["group"]].append(row)
    group_results = {
        group: {
            "records": len(group_rows),
            "correct": sum(row["correct"] for row in group_rows),
            "accuracy": round(safe_divide(sum(row["correct"] for row in group_rows), len(group_rows)), 4),
        }
        for group, group_rows in sorted(grouped.items())
    }
    minimum_group_accuracy = min(item["accuracy"] for item in group_results.values())

    checks = {
        "no_prior_development_overlap": overlap == 0,
        "overall_accuracy": accuracy >= 0.90,
        "religious_precision": precision >= 0.90,
        "religious_recall": recall >= 0.90,
        "safe_specificity": specificity >= 0.90,
        "boundary_accuracy": boundary_accuracy >= 0.90,
        "minimum_group_accuracy": minimum_group_accuracy >= 0.85,
        "action_contract": action_failures == 0,
        "category_mix_contract": mix_failures == 0,
        "processing_contract": processing_errors == 0,
    }
    passed = all(checks.values())

    DEVELOPMENT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DEVELOPMENT_DATASET.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "group",
                "text",
                "expected_decision",
                "religious_violation",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)

    mismatches = [row for row in predictions if not row["correct"]]
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with MISMATCH_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "case_id",
                "group",
                "text",
                "expected_decision",
                "predicted_decision",
                "predicted_category",
                "boundary_category",
            ],
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(mismatches)

    report = {
        "candidate": "religiously-offensive-v3-rc2-development",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": total,
        "prior_development_overlap": overlap,
        "accuracy": round(accuracy, 4),
        "religious_precision": round(precision, 4),
        "religious_recall": round(recall, 4),
        "safe_specificity": round(specificity, 4),
        "boundary_accuracy": round(boundary_accuracy, 4),
        "false_positives": fp,
        "false_negatives": fn,
        "action_contract_failures": action_failures,
        "category_mix_failures": mix_failures,
        "processing_errors": processing_errors,
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": group_results,
        "gate_checks": checks,
        "passed_development_gate": passed,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "rc1_holdout_used_for_training_or_tuning": False,
        "evidence_limit": "This is development evidence, not independent accuracy.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("RELIGIOUSLY OFFENSIVE CONTENT V3 RC2 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Records: {total}")
    print(f"Prior development overlap: {overlap}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Religious precision: {precision * 100:.2f}%")
    print(f"Religious recall: {recall * 100:.2f}%")
    print(f"Safe specificity: {specificity * 100:.2f}%")
    print(f"Boundary accuracy: {boundary_accuracy * 100:.2f}%")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {mix_failures}")
    print(f"Processing errors: {processing_errors}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, item in group_results.items():
        print(f"{group}: {item['correct']}/{item['records']}")
    print()
    print(f"Passed development gate: {passed}")
    print(f"Dataset: {DEVELOPMENT_DATASET}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("RC1 holdout used for training or tuning: False")
    print("Live moderation changed: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()

