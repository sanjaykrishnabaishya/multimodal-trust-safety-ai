from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.fusion_service import fuse_moderation_decision


VERSION = "2026.08-cyberbullying-v1-development"
CATEGORY = "Cyberbullying & Harassment"
ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = ROOT / "datasets" / "development" / "cyberbullying_v1"
REPORT_DIR = ROOT / "reports" / "evaluation" / "cyberbullying" / "development_v1"


@dataclass(frozen=True)
class Case:
    case_id: str
    group: str
    text: str
    expected_detected: bool


def make_cases() -> list[Case]:
    groups: dict[str, tuple[bool, tuple[str, ...]]] = {
        "repeated_targeted_abuse": (
            True,
            (
                "Every day you post that Riya is stupid and worthless.",
                "You keep calling Arjun a disgusting loser under each of his photos.",
                "For the third time this week, they mocked Meera's appearance in the group chat.",
                "He repeatedly sends Karan messages saying nobody likes him.",
                "The account posts humiliating edits of the same student every morning.",
                "They keep tagging Sana in comments that call her useless and pathetic.",
                "Each night, the group sends Amit insulting messages about his body.",
                "She repeatedly tells Neha that everyone would be happier without her.",
                "The page has posted five cruel memes targeting one classmate.",
                "He follows Dev across platforms to call him an idiot again and again.",
                "For several days they have publicly mocked Priya's speech difficulty.",
                "The same user comments 'you are a failure' on every video Rahul uploads.",
                "They repeatedly share an embarrassing picture to humiliate one employee.",
                "She keeps sending targeted voice notes calling Leena ugly and unwanted.",
                "The chat members repeatedly ridicule one boy's clothes and family income.",
                "He created multiple posts solely to embarrass his former friend.",
                "Every week the account publishes another insulting collage about Anil.",
                "They continue mocking the same child even after he asks them to stop.",
                "She repeatedly spreads humiliating nicknames about one coworker.",
                "The group targets Nisha with degrading comments whenever she comes online.",
            ),
        ),
        "unwanted_contact": (
            True,
            (
                "I told you to stop, but you keep demanding my phone number.",
                "He sends new messages every day after she said she wants no contact.",
                "Give me your private number; I will keep asking until you do.",
                "She blocked him twice, and he created another account to contact her.",
                "Reply to my private messages or I will continue messaging all night.",
                "They repeatedly pressure the student to move the conversation into a private chat.",
                "After I said no, the user kept requesting my address and mobile number.",
                "He contacts her through friends because she asked him to leave her alone.",
                "The account sends dozens of unwanted messages demanding a response.",
                "She keeps asking for personal contact details despite repeated refusals.",
                "He says he will not stop messaging until I agree to meet privately.",
                "The user opens replacement profiles whenever the recipient blocks him.",
                "They continue calling and messaging after being clearly told to stop.",
                "Send me a private message now; I will keep bothering you otherwise.",
                "He repeatedly asks a minor to share a personal phone number after refusal.",
                "She receives unwanted direct messages from the same person every morning.",
                "The sender ignores her request for no further contact and writes again.",
                "They keep pressuring him to join a private video call he declined.",
                "The stranger demands her number in every comment despite her objections.",
                "He uses several accounts to continue unwanted contact with one person.",
            ),
        ),
        "coordinated_harassment": (
            True,
            (
                "Everyone go to Vikram's page and flood it with insulting comments.",
                "Let's all mock this student under every post she makes.",
                "Share his profile so the whole group can humiliate him tonight.",
                "Join me in sending abusive messages to this journalist.",
                "The group plans shifts to repeatedly harass one creator online.",
                "Go report her account and call her disgusting in the comments.",
                "Tell your followers to target this employee with degrading messages.",
                "We should fill his inbox with insults until he deletes his page.",
                "Everyone repost this embarrassing photo to shame the same person.",
                "Bring more people into the chat so we can bully him together.",
                "The channel instructs members to ridicule one classmate every day.",
                "Send this profile to the group and ask them all to abuse the owner.",
                "Let's coordinate hundreds of humiliating replies against her.",
                "The administrator encourages members to keep harassing a former member.",
                "Go to his livestream and repeatedly call him worthless.",
                "Recruit other users to pressure this person into leaving the platform.",
                "The post provides instructions for a coordinated pile-on against one woman.",
                "Everyone should tag him in cruel memes until he responds.",
                "The group agrees to publish insulting edits of one teacher.",
                "Ask all your friends to send degrading comments to this account.",
            ),
        ),
        "targeted_threat": (
            True,
            (
                "I will break your jaw when you leave work.",
                "We are waiting outside your home to hurt you.",
                "Delete that post or your brother will be attacked.",
                "I have a knife and I am coming for you tonight.",
                "Meet me after class and I will smash your face.",
                "You will be beaten if you return here.",
                "I know your route and plan to injure you on the way home.",
                "Someone should physically attack him for that opinion.",
                "I will burn your room while you are inside.",
                "She deserves to have her legs broken.",
                "Pay me or my friends will harm your family.",
                "When I find you, I am going to stab you.",
                "We will corner her outside and beat her.",
                "I bought a weapon specifically to use against you.",
                "Watch your back because I intend to hurt you.",
                "You will need a hospital after our next meeting.",
                "Go attack that person and teach him a lesson.",
                "I am coming to your office to break your arms.",
                "Your parents will suffer if you refuse.",
                "I will send people to assault you tomorrow.",
            ),
        ),
        "allowed_boundary": (
            False,
            (
                "I disagree with Rahul's proposal because the cost estimate is incomplete.",
                "Please do not contact me again.",
                "Would you like to exchange phone numbers? It is completely fine to say no.",
                "The article discusses how schools can prevent cyberbullying.",
                "She reported the abusive messages to a platform moderator.",
                "The documentary examines online harassment without targeting anyone.",
                "I dislike this film and think the story is poorly written.",
                "Please send the project file in a private message if convenient.",
                "He blocked the account and saved the unwanted messages as evidence.",
                "The workshop teaches respectful disagreement on social media.",
                "One customer left a negative but factual review of the service.",
                "The news report quotes a threat while describing a police investigation.",
                "Never pressure someone to provide private contact information.",
                "The teacher explained why humiliating classmates is unacceptable.",
                "I strongly oppose her policy position but respect her right to speak.",
                "Could we schedule one call about the invoice? No problem if not.",
                "The safety guide tells users how to report coordinated harassment.",
                "They discussed a fictional bully in a classroom lesson.",
                "The moderator removed insulting comments directed at a user.",
                "This critique addresses the argument and contains no personal abuse.",
            ),
        ),
        "category_isolation": (
            False,
            (
                "Send your OTP to claim the cash prize.",
                "This post publishes a private home address.",
                "The attachment installs software that steals passwords.",
                "The account impersonates a bank officer and requests money.",
                "The message promotes an extremist organization.",
                "The listing offers illegal drugs for sale.",
                "The page distributes a copyrighted movie without permission.",
                "The article contains a false claim about a national election.",
                "The image contains explicit adult nudity.",
                "The comment attacks an entire religious group.",
                "The message contains an unwanted sexual proposition at work.",
                "The file contains a normal monthly financial report.",
                "The family photographed the Eiffel Tower during their holiday.",
                "The meeting begins at nine tomorrow morning.",
                "The recipe calls for two cups of rice.",
                "A doctor explains a routine medical procedure.",
                "The sports report summarizes yesterday's match.",
                "The student submitted a history assignment.",
                "The shop confirms that the parcel has shipped.",
                "The weather forecast predicts rain this evening.",
            ),
        ),
    }
    cases: list[Case] = []
    for group, (expected, texts) in groups.items():
        for position, text in enumerate(texts, 1):
            cases.append(Case(f"CB-{group[:3].upper()}-{position:03d}", group, text, expected))
    return cases


