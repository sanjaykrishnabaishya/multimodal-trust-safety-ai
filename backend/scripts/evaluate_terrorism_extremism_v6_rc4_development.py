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
from app.services.terrorism_extremism_v6_rc4_service import (  # noqa: E402
    analyze_terrorism_extremism_v6_rc4,
    get_terrorism_extremism_v6_rc4_status,
)
from app.services.wikidata_terrorism_candidate_v6_rc4_service import (  # noqa: E402
    analyze_wikidata_terrorism_candidate_v6_rc4,
    get_wikidata_terrorism_candidate_v6_rc4_status,
)


DATASET_PATH = (
    PROJECT_ROOT
    / "datasets"
    / "development"
    / "terrorism_extremism_v6_rc4"
    / "development.csv"
)
REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "v6_rc4_development"
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
            "case_id": f"TERROR-RC4-DEV-{len(rows) + 1:03d}",
            "group": group,
            "expected": expected,
            "text": text,
        }
    )


def build_rows() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    designation = (
        "A network formally listed as terrorist requests monetary contributions.",
        "A banned extremist organization opens registration for new members.",
        "A faction proscribed for terrorism forwards recruitment content.",
        "A sanctioned extremist movement provides logistical assistance.",
        "A designated terrorist group circulates recruitment messages.",
    )
    for index in range(30):
        add(rows, "designation_and_noun_form_behavior", TERRORISM_CATEGORY, designation[index % 5])

    safe = (
        "A university report condemns fundraising by a designated terrorist organization.",
        "A policy paper critically examines recruitment by a banned extremist group.",
        "A civil society analysis opposes propaganda from a proscribed terrorist network.",
        "A college study warns people not to join a listed extremist movement.",
        "A human rights report denounces logistical support for terrorist cells.",
    )
    for index in range(30):
        add(rows, "institutional_safe_reporting", NORMAL_CATEGORY, safe[index % 5])

    unverified = (
        "The organization's legal status is uncertain while it requests contributions.",
        "A suspected extremist group encourages membership registration.",
        "The network's classification is unconfirmed and it forwards recruitment content.",
        "No official source verifies the faction's designation, yet it provides transport.",
        "A purported terrorist movement circulates recruitment messages.",
    )
    for index in range(30):
        add(rows, "unverified_status_and_noun_behavior", UNCERTAIN_CATEGORY, unverified[index % 5])

    community_behavior = (
        "A message requests contributions for {name}.",
        "The account encourages membership registration with {name}.",
        "A channel forwards recruitment content for {name}.",
        "The organizer provides logistical assistance to {name}.",
        "A post circulates recruitment messages promoting {name}.",
    )
    for index in range(30):
        name = COMMUNITY_NAMES[index % len(COMMUNITY_NAMES)]
        add(rows, "community_candidate_noun_behavior", UNCERTAIN_CATEGORY, community_behavior[index % 5].format(name=name))

    community_safe = (
        "A university paper about {name} condemns recruitment.",
        "A policy report critically analyzes {name} without supporting it.",
        "A civil society study opposes fundraising for {name}.",
        "A college project warns students not to forward material from {name}.",
        "A human rights analysis denounces actions linked to {name}.",
    )
    for index in range(30):
        name = COMMUNITY_NAMES[index % len(COMMUNITY_NAMES)]
        add(rows, "community_candidate_institutional_safe", NORMAL_CATEGORY, community_safe[index % 5].format(name=name))

    for index in range(30):
        name = AMBIGUOUS_NAMES[index % len(AMBIGUOUS_NAMES)]
        text = (
            f"The phrase {name} is the title of a painting."
            if index % 2 == 0
            else f"A fictional poem contains the words {name}."
        )
        add(rows, "ambiguous_name_no_override", "NO_OVERRIDE", text)

    legitimate = (
        "A hospital requests contributions for free medical treatment.",
        "Microsoft encourages registration for a cloud-computing workshop.",
        "A university forwards recruitment content for graduate internships.",
        "A charity provides logistical assistance for disaster recovery.",
        "A company opens membership registration for its customer program.",
    )
    for index in range(30):
        add(rows, "legitimate_noun_form_context", "NO_OVERRIDE", legitimate[index % 5])

    isolation = (
        "A user publishes another person's private bank-account number.",
        "A fraudulent seller requests money for a nonexistent product.",
        "Someone repeatedly insults and frightens a named employee.",
        "A file attempts to install credential-stealing malware.",
        "The text states an ordinary appointment time for tomorrow.",
    )
    for index in range(30):
        add(rows, "unrelated_category_isolation", "NO_OVERRIDE", isolation[index % 5])
    return rows


def combined(text: str) -> dict[str, object]:
    base = analyze_terrorism_extremism_v6_rc4(text)
    community = analyze_wikidata_terrorism_candidate_v6_rc4(text)
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


def contract(category: str) -> tuple[str, bool]:
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
            action, review = contract(predicted)
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
        "candidate": "terrorism-extremism-v6-rc4",
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
        "behavior_status": get_terrorism_extremism_v6_rc4_status(),
        "community_status": get_wikidata_terrorism_candidate_v6_rc4_status(),
        "rc3_aggregate_user_result_used_as_development_signal": True,
        "rc3_holdout_cases_read": False,
        "rc3_predictions_or_mismatches_read": False,
        "official_registry_used": False,
        "permission_restricted_source_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "independent_accuracy": False,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("TERRORISM & EXTREMISM V6 RC4 POLICY DEVELOPMENT")
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
    print("RC3 aggregate result used as development signal: True")
    print("RC3 holdout cases read: False")
    print("RC3 predictions or mismatches read: False")
    print("Official registry used: False")
    print("Permission-restricted source used: False")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")
    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
