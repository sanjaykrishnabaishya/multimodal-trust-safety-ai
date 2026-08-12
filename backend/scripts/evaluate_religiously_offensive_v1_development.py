from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.moderation_service import moderate_text


ROOT = Path(__file__).resolve().parents[2]
DATA_DIRECTORY = ROOT / "datasets" / "development" / "religiously_offensive_v1"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "development_v1"
)
DATASET_PATH = DATA_DIRECTORY / "development.csv"
REPORT_PATH = REPORT_DIRECTORY / "baseline_report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "baseline_mismatches.csv"

RELIGIOUS_CATEGORY = "Religiously Offensive Content"
HATE_CATEGORY = "Hate Speech & Discrimination"
ABUSIVE_CATEGORY = "Abusive Words"
NORMAL_CATEGORY = "Normal/Ignore"
SPAM_CATEGORY = "Spam, Scam & Phishing"
VIOLENCE_CATEGORY = "Violent Content"

MINIMUM_OVERALL_ACCURACY = 0.85
MINIMUM_RELIGIOUS_RECALL = 0.85
MINIMUM_SAFE_SPECIFICITY = 0.85
MINIMUM_BOUNDARY_ACCURACY = 0.85
MAXIMUM_ACTION_CONTRACT_FAILURES = 0


def add_cases(
    rows: list[dict[str, Any]],
    *,
    group: str,
    expected_category: str,
    texts: list[str],
    religious_violation: bool,
) -> None:
    start = len(rows) + 1
    for offset, text in enumerate(texts):
        rows.append(
            {
                "case_id": f"REL-V1-{start + offset:03d}",
                "group": group,
                "text": text,
                "expected_category": expected_category,
                "religious_violation": religious_violation,
            }
        )


