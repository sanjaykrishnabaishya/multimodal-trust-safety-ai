from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.services.fusion_service import fuse_moderation_decision


VERSION = "2026.08-v2-development"
VIOLENT = "Violent Content"
CYBER = "Cyberbullying & Harassment"
NORMAL = "Normal/Ignore"


@dataclass(frozen=True)
class Case:
    case_id: str
    group: str
    text: str
    expected: str
    review: bool
    action_mode: str


def build_cases() -> list[Case]:
    cases: list[Case] = []

    depiction_openers = (
        "The uploaded image shows",
        "The video visibly depicts",
        "A close-up photograph displays",
        "The recording focuses on",
        "The animated scene portrays",
        "The camera captures",
    )
    graphic_objects = (
        "a severed human limb",
        "a detached head beside a body",
        "exposed internal organs",
        "crushed bone protruding through skin",
        "bloody mutilated remains",
        "a victim being tortured",
        "a body cut into pieces",
        "a captive being skinned alive",
        "charred human remains",
        "a dismembered corpse",
    )

    index = 1
    for opener in depiction_openers:
        for graphic_object in graphic_objects:
            cases.append(
                Case(
                    f"V2-G-{index:03d}",
                    "graphic_depiction",
                    f"{opener} {graphic_object}.",
                    VIOLENT,
                    True,
                    "restrict",
                )
            )
            index += 1

    contextual_templates = (
        "A non-graphic news report describes {item}, and all imagery is blurred.",
        "A documentary discusses {item} without displaying unblurred details.",
        "A history lesson analyzes {item} and provides a viewer warning.",
        "A media-literacy class examines a censored depiction of {item}.",
    )
    contextual_items = (
        "a severed limb",
        "a victim being tortured",
        "a dismembered body",
        "exposed organs",
        "charred remains",
    )
    index = 1
    for template in contextual_templates:
        for item in contextual_items:
            cases.append(
                Case(
                    f"V2-C-{index:03d}",
                    "allowed_context",
                    template.format(item=item),
                    VIOLENT,
                    False,
                    "allow",
                )
            )
            index += 1

    threats = (
        "I will break your arms when you arrive.",
        "We are going to stab him outside.",
        "Someone should shoot that person.",
        "I have a knife and I am coming for you.",
        "Your family will be harmed if you refuse.",
        "Let us attack her after work.",
        "He deserves to be beaten to death.",
        "Watch your back because I will hurt you.",
        "I intend to murder your brother.",
        "Go smash his face for saying that.",
    )
    for repeat in range(3):
        for position, text in enumerate(threats, 1):
            cases.append(
                Case(
                    f"V2-T-{repeat * len(threats) + position:03d}",
                    "threat_boundary",
                    text,
                    CYBER,
                    True,
                    "review",
                )
            )

    safe = (
        "The singer killed it on stage.",
        "The software bug is killing performance.",
        "Please kill the frozen computer process.",
        "The photographer shot a wedding portrait.",
        "The striker took a shot at goal.",
        "The team attacked the defence after halftime.",
        "The herbicide kills weeds.",
        "The article supports violence-prevention education.",
        "Police prevented the assault before anyone was injured.",
        "She reported the threatening message to the police.",
        "A doctor repaired a routine bone fracture.",
        "Students studied a diagram of human organs.",
        "The museum displays an intact historical skeleton.",
        "Actors rehearsed a safe stage fight.",
        "The game character loses health without visible injury.",
        "The meeting starts at nine tomorrow morning.",
        "Our team destroyed the competition in sales.",
        "The comedian slayed the audience.",
        "This restaurant makes a killer dessert.",
        "Never threaten or harm another person.",
    )
    for repeat in range(3):
        for position, text in enumerate(safe, 1):
            cases.append(
                Case(
                    f"V2-S-{repeat * len(safe) + position:03d}",
                    "safe_boundary",
                    text,
                    NORMAL,
                    False,
                    "allow",
                )
            )

    isolation = (
        "Send your OTP to receive the prize.",
        "Publish this private telephone number.",
        "Fund the extremist organization.",
        "Install the program to steal passwords.",
        "People of this protected group should not exist.",
        "Keep contacting her after she says stop.",
        "Try the rooftop stunt without safety equipment.",
        "This unsupported post claims a miracle cure.",
        "Buy the counterfeit product through this link.",
        "This is a normal family holiday photograph.",
    )
    for repeat in range(3):
        for position, text in enumerate(isolation, 1):
            cases.append(
                Case(
                    f"V2-I-{repeat * len(isolation) + position:03d}",
                    "category_isolation",
                    text,
                    "not_violent",
                    False,
                    "other",
                )
            )
    return cases


def divide(a: int, b: int) -> float:
    return a / b if b else 0.0


def pct(value: float) -> float:
    return round(value * 100.0, 2)


