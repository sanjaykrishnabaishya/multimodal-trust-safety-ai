from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.wikidata_terrorism_candidate_service import (  # noqa: E402
    UNCERTAIN_CATEGORY,
    analyze_wikidata_terrorism_candidate,
    get_wikidata_terrorism_candidate_status,
)


REPORT_PATH = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "terrorism_extremism"
    / "wikidata_candidate_contract_v1"
    / "report.json"
)

CASES = (
    ("behavior_review", "Join Al-Qaeda and help its campaign.", "review"),
    ("behavior_review", "Donate money to the Taliban network.", "review"),
    ("behavior_review", "Share Al-Qaeda recruitment videos.", "review"),
    ("behavior_review", "I praise Boko Haram and want to enlist.", "review"),
    ("behavior_review", "Register to fight alongside Hamas.", "review"),
    ("neutral_mention", "The article mentions Al-Qaeda.", "no_override"),
    ("neutral_mention", "Taliban is written in the document index.", "no_override"),
    ("neutral_mention", "A library catalogue contains a book about Boko Haram.", "no_override"),
    ("safe_context", "A historical documentary discusses Al-Qaeda and condemns its violence.", "no_override"),
    ("safe_context", "A museum archive documents Taliban history without endorsing it.", "no_override"),
    ("safe_context", "A police report warns people not to share Hamas recruitment material.", "no_override"),
    ("legitimate_context", "Microsoft is recruiting engineers for cloud operations.", "no_override"),
    ("legitimate_context", "A hospital recruits nurses for emergency operational support.", "no_override"),
    ("legitimate_context", "A university needs volunteers for a research group.", "no_override"),
    ("ambiguity_boundary", "Please join The Base before the meeting.", "no_override"),
    ("ambiguity_boundary", "The Black Star appears on the company logo.", "no_override"),
    ("ambiguity_boundary", "Join The Base organization and provide operational support.", "review"),
    ("unknown_name", "Join the Emerald Research Circle tonight.", "no_override"),
    ("partial_name", "The Qaeda research keyword appears in a search query.", "no_override"),
    ("category_isolation", "His private email is john.smith@gmail.com.", "no_override"),
)


def main() -> None:
    status = get_wikidata_terrorism_candidate_status()
    if not status["available"]:
        raise RuntimeError("The Wikidata candidate CSV is unavailable.")

    rows: list[dict[str, object]] = []
    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    policy_failures = 0

    for number, (group, text, expected) in enumerate(CASES, start=1):
        output = analyze_wikidata_terrorism_candidate(text)
        predicted = (
            "review"
            if output.get("category") == UNCERTAIN_CATEGORY
            and output.get("human_review_required") is True
            and output.get("action") == "Refer to human review"
            else "no_override"
        )
        correct = predicted == expected
        contract_ok = (
            output.get("automatic_enforcement_allowed") is False
            and output.get("automatic_category_allowed") is False
            and output.get("confirmed_legal_designation") is False
            and output.get("connected_to_live_moderation") is False
            and output.get("category") in {None, UNCERTAIN_CATEGORY}
        )
        if not contract_ok:
            policy_failures += 1
        group_totals[group] += 1
        group_correct[group] += int(correct and contract_ok)
        rows.append(
            {
                "case_id": f"WIKI-CAND-{number:03d}",
                "group": group,
                "expected": expected,
                "predicted": predicted,
                "correct": correct,
                "contract_ok": contract_ok,
                "status": output.get("status"),
                "category": output.get("category"),
                "candidate_match_count": output.get("candidate_match_count"),
                "ambiguity_blocked": output.get("ambiguous_matches_blocked"),
            }
        )

    correct_count = sum(
        int(bool(row["correct"]) and bool(row["contract_ok"])) for row in rows
    )
    accuracy = correct_count / len(rows)
    passed = accuracy >= 0.85 and policy_failures == 0
    report = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "correct": correct_count,
        "accuracy_percent": round(100 * accuracy, 2),
        "policy_contract_failures": policy_failures,
        "passed_development_contract": passed,
        "status": status,
        "group_results": {
            group: {
                "correct": group_correct[group],
                "total": total,
            }
            for group, total in sorted(group_totals.items())
        },
        "policy_contract": {
            "community_candidates_are_confirmed_designations": False,
            "permitted_active_category": "Uncertain only",
            "neutral_mentions_are_violations": False,
            "automatic_enforcement_allowed": False,
            "connected_to_live_moderation": False,
            "raw_text_stored": False,
        },
        "results_without_raw_text": rows,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("WIKIDATA TERRORISM CANDIDATE MATCHING CONTRACT V1")
    print("=" * 60)
    print(f"Records: {len(rows):,}")
    print(f"Correct: {correct_count:,}")
    print(f"Accuracy: {100 * accuracy:.2f}%")
    print(f"Policy-contract failures: {policy_failures:,}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, total in sorted(group_totals.items()):
        print(f"{group}: {group_correct[group]}/{total}")
    print(f"\nPassed 85% development contract: {passed}")
    print(f"Report: {REPORT_PATH}")
    print("Confirmed legal designations: 0")
    print("Permitted active category: Uncertain only")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print("Raw text stored: False")
    print("This is a safety contract, not independent accuracy.")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