def main() -> None:
    cases = make_cases()
    DATASET_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    dataset_path = DATASET_DIR / "development.csv"
    mismatch_path = REPORT_DIR / "baseline_mismatches.csv"
    report_path = REPORT_DIR / "baseline_report.json"

    with dataset_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(("case_id", "group", "text", "expected_detected"))
        for case in cases:
            writer.writerow((case.case_id, case.group, case.text, case.expected_detected))

    rows: list[dict[str, object]] = []
    group_counts: dict[str, Counter[str]] = defaultdict(Counter)
    true_positive = true_negative = false_positive = false_negative = 0
    action_failures = 0
    for case in cases:
        result = fuse_moderation_decision(case.text, "user", ["text"])
        predicted = result.get("category") == CATEGORY
        correct = predicted == case.expected_detected
        if case.expected_detected and predicted:
            true_positive += 1
        elif not case.expected_detected and not predicted:
            true_negative += 1
        elif not case.expected_detected and predicted:
            false_positive += 1
        else:
            false_negative += 1
        if predicted and not bool(result.get("human_review_required", False)):
            action_failures += 1
        group_counts[case.group]["total"] += 1
        group_counts[case.group]["correct"] += int(correct)
        rows.append(
            {
                "case_id": case.case_id,
                "group": case.group,
                "expected_detected": case.expected_detected,
                "predicted_category": result.get("category", ""),
                "predicted_action": result.get("action", ""),
                "human_review_required": result.get("human_review_required", False),
                "correct": correct,
                "text": case.text,
            }
        )

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    specificity = true_negative / (true_negative + false_positive) if true_negative + false_positive else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    accuracy = (true_positive + true_negative) / len(cases)

    mismatches = [row for row in rows if not row["correct"]]
    with mismatch_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(mismatches)

    report = {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(cases),
        "accuracy": round(accuracy, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "f1": round(f1, 4),
        "true_positives": true_positive,
        "true_negatives": true_negative,
        "false_positives": false_positive,
        "false_negatives": false_negative,
        "action_contract_failures": action_failures,
        "group_results": {
            group: {
                "total": values["total"],
                "correct": values["correct"],
                "accuracy": round(values["correct"] / values["total"], 4),
            }
            for group, values in sorted(group_counts.items())
        },
        "passed_85_percent_development_gate": (
            accuracy >= 0.85
            and precision >= 0.85
            and recall >= 0.85
            and specificity >= 0.85
            and f1 >= 0.85
            and action_failures == 0
        ),
        "notice": "Development baseline only; not independent accuracy.",
    }
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("CYBERBULLYING & HARASSMENT V1 DEVELOPMENT BASELINE")
    print("=" * 60)
    print(f"Records: {len(cases)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Precision: {precision * 100:.2f}%")
    print(f"Recall: {recall * 100:.2f}%")
    print(f"Specificity: {specificity * 100:.2f}%")
    print(f"F1: {f1 * 100:.2f}%")
    print(f"False positives: {false_positive}")
    print(f"False negatives: {false_negative}")
    print(f"Action-contract failures: {action_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, values in sorted(group_counts.items()):
        print(f"{group}: {values['correct']}/{values['total']}")
    print(f"\nPassed 85% development gate: {report['passed_85_percent_development_gate']}")
    print(f"Dataset: {dataset_path}")
    print(f"Report: {report_path}")
    print(f"Mismatches: {mismatch_path}")
    print("This is development data, not independent accuracy.")


if __name__ == "__main__":
    main()