def build_development_rows() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    add_cases(
        rows,
        group="symbol_scripture_desecration",
        expected_category=RELIGIOUS_CATEGORY,
        religious_violation=True,
        texts=[
            "Destroy their religious symbol and scatter the pieces outside.",
            "Damage the community's sacred emblem during the ceremony.",
            "Burn their religious book in public to insult the faith.",
            "Desecrate their religious scripture and display the damaged pages.",
            "Tear apart the sacred flag because it represents their religion.",
            "Smash the community's holy statue to mock its beliefs.",
            "Deface the religious emblem painted on the prayer-hall wall.",
            "Rip the sacred book and throw its pages into the street.",
            "Break the ceremonial symbol so worshippers cannot use it.",
            "Set fire to the community's holy text as an insult.",
            "Mutilate the sacred image displayed by the worshippers.",
            "Spit on the religious book to deliberately desecrate it.",
            "Vandalize the faith's emblem and post the destruction online.",
            "Crush the sacred object used in their religious ceremony.",
            "Cut up the religious flag to humiliate the community's faith.",
            "Paint abusive words across the sacred religious symbol.",
            "Throw the holy scripture into the fire to mock the religion.",
            "Destroy the prayer beads because they are religious objects.",
            "Damage the sacred monument specifically to insult the faith.",
            "Dismantle the religious statue and celebrate its destruction.",
        ],
    )

    add_cases(
        rows,
        group="deity_prophet_leader_denigration",
        expected_category=RELIGIOUS_CATEGORY,
        religious_violation=True,
        texts=[
            "Mock their god using deliberately degrading language.",
            "Insult their god and call the deity disgusting.",
            "Abuse their prophet with a demeaning slur.",
            "Insult their prophet to provoke the worshippers.",
            "The religious figure is disgusting and should be mocked.",
            "The religious deity is disgusting and deserves humiliation.",
            "Publish a morphed image that degrades their sacred figurehead.",
            "Use obscene insults against the community's prophet.",
            "Ridicule the deity with deliberately denigrating descriptions.",
            "Create an abusive caricature intended to humiliate their god.",
            "Call the faith's spiritual leader filthy and repulsive.",
            "Deliberately abuse the name of their revered religious teacher.",
            "Post a degrading edit of the deity to mock the religion.",
            "Describe the sacred reincarnation with obscene insults.",
            "Use humiliating language against the religion's figurehead.",
            "Morph the prophet's image into an intentionally abusive depiction.",
            "Call the worshipped deity worthless in a post attacking the faith.",
            "Publish insulting claims about the sacred religious leader.",
            "Abuse the revered prophet specifically to offend the religion.",
            "Demean the god with obscene language aimed at the faith.",
        ],
    )

    add_cases(
        rows,
        group="religious_building_desecration",
        expected_category=RELIGIOUS_CATEGORY,
        religious_violation=True,
        texts=[
            "Demolish their temple because it is a place of worship.",
            "Demolish their church to insult the religion.",
            "Demolish their mosque as an attack on the faith.",
            "Demolish their gurudwara to humiliate its worshippers' religion.",
            "Vandalize the prayer hall because it represents their faith.",
            "Deface the shrine with obscene religious insults.",
            "Damage the sacred building to mock the community's worship.",
            "Burn the religious monument as a deliberate act of desecration.",
            "Smash the altar to insult the faith practiced there.",
            "Destroy the sanctuary's sacred objects and celebrate it.",
            "Paint degrading messages across the place of worship.",
            "Break the shrine's religious emblem to offend the faith.",
            "Mutilate the sacred carvings inside the worship building.",
            "Desecrate the prayer space with deliberately obscene material.",
            "Damage the monastery's sacred statue as an insult.",
            "Destroy the chapel's religious symbols to mock worshippers.",
            "Vandalize the sacred site because of the religion it represents.",
            "Deface the worship building with attacks on its deity.",
            "Tear down the shrine's holy flag to humiliate the faith.",
            "Break the sacred fixtures inside the religious building.",
        ],
    )

    add_cases(
        rows,
        group="protected_followers_hate_boundary",
        expected_category=HATE_CATEGORY,
        religious_violation=False,
        texts=[
            "People of this religion are inferior and should be excluded.",
            "All members of this religious group are criminals.",
            "This protected religious group is not human.",
            "Remove these people because of their religion.",
            "People of this religion should not exist in our country.",
            "Boycott every person who belongs to this religion.",
            "Attack this protected group because of their religion.",
            "Followers of this faith are parasites who should be expelled.",
            "Deny jobs to everyone from this religious community.",
            "These worshippers are inferior because of their faith.",
            "Exclude all followers of this religion from public life.",
            "Members of this religious community are less than human.",
            "Destroy this group because its members follow that religion.",
            "Every follower of this faith should be forced to leave.",
            "Do not rent homes to people from that religious group.",
            "People with this religion deserve discrimination.",
            "Block this religious community from attending schools.",
            "Harm the protected group because of its religious identity.",
            "All followers of that religion are inherently dangerous.",
            "Terminate workers merely because they belong to this faith.",
        ],
    )

    add_cases(
        rows,
        group="safe_reporting_education_criticism",
        expected_category=NORMAL_CATEGORY,
        religious_violation=False,
        texts=[
            "The religious history class compares several ancient traditions.",
            "A religious studies paper examines how worship practices changed.",
            "The interfaith education workshop encourages mutual respect.",
            "This is a good-faith criticism of a religious institution's policy.",
            "The article condemns religious hatred and attacks on worshippers.",
            "A documentary reports the destruction of a historical shrine.",
            "The museum restored a damaged sacred statue for public display.",
            "The news report describes vandalism at a place of worship.",
            "The teacher explains why burning sacred books is harmful.",
            "The safety campaign asks people not to damage religious symbols.",
            "A historian discusses earlier disputes involving sacred buildings.",
            "The essay respectfully questions a religious organization's budget.",
            "Researchers study how communities protect religious monuments.",
            "The speaker condemns insults directed at prophets and deities.",
            "The report quotes an offensive statement as evidence of abuse.",
            "The interfaith group repairs a vandalized prayer hall.",
            "The lesson explains the cultural meaning of a sacred emblem.",
            "The critic disagrees with a doctrine without insulting believers.",
            "The documentary examines religious art in its historical context.",
            "The public-service announcement opposes desecration of holy sites.",
        ],
    )

    add_cases(
        rows,
        group="personal_abuse_boundary",
        expected_category=ABUSIVE_CATEGORY,
        religious_violation=False,
        texts=[
            "You are a stupid idiot.",
            "You are a pathetic loser.",
            "That person is a disgusting asshole.",
            "You are a worthless bastard.",
            "He called his coworker a useless idiot.",
            "She sent him a message saying he was stupid.",
            "You are ugly and pathetic.",
            "That user is a complete loser.",
            "You are a disgusting person.",
            "He called the creator a worthless fool.",
            "You are a useless idiot and nobody likes you.",
            "That classmate is pathetic and stupid.",
            "She called the employee an asshole.",
            "You are a complete bastard.",
            "He insulted the journalist as a pathetic loser.",
            "You are stupid and worthless.",
            "The message calls her ugly and useless.",
            "That person is a disgusting idiot.",
            "You are a pathetic fool.",
            "The comment calls him a stupid loser.",
        ],
    )

    add_cases(
        rows,
        group="unrelated_category_isolation",
        expected_category=SPAM_CATEGORY,
        religious_violation=False,
        texts=[
            "Congratulations, claim your cash prize and send your OTP now.",
            "Your account is blocked; send your password immediately.",
            "You won a reward, transfer the processing fee today.",
            "Click this suspicious link to verify your bank account.",
            "Send your card details now to receive the lottery payment.",
            "Urgent prize alert: share your OTP to claim the money.",
            "Pay the fee now or your bank account will be closed.",
            "You have won cash; provide your password for verification.",
            "Transfer money immediately to unlock your reward.",
            "Share your banking credentials to receive the prize.",
        ],
    )
    add_cases(
        rows,
        group="unrelated_category_isolation",
        expected_category=VIOLENCE_CATEGORY,
        religious_violation=False,
        texts=[
            "I will kill you tonight.",
            "I am going to shoot you.",
            "I will stab you when you arrive.",
            "The post contains graphic violence and visible bodily harm.",
            "I will physically harm you tomorrow.",
            "The footage shows a specific threat to murder someone.",
            "I am going to hurt you after work.",
            "The video depicts severe graphic violence.",
            "I will attack this person with a weapon.",
            "The message says I will murder you.",
        ],
    )

    return rows