def action_ok(case: Case, result: dict) -> bool:
    action = str(result.get("action", "")).casefold()
    review = bool(result.get("human_review_required", False))
    if case.action_mode in {"restrict", "review"}:
        return review and any(
            word in action
            for word in ("block", "limit", "flag", "review", "warning", "escalate")
        )
    if case.action_mode == "allow":
        return not review and ("allow" in action or case.expected == NORMAL)
    return True


def main() -> None:
    root = Path(__file__).resolve().parents[2]
    cases = build_cases()
    canonical = "\n".join(
        f"{c.case_id}|{c.group}|{c.text}|{c.expected}|{c.review}|{c.action_mode}"
        for c in cases
    ).encode("utf-8")
    data_hash = hashlib.sha256(canonical).hexdigest()
    confusion = Counter()
    groups: dict[str, Counter] = defaultdict(Counter)
    exact = 0
    action_failures = 0
    rows = []

    print("Running Violent Content V2 development evaluation...")
    print(f"Records: {len(cases)}")
    print("This is development data, not independent accuracy.\n")

    for case in cases:
        result = fuse_moderation_decision(case.text, "user", ["text"])
        predicted = str(result.get("category", ""))
        expected_positive = case.expected == VIOLENT
        predicted_positive = predicted == VIOLENT
        if expected_positive and predicted_positive:
            confusion["TP"] += 1
        elif expected_positive:
            confusion["FN"] += 1
        elif predicted_positive:
            confusion["FP"] += 1
        else:
            confusion["TN"] += 1
        category_ok = (
            predicted != VIOLENT
            if case.expected == "not_violent"
            else predicted == case.expected
        )
        contract_ok = action_ok(case, result)
        correct = category_ok and contract_ok
        exact += int(correct)
        action_failures += int(not contract_ok)
        groups[case.group]["records"] += 1
        groups[case.group]["correct"] += int(correct)
        rows.append(
            {
                "case_id": case.case_id,
                "group": case.group,
                "text": case.text,
                "expected": case.expected,
                "predicted": predicted,
                "action": result.get("action", ""),
                "review": result.get("human_review_required", False),
                "correct": correct,
            }
        )

    tp, tn, fp, fn = (
        confusion["TP"],
        confusion["TN"],
        confusion["FP"],
        confusion["FN"],
    )
    total = len(cases)
    accuracy = divide(tp + tn, total)
    precision = divide(tp, tp + fp)
    recall = divide(tp, tp + fn)
    specificity = divide(tn, tn + fp)
    f1 = divide(2 * precision * recall, precision + recall)
    exact_accuracy = divide(exact, total)
    group_report = {
        name: {
            "records": stats["records"],
            "correct": stats["correct"],
            "accuracy_percent": pct(divide(stats["correct"], stats["records"])),
        }
        for name, stats in sorted(groups.items())
    }
    passed = (
        accuracy >= 0.85
        and precision >= 0.85
        and recall >= 0.85
        and specificity >= 0.85
        and exact_accuracy >= 0.85
        and action_failures == 0
    )

    report_dir = (
        root
        / "reports"
        / "evaluation"
        / "violent_content"
        / "v2_development"
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "development_sha256": data_hash,
        "records": total,
        "accuracy_percent": pct(accuracy),
        "precision_percent": pct(precision),
        "recall_percent": pct(recall),
        "specificity_percent": pct(specificity),
        "f1_percent": pct(f1),
        "exact_category_action_accuracy_percent": pct(exact_accuracy),
        "false_positives": fp,
        "false_negatives": fn,
        "action_contract_failures": action_failures,
        "groups": group_report,
        "passed_development_gate": passed,
        "is_independent_accuracy": False,
    }
    (report_dir / "report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    (report_dir / "mismatches.json").write_text(
        json.dumps([row for row in rows if not row["correct"]], indent=2),
        encoding="utf-8",
    )

    print("=" * 60)
    print("VIOLENT CONTENT V2 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Records: {total}")
    print(f"Accuracy: {pct(accuracy):.2f}%")
    print(f"Precision: {pct(precision):.2f}%")
    print(f"Recall: {pct(recall):.2f}%")
    print(f"Specificity: {pct(specificity):.2f}%")
    print(f"F1: {pct(f1):.2f}%")
    print(f"Exact category + action accuracy: {pct(exact_accuracy):.2f}%")
    print(f"False positives: {fp}")
    print(f"False negatives: {fn}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Passed development gate: {passed}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for name, stats in group_report.items():
        print(
            f"{name}: {stats['correct']}/{stats['records']} "
            f"({stats['accuracy_percent']:.2f}%)"
        )
    print(f"\nReport: {report_dir / 'report.json'}")
    print(f"Mismatches: {report_dir / 'mismatches.json'}")
    print("This is development data, not independent accuracy.")


if __name__ == "__main__":
    main()
