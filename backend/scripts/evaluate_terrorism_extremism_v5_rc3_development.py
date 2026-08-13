from __future__ import annotations

import csv
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.terrorism_extremism_service import (  # noqa: E402
    NORMAL_CATEGORY,
    TERRORISM_CATEGORY,
    UNCERTAIN_CATEGORY,
)
from app.services.terrorism_extremism_v5_rc3_service import (  # noqa: E402
    analyze_terrorism_extremism_v5_rc3,
    get_terrorism_extremism_v5_rc3_status,
)
from app.services.wikidata_terrorism_candidate_v5_rc3_service import (  # noqa: E402
    analyze_wikidata_terrorism_candidate_v5_rc3,
    get_wikidata_terrorism_candidate_v5_rc3_status,
)


DATASET_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "development"
    / "terrorism_extremism_v5_rc3"
    / "development.csv"
)
REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "v5_rc3_development"
    / "report.json"
)

COMMUNITY_NAMES = (
    "Abu Sayyaf",
    "Jemaah Islamiyah",
    "Lashkar-e-Taiba",
    "Jaish-e-Mohammed",
    "Indian Mujahideen",
    "Al-Shabaab",
    "Ansar Dine",
    "Aum Shinrikyo",
    "Red Army Faction",
    "Shining Path",
)
AMBIGUOUS_NAMES = (
    "The Base",
    "Black Star",
    "Secret Group",
    "The Revolt",
    "Kingdom of Israel",
    "Crusaders",
    "National Vanguard",
    "Caliphate State",
    "Army of God",
    "The Black Eagles",
)


def add(rows: list[dict[str, str]], group: str, expected: str, text: str) -> None:
    rows.append(
        {
            "case_id": f"TERROR-RC3-DEV-{len(rows) + 1:03d}",
            "group": group,
            "expected": expected,
            "text": text,
        }
    )


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    designation = (
        "A designated terrorist organization encourages registration by new members.",
        "A group banned as extremist collects financial contributions.",
        "A network has been listed as a terrorist organization and forwards recruitment posts.",
        "A proscribed extremist movement provides transport and safe houses.",
        "An outfit sanctioned as terrorist circulates propaganda material.",
        "A terrorist faction was officially designated and opens an enlistment drive.",
        "The organization is designated terrorist and solicits payments.",
        "The movement remains listed as extremist and invites people to register.",
        "A banned terrorist cell arranges logistical support.",
        "A network proscribed for extremism praises its fighters and recruits members.",
    )
    for index in range(40):
        add(rows, "claimed_designation_any_word_order", TERRORISM_CATEGORY, designation[index % 10])

    safe = (
        "A journalistic report condemns recruitment by a designated terrorist organization.",
        "A scholarly analysis critically examines propaganda from a banned extremist group.",
        "A public-safety advisory warns people not to finance a proscribed terrorist network.",
        "A museum archive documents a listed extremist movement and opposes its actions.",
        "An educational lesson denounces enlistment campaigns run by terrorist organizations.",
        "A police account tells readers not to forward recruitment posts from extremist groups.",
        "A historical documentary discusses a sanctioned terrorist faction without endorsing it.",
        "A research study criticizes funding methods used by banned extremist networks.",
        "A newspaper article rejects propaganda distributed by a designated terrorist movement.",
        "A classroom textbook describes extremist recruitment and discourages participation.",
    )
    for index in range(40):
        add(rows, "safe_reporting_education_and_prevention", NORMAL_CATEGORY, safe[index % 10])

    unverified = (
        "The group's designation is uncertain, but it encourages people to enlist.",
        "A possible extremist organization solicits money from users.",
        "The network's identity is not verified and it forwards recruitment posts.",
        "No reliable source confirms the faction's status, yet it opens membership registration.",
        "A purported terrorist movement provides logistical support.",
    )
    for index in range(20):
        add(rows, "unverified_status_review", UNCERTAIN_CATEGORY, unverified[index % 5])

    community_behavior = (
        "The post asks readers to register with {name}.",
        "A private message solicits contributions for {name}.",
        "The channel forwards recruitment material for {name}.",
        "The author provides logistical assistance to {name}.",
    )
    for index in range(20):
        name = COMMUNITY_NAMES[index % len(COMMUNITY_NAMES)]
        add(rows, "community_candidate_behavior", UNCERTAIN_CATEGORY, community_behavior[index % 4].format(name=name))

    community_safe = (
        "A journalistic report about {name} condemns its recruitment.",
        "A scholarly study critically examines {name} without endorsing it.",
        "A public-safety warning tells people not to donate to {name}.",
        "A historical archive documents {name} and opposes its actions.",
    )
    for index in range(20):
        name = COMMUNITY_NAMES[index % len(COMMUNITY_NAMES)]
        add(rows, "community_safe_context", NORMAL_CATEGORY, community_safe[index % 4].format(name=name))

    for index in range(20):
        name = AMBIGUOUS_NAMES[index % len(AMBIGUOUS_NAMES)]
        text = (
            f"The phrase join {name} appears in a fictional board game."
            if index % 2 == 0
            else f"An art poster displays the words {name}."
        )
        add(rows, "ambiguous_name_safety", "NO_OVERRIDE", text)

    legitimate = (
        "Microsoft solicits applications for cloud engineering roles.",
        "A hospital provides logistical assistance to its emergency clinic.",
        "A charity forwards volunteer registration forms for relief work.",
        "A university invites students to join a research project.",
        "A software company collects subscription payments from customers.",
    )
    for index in range(20):
        add(rows, "legitimate_jobs_and_operations", "NO_OVERRIDE", legitimate[index % 5])

    isolation = (
        "A user exposes another person's private email address.",
        "A fake prize message asks the recipient to pay a processing fee.",
        "Someone repeatedly intimidates a named student online.",
        "An attachment attempts to install malicious software.",
        "The article makes an unsupported factual claim.",
    )
    for index in range(20):
        add(rows, "unrelated_category_isolation", "NO_OVERRIDE", isolation[index % 5])
    return rows