def write_dataset(rows: list[dict[str, Any]]) -> None:
    DATA_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with DATASET_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    rows = build_development_rows()
    write_dataset(rows)
    results: list[dict[str, Any]] = []

    for row in rows:
        decision = moderate_text(text=str(row["text"]), source_context="unknown")
        correct = decision["category"] == row["expected_category"]
        action_contract_failure = bool(
            row["religious_violation"]
            and (
                decision["category"] == RELIGIOUS_CATEGORY
                and not decision["human_review_required"]
            )
        )
        results.append(
            {
                **row,
                "predicted_category": decision["category"],
                "correct": correct,
                "action_contract_failure": action_contract_failure,
                "action": decision["action"],
                "human_review_required": decision["human_review_required"],
                "confidence": decision["confidence"],
            }
        )

    total = len(results)
    correct = sum(bool(row["correct"]) for row in results)
    religious_rows = [row for row in results if row["religious_violation"]]
    religious_correct = sum(
        row["predicted_category"] == RELIGIOUS_CATEGORY for row in religious_rows
    )
    safe_rows = [
        row
        for row in results
        if row["expected_category"] == NORMAL_CATEGORY
    ]
    safe_correct = sum(row["correct"] for row in safe_rows)
    boundary_rows = [
        row
        for row in results
        if row["group"] in {
            "protected_followers_hate_boundary",
            "personal_abuse_boundary",
            "unrelated_category_isolation",
        }
    ]
    boundary_correct = sum(row["correct"] for row in boundary_rows)
    action_failures = sum(row["action_contract_failure"] for row in results)

    group_results: dict[str, dict[str, Any]] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[str(row["group"])].append(row)
    for group, group_rows in sorted(grouped.items()):
        group_correct = sum(row["correct"] for row in group_rows)
        group_results[group] = {
            "records": len(group_rows),
            "correct": group_correct,
            "accuracy": round(group_correct / len(group_rows), 4),
        }

    accuracy = correct / total
    religious_recall = religious_correct / len(religious_rows)
    safe_specificity = safe_correct / len(safe_rows)
    boundary_accuracy = boundary_correct / len(boundary_rows)
    passed = bool(
        accuracy >= MINIMUM_OVERALL_ACCURACY
        and religious_recall >= MINIMUM_RELIGIOUS_RECALL
        and safe_specificity >= MINIMUM_SAFE_SPECIFICITY
        and boundary_accuracy >= MINIMUM_BOUNDARY_ACCURACY
        and action_failures <= MAXIMUM_ACTION_CONTRACT_FAILURES
    )

    mismatch_rows = [row for row in results if not row["correct"]]
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    with MISMATCH_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        fieldnames = list(results[0])
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(mismatch_rows)

    report = {
        "candidate": "religiously-offensive-v1-rule-baseline",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": total,
        "expected_category_counts": dict(
            Counter(str(row["expected_category"]) for row in results)
        ),
        "accuracy": round(accuracy, 4),
        "religious_violation_recall": round(religious_recall, 4),
        "safe_specificity": round(safe_specificity, 4),
        "boundary_accuracy": round(boundary_accuracy, 4),
        "action_contract_failures": action_failures,
        "group_results": group_results,
        "gates": {
            "minimum_overall_accuracy": MINIMUM_OVERALL_ACCURACY,
            "minimum_religious_recall": MINIMUM_RELIGIOUS_RECALL,
            "minimum_safe_specificity": MINIMUM_SAFE_SPECIFICITY,
            "minimum_boundary_accuracy": MINIMUM_BOUNDARY_ACCURACY,
            "maximum_action_contract_failures": MAXIMUM_ACTION_CONTRACT_FAILURES,
        },
        "passed_development_gate": passed,
        "live_moderation_changed": False,
        "independent_accuracy": False,
        "dataset": str(DATASET_PATH),
        "mismatches": str(MISMATCH_PATH),
    }
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("RELIGIOUSLY OFFENSIVE CONTENT V1 DEVELOPMENT BASELINE")
    print("=" * 60)
    print(f"Records: {total}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Religious-violation recall: {religious_recall * 100:.2f}%")
    print(f"Safe specificity: {safe_specificity * 100:.2f}%")
    print(f"Boundary accuracy: {boundary_accuracy * 100:.2f}%")
    print(f"Action-contract failures: {action_failures}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, metrics in group_results.items():
        print(f"{group}: {metrics['correct']}/{metrics['records']}")
    print()
    print(f"Passed 85% development gate: {passed}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Live moderation changed: False")
    print("This is development data, not independent accuracy.")


if __name__ == "__main__":
    main()
