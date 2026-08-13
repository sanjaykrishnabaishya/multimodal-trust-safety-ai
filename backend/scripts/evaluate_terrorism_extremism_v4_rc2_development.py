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
from app.services.terrorism_extremism_v4_rc2_service import (  # noqa: E402
    analyze_terrorism_extremism_v4_rc2,
    get_terrorism_extremism_v4_rc2_status,
)
from app.services.wikidata_terrorism_candidate_v4_rc2_service import (  # noqa: E402
    analyze_wikidata_terrorism_candidate_v4_rc2,
    get_wikidata_terrorism_candidate_v4_rc2_status,
)


DATASET_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "development"
    / "terrorism_extremism_v4_rc2"
    / "development.csv"
)
REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "v4_rc2_development"
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


def add(
    rows: list[dict[str, str]],
    group: str,
    expected: str,
    text: str,
) -> None:
    rows.append(
        {
            "case_id": f"TERROR-RC2-DEV-{len(rows) + 1:03d}",
            "group": group,
            "expected": expected,
            "text": text,
        }
    )


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    designation_prefix = (
        "A designated terrorist organization is encouraging readers to enlist.",
        "A banned extremist group is collecting money for operational support.",
        "A proscribed terrorist network is circulating recruitment posts.",
        "A listed extremist movement is inviting new members to sign up.",
        "A sanctioned terrorist faction is providing transport and supplies.",
    )
    for index in range(20):
        add(rows, "claimed_designation_prefix", TERRORISM_CATEGORY, designation_prefix[index % 5])

    designation_suffix = (
        "The group has been listed as an extremist organization and invites people to join.",
        "The network was officially proscribed as a terrorist organization and solicits contributions.",
        "The movement is designated as extremist and circulates recruitment clips.",
        "The organization remains banned as a terrorist group and urges readers to enlist.",
        "The faction was sanctioned as extremist and provides logistical support.",
    )
    for index in range(20):
        add(rows, "claimed_designation_suffix", TERRORISM_CATEGORY, designation_suffix[index % 5])

    unknown_status = (
        "The organization invites enlistment, but its legal status remains unverified.",
        "Membership applications are open although the group's designation is not confirmed.",
        "An alleged terrorist group solicits contributions from readers.",
        "The network urges people to join, but its identity has not been authenticated.",
        "A possible extremist movement circulates recruitment posts.",
    )
    for index in range(20):
        add(rows, "unverified_identity_or_status", UNCERTAIN_CATEGORY, unknown_status[index % 5])

    community_behavior = (
        "The post invites readers to join {name}.",
        "The message collects money as support for {name}.",
        "The channel circulates recruitment posts for {name}.",
        "The speaker urges people to enlist with {name}.",
    )
    for index in range(20):
        name = COMMUNITY_NAMES[index % len(COMMUNITY_NAMES)]
        add(
            rows,
            "community_name_plus_behavior",
            UNCERTAIN_CATEGORY,
            community_behavior[index % 4].format(name=name),
        )

    for index in range(20):
        name = AMBIGUOUS_NAMES[index % len(AMBIGUOUS_NAMES)]
        text = (
            f"Please join {name} before the neighborhood meeting."
            if index % 2 == 0
            else f"The words {name} appear in a fictional story title."
        )
        add(rows, "ambiguous_name_without_external_context", "NO_OVERRIDE", text)

    for index in range(20):
        name = AMBIGUOUS_NAMES[index % len(AMBIGUOUS_NAMES)]
        text = (
            f"The {name} organization invites people to enlist."
            if index % 2 == 0
            else f"Collect money for the organization called {name}."
        )
        add(rows, "ambiguous_name_with_external_context", UNCERTAIN_CATEGORY, text)

    safe = (
        "A news report describes a listed terrorist group and condemns its recruitment.",
        "An academic study examines an alleged extremist organization without endorsing it.",
        "A museum archive documents a banned network and opposes its propaganda.",
        "A police report warns the public not to provide funds to a proscribed group.",
        "A historical documentary discusses recruitment by an extremist movement and condemns it.",
    )
    for index in range(20):
        add(rows, "safe_reporting_and_condemnation", NORMAL_CATEGORY, safe[index % 5])

    legitimate = (
        "Microsoft invites engineers to join its cloud support team.",
        "A hospital solicits applications for nursing positions.",
        "A charity collects money for flood relief operations.",
        "A university circulates internship posts for its research laboratory.",
        "A logistics business provides transport and supplies to customers.",
    )
    for index in range(20):
        add(rows, "legitimate_jobs_and_operations", "NO_OVERRIDE", legitimate[index % 5])

    neutral = (
        "The library index includes a reference to {name}.",
        "A newspaper archive contains the name {name}.",
        "The document footnote mentions {name}.",
        "A history-book title refers to {name}.",
    )
    for index in range(20):
        name = COMMUNITY_NAMES[index % len(COMMUNITY_NAMES)]
        add(rows, "neutral_community_mentions", "NO_OVERRIDE", neutral[index % 4].format(name=name))

    isolation = (
        "The message exposes a person's private telephone number.",
        "A fake bank account requests a customer's password.",
        "The post repeatedly insults and intimidates one named person.",
        "The document contains an ordinary weather forecast.",
        "The software installs a malicious executable.",
    )
    for index in range(20):
        add(rows, "unrelated_category_isolation", "NO_OVERRIDE", isolation[index % 5])
    return rows