def combined(text: str) -> dict[str, object]:
    base = analyze_terrorism_extremism_v5_rc3(text)
    community = analyze_wikidata_terrorism_candidate_v5_rc3(text)
    if base.get("category") == TERRORISM_CATEGORY:
        return base
    if community.get("category") == UNCERTAIN_CATEGORY:
        return community
    if base.get("category") in {UNCERTAIN_CATEGORY, NORMAL_CATEGORY}:
        return base
    return {
        "category": None,
        "action": "No boundary override",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }


def expected_contract(category: str) -> tuple[str, bool]:
    if category == TERRORISM_CATEGORY:
        return "Block and escalate", True
    if category == UNCERTAIN_CATEGORY:
        return "Refer to human review", True
    if category == NORMAL_CATEGORY:
        return "Allow", False
    return "No boundary override", False


def main() -> None:
    rows = build_rows()
    DATASET_PATH.parent.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    group_total: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    correct = 0
    action_failures = 0
    policy_failures = 0
    processing_errors = 0
    for row in rows:
        group = row["group"]
        expected = row["expected"]
        group_total[group] += 1
        try:
            result = combined(row["text"])
            predicted = str(result.get("category") or "NO_OVERRIDE")
            is_correct = predicted == expected
            correct += int(is_correct)
            group_correct[group] += int(is_correct)
            action, review = expected_contract(predicted)
            if result.get("action") != action or result.get("human_review_required") is not review:
                action_failures += 1
            if result.get("automatic_enforcement_allowed") is not False or result.get("connected_to_live_moderation") is not False:
                policy_failures += 1
        except Exception:
            processing_errors += 1

    accuracy = correct / len(rows)
    group_accuracy = {group: group_correct[group] / total for group, total in sorted(group_total.items())}
    minimum_group = min(group_accuracy.values())
    passed = accuracy >= 0.90 and minimum_group >= 0.85 and action_failures == 0 and policy_failures == 0 and processing_errors == 0
    report = {
        "candidate": "terrorism-extremism-v5-rc3",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "accuracy": accuracy,
        "minimum_group_accuracy": minimum_group,
        "action_contract_failures": action_failures,
        "policy_contract_failures": policy_failures,
        "processing_errors": processing_errors,
        "group_results": {
            group: {"correct": group_correct[group], "records": total, "accuracy": group_accuracy[group]}
            for group, total in sorted(group_total.items())
        },
        "passed_development_gate": passed,
        "behavior_status": get_terrorism_extremism_v5_rc3_status(),
        "community_status": get_wikidata_terrorism_candidate_v5_rc3_status(),
        "rc2_aggregate_user_result_used_as_development_signal": True,
        "rc2_holdout_cases_read": False,
        "rc2_predictions_or_mismatches_read": False,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "independent_accuracy": False,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("TERRORISM & EXTREMISM V5 RC3 POLICY DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {len(rows):,}")
    print(f"Accuracy: {100 * accuracy:.2f}%")
    print(f"Minimum group accuracy: {100 * minimum_group:.2f}%")
    print(f"Action-contract failures: {action_failures:,}")
    print(f"Policy-contract failures: {policy_failures:,}")
    print(f"Processing errors: {processing_errors:,}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, total in sorted(group_total.items()):
        print(f"{group}: {group_correct[group]}/{total} ({100 * group_accuracy[group]:.2f}%)")
    print(f"\nPassed development gate: {passed}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("RC2 aggregate result used as a development signal: True")
    print("RC2 holdout cases read: False")
    print("RC2 predictions or mismatches read: False")
    print("Official registry used: False")
    print("Permission-restricted source used: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