def combined(text: str) -> dict[str, object]:
    base = analyze_terrorism_extremism_v4_rc2(text)
    community = analyze_wikidata_terrorism_candidate_v4_rc2(text)
    if base.get("category") == TERRORISM_CATEGORY:
        return base
    if community.get("category") == UNCERTAIN_CATEGORY:
        return community
    if base.get("category") in {TERRORISM_CATEGORY, UNCERTAIN_CATEGORY, NORMAL_CATEGORY}:
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
            predicted = result.get("category") or "NO_OVERRIDE"
            is_correct = predicted == expected
            correct += int(is_correct)
            group_correct[group] += int(is_correct)
            action, review = expected_contract(str(predicted))
            if result.get("action") != action or result.get("human_review_required") is not review:
                action_failures += 1
            if result.get("automatic_enforcement_allowed") is not False or result.get("connected_to_live_moderation") is not False:
                policy_failures += 1
        except Exception:
            processing_errors += 1

    accuracy = correct / len(rows)
    group_accuracy = {
        group: group_correct[group] / total
        for group, total in sorted(group_total.items())
    }
    minimum_group = min(group_accuracy.values())
    passed = (
        accuracy >= 0.90
        and minimum_group >= 0.85
        and action_failures == 0
        and policy_failures == 0
        and processing_errors == 0
    )
    report = {
        "candidate": "terrorism-extremism-v4-rc2",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "accuracy": accuracy,
        "minimum_group_accuracy": minimum_group,
        "action_contract_failures": action_failures,
        "policy_contract_failures": policy_failures,
        "processing_errors": processing_errors,
        "group_results": {
            group: {
                "correct": group_correct[group],
                "records": total,
                "accuracy": group_accuracy[group],
            }
            for group, total in sorted(group_total.items())
        },
        "passed_development_gate": passed,
        "behavior_status": get_terrorism_extremism_v4_rc2_status(),
        "community_status": get_wikidata_terrorism_candidate_v4_rc2_status(),
        "rc1_independent_holdout_read": False,
        "rc1_individual_predictions_read": False,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "independent_accuracy": False,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("TERRORISM & EXTREMISM V4 RC2 POLICY DEVELOPMENT")
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
    print("RC1 independent holdout read: False")
    print("RC1 individual predictions read: False")
    print("Official registry used: False")
    print("Permission-restricted source used: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
