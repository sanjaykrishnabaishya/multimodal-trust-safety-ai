from __future__ import annotations

import csv
import hashlib
import importlib.util
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from types import ModuleType
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v2-rc1"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
FROZEN_SERVICE_PATH = (
    CANDIDATE_DIRECTORY
    / "source_snapshot"
    / "religiously_offensive_v2_service.py"
)
DEVELOPMENT_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v1"
    / "development.csv"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v2_rc1_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"

CANDIDATE_NAME = "religiously-offensive-v2-rc1"
RELIGIOUS_CATEGORY = "Religiously Offensive Content"
HATE_CATEGORY = "Hate Speech & Discrimination"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_hash(text: str) -> str:
    normalized = " ".join(str(text).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def challenge_hash(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        "|".join(
            (
                str(row["case_id"]),
                str(row["group"]),
                str(row["expected_decision"]),
                str(row["text"]),
            )
        )
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required independent-evaluation file is missing: {path}")


def verify_candidate(manifest: dict[str, Any]) -> None:
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected Religiously Offensive Content candidate.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("The frozen candidate did not pass development.")
    if manifest.get("independent_holdout_created_before_freeze") is not False:
        raise RuntimeError("The pre-freeze holdout contract is invalid.")
    if manifest.get("independent_holdout_used_before_freeze") is not False:
        raise RuntimeError("The pre-freeze evaluation contract is invalid.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("The manifest incorrectly marks this candidate as validated.")
    if manifest.get("connected_to_live_moderation") is not False:
        raise RuntimeError("The candidate must remain disconnected during evaluation.")
    if manifest.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The candidate must remain review-only.")

    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / Path(str(artifact["relative_path"]))
        require_file(path)
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen artifact hash mismatch: {path.name}")

    dataset = manifest["development_dataset"]
    require_file(DEVELOPMENT_DATASET)
    if sha256_file(DEVELOPMENT_DATASET) != str(dataset["sha256"]):
        raise RuntimeError("The development dataset changed after freeze.")


def load_frozen_service() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "frozen_religiously_offensive_v2_rc1",
        FROZEN_SERVICE_PATH,
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Could not load the frozen V2 service snapshot.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected_decision: str,
    religious_violation: bool,
    texts: tuple[str, ...],
) -> None:
    start = len(rows) + 1
    for offset, text in enumerate(texts):
        rows.append(
            {
                "case_id": f"REL-RC1-{start + offset:03d}",
                "group": group,
                "expected_decision": expected_decision,
                "religious_violation": religious_violation,
                "text": text,
            }
        )


def build_fixed_challenge() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    add_group(
        rows,
        "sacred_object_or_text_attack",
        "religiously_offensive_review_only",
        True,
        (
            "Shred the holy scripture and dump the fragments at the gate.",
            "Torch the sacred book to show contempt for the faith.",
            "Vandalize the religious emblem during the public ceremony.",
            "Smash their sacred statue and upload the destruction.",
            "Deface the holy text with obscene drawings.",
            "Break the ceremonial symbol used for worship.",
            "Trample on the sacred flag to insult the religion.",
            "Rip up the religious scripture in front of worshippers.",
            "Burn the community's holy book as a deliberate provocation.",
            "Spit on the sacred image and celebrate the desecration.",
            "Crush the prayer beads because they represent the faith.",
            "Mutilate the religious statue to offend the believers.",
            "Set fire to the sacred text outside the gathering.",
            "Cut apart the holy emblem displayed for worship.",
            "Destroy the ceremonial object because it is sacred.",
            "Scrawl degrading abuse across the religious symbol.",
            "Throw the scripture into flames to humiliate the faith.",
            "Wreck the sacred monument and mock what it represents.",
            "Damage the holy image used in the religious ceremony.",
            "Dismantle the sacred statue as an attack on the religion.",
        ),
    )
    add_group(
        rows,
        "deity_prophet_or_figure_attack",
        "religiously_offensive_review_only",
        True,
        (
            "Vilify their prophet with deliberately obscene insults.",
            "Call the worshipped deity filthy and repulsive.",
            "Create a degrading caricature of their god to offend the faith.",
            "Ridicule the sacred figurehead with humiliating language.",
            "Publish an abusive image that mocks their prophet.",
            "Describe the religious deity as disgusting and worthless.",
            "Use obscene abuse against the revered spiritual leader.",
            "Deride their god in a post intended to insult the religion.",
            "Morph an image of the prophet into a degrading depiction.",
            "Humiliate the sacred reincarnation with abusive language.",
            "Insult their deity to provoke members of the faith.",
            "Post repulsive slurs about the religion's figurehead.",
            "Demean the revered religious teacher with obscene words.",
            "Mock their prophet through a deliberately abusive edit.",
            "Call the sacred leader worthless to attack the faith.",
            "Abuse their god with a degrading public message.",
            "Revile the religious figure in language intended to offend.",
            "Publish a humiliating depiction of the worshipped deity.",
            "Ridicule the prophet with a filthy insult.",
            "Degrade their spiritual leader specifically because the figure is sacred.",
        ),
    )
    add_group(
        rows,
        "place_of_worship_attack",
        "religiously_offensive_review_only",
        True,
        (
            "Raze the shrine because it represents that faith.",
            "Vandalize the mosque with degrading religious messages.",
            "Smash the altar to insult the worship practiced there.",
            "Deface the church with obscene attacks on its deity.",
            "Demolish the temple as a deliberate insult to the religion.",
            "Burn the chapel to desecrate the place of worship.",
            "Damage the gurudwara because it is sacred to the community.",
            "Wreck the prayer hall and celebrate the religious insult.",
            "Mutilate the sacred carvings inside the monastery.",
            "Break the shrine's holy fixtures to offend the faith.",
            "Paint abusive religious insults across the sanctuary.",
            "Destroy the sacred objects inside the mosque.",
            "Tear down the religious flag above the temple.",
            "Desecrate the prayer space with obscene material.",
            "Deface the monastery's sacred statue as an insult.",
            "Dismantle the chapel's altar to mock the religion.",
            "Crush the religious emblem mounted in the worship building.",
            "Set fire to the shrine as an attack on the faith.",
            "Vandalise the sacred site to humiliate its religion.",
            "Damage the church's sacred fixtures because they represent worship.",
        ),
    )
    add_group(
        rows,
        "religious_followers_hate_boundary",
        "protected_followers_hate_boundary",
        False,
        (
            "Expel every follower of this religion from the country.",
            "Members of that faith are inferior and deserve exclusion.",
            "Refuse housing to people because of their religion.",
            "Every believer in that religious group is a criminal.",
            "Those worshippers are parasites who should be removed.",
            "Deny employment to this religious community.",
            "People from that faith are less than human.",
            "Block followers of this religion from attending school.",
            "Attack the protected group because of its religious identity.",
            "That religious community should not exist here.",
            "Terminate workers merely for belonging to this faith.",
            "Exclude all believers of that religion from public services.",
            "Do not rent homes to members of this religious group.",
            "Every follower of this faith should be forced to leave.",
            "Religious minorities like this are inherently dangerous.",
            "Discriminate against those people because they worship differently.",
            "Harm the group solely because of their religion.",
            "These religious followers are not human.",
            "Boycott every person who belongs to that faith.",
            "Remove this community because its members follow that religion.",
        ),
    )
    add_group(
        rows,
        "reporting_education_and_criticism",
        "safe_reporting_education_or_criticism",
        False,
        (
            "A news report documents damage to a historic place of worship.",
            "The lesson explains why insulting a prophet can cause harm.",
            "This religious studies paper compares sacred texts respectfully.",
            "The interfaith workshop condemns attacks on holy sites.",
            "A historian discusses the restoration of a damaged shrine.",
            "The article reports that vandals defaced a religious emblem.",
            "The museum restored the sacred statue after it was damaged.",
            "This is good-faith criticism of a religious institution's finances.",
            "The speaker condemns obscene abuse directed at deities.",
            "A public service announcement opposes desecration of scriptures.",
            "Researchers study protection methods for religious monuments.",
            "The documentary examines sacred art in historical context.",
            "The teacher asks students not to damage religious symbols.",
            "The essay respectfully questions a doctrine without insulting believers.",
            "An interfaith group repairs a vandalized prayer hall.",
            "The report quotes a degrading statement as evidence of abuse.",
            "The safety campaign tells people never to burn holy books.",
            "The class explores the cultural meaning of a sacred emblem.",
            "The documentary reports destruction without praising it.",
            "The organization condemns religious hatred and vandalism.",
        ),
    )
    add_group(
        rows,
        "unrelated_or_personal_boundary",
        "no_religious_boundary_override",
        False,
        (
            "You are a pathetic idiot.",
            "That coworker is a worthless loser.",
            "Congratulations, send your OTP to claim the prize.",
            "Transfer the processing fee to unlock your cash reward.",
            "I will stab you when you arrive.",
            "The footage depicts graphic bodily harm.",
            "His private email address is person@example.com.",
            "This article discusses a disputed tax proposal.",
            "The Eiffel Tower is located in Paris.",
            "You are an ugly and useless person.",
            "Send your password now to verify the account.",
            "I am going to physically hurt you tonight.",
            "The message calls one individual a stupid bastard.",
            "A bank notice explains how to avoid phishing attempts.",
            "The report describes a non-religious historical monument.",
            "A student submits an ordinary science assignment.",
            "The user uploads a family photograph from a holiday.",
            "A recipe explains how to prepare vegetable soup.",
            "The comment criticizes a company product without abuse.",
            "A weather bulletin predicts rain tomorrow.",
        ),
    )
    return rows


def development_text_hashes() -> set[str]:
    hashes: set[str] = set()
    with DEVELOPMENT_DATASET.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            text = str(row.get("text", "")).strip()
            if text:
                hashes.add(normalized_hash(text))
    return hashes


def binary_metrics(results: list[dict[str, Any]]) -> dict[str, Any]:
    true_positives = sum(
        row["religious_violation"] and row["detected"] for row in results
    )
    true_negatives = sum(
        not row["religious_violation"] and not row["detected"] for row in results
    )
    false_positives = sum(
        not row["religious_violation"] and row["detected"] for row in results
    )
    false_negatives = sum(
        row["religious_violation"] and not row["detected"] for row in results
    )
    total = len(results)
    precision = true_positives / (true_positives + false_positives) if (
        true_positives + false_positives
    ) else 0.0
    recall = true_positives / (true_positives + false_negatives) if (
        true_positives + false_negatives
    ) else 0.0
    specificity = true_negatives / (true_negatives + false_positives) if (
        true_negatives + false_positives
    ) else 0.0
    return {
        "accuracy": round((true_positives + true_negatives) / total, 4),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(specificity, 4),
        "true_positives": true_positives,
        "true_negatives": true_negatives,
        "false_positives": false_positives,
        "false_negatives": false_negatives,
    }


def main() -> None:
    if VERDICT_PATH.exists():
        raise FileExistsError(
            "This RC1 already has an independent verdict. The challenge will not be rerun."
        )
    for path in (MANIFEST_PATH, FROZEN_SERVICE_PATH, DEVELOPMENT_DATASET):
        require_file(path)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_candidate(manifest)
    gate = manifest["independent_gate_frozen_before_holdout"]
    frozen_service = load_frozen_service()
    challenge = build_fixed_challenge()
    dev_hashes = development_text_hashes()
    overlap_count = sum(normalized_hash(row["text"]) in dev_hashes for row in challenge)

    results: list[dict[str, Any]] = []
    processing_errors = 0
    for row in challenge:
        try:
            analysis = frozen_service.analyze_religiously_offensive_v2(row["text"])
        except Exception:
            processing_errors += 1
            analysis = {
                "decision": "processing_error",
                "detected": False,
                "primary_category": "",
                "action": "",
                "human_review_required": False,
                "automatic_enforcement_allowed": False,
            }
        detected = bool(analysis.get("detected", False))
        expected = str(row["expected_decision"])
        predicted = str(analysis.get("decision", ""))
        action_failure = bool(
            detected
            and (
                analysis.get("action") != "Remove and send for human review"
                or not bool(analysis.get("human_review_required", False))
                or bool(analysis.get("automatic_enforcement_allowed", False))
            )
        )
        category_mix_failure = bool(
            not row["religious_violation"]
            and analysis.get("primary_category") == RELIGIOUS_CATEGORY
        )
        results.append(
            {
                "group": row["group"],
                "religious_violation": row["religious_violation"],
                "detected": detected,
                "correct": predicted == expected,
                "action_contract_failure": action_failure,
                "category_mix_failure": category_mix_failure,
            }
        )

    metrics = binary_metrics(results)
    exact_correct = sum(row["correct"] for row in results)
    exact_accuracy = exact_correct / len(results)
    boundary_rows = [row for row in results if not row["religious_violation"]]
    boundary_accuracy = sum(row["correct"] for row in boundary_rows) / len(boundary_rows)
    action_failures = sum(row["action_contract_failure"] for row in results)
    category_mix_failures = sum(row["category_mix_failure"] for row in results)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
        grouped[str(row["group"])].append(row)
    group_results = {
        group: {
            "records": len(group_rows),
            "correct": sum(row["correct"] for row in group_rows),
            "accuracy": round(
                sum(row["correct"] for row in group_rows) / len(group_rows), 4
            ),
        }
        for group, group_rows in sorted(grouped.items())
    }
    minimum_group_accuracy = min(
        float(result["accuracy"]) for result in group_results.values()
    )
    checks = {
        "no_development_overlap": overlap_count == 0,
        "overall_accuracy": exact_accuracy >= gate["minimum_overall_accuracy"],
        "religious_precision": metrics["precision"] >= gate["minimum_religious_precision"],
        "religious_recall": metrics["recall"] >= gate["minimum_religious_recall"],
        "safe_specificity": metrics["specificity"] >= gate["minimum_safe_specificity"],
        "boundary_accuracy": boundary_accuracy >= gate["minimum_boundary_accuracy"],
        "minimum_group_accuracy": minimum_group_accuracy >= gate["minimum_group_accuracy"],
        "action_contract": action_failures <= gate["maximum_action_contract_failures"],
        "category_mix_contract": category_mix_failures <= gate["maximum_category_mix_failures"],
        "processing_contract": processing_errors <= gate["maximum_processing_errors"],
    }
    passed = all(checks.values())

    report = {
        "candidate": CANDIDATE_NAME,
        "challenge_version": "2026.08-v2-rc1-synthetic-independent",
        "challenge_sha256": challenge_hash(challenge),
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(results),
        "development_overlap": overlap_count,
        "exact_accuracy": round(exact_accuracy, 4),
        "binary_metrics": metrics,
        "boundary_accuracy": round(boundary_accuracy, 4),
        "minimum_group_accuracy": round(minimum_group_accuracy, 4),
        "group_results": group_results,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "processing_errors": processing_errors,
        "independent_gate": gate,
        "gate_checks": checks,
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_challenge_text_stored": False,
        "individual_predictions_stored": False,
        "individual_predictions_printed": False,
        "holdout_may_modify_rc1": False,
        "evaluation_limit": (
            "This is a fixed synthetic independent challenge, not external or "
            "real-world accuracy evidence."
        ),
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    verdict = {
        "candidate": CANDIDATE_NAME,
        "status": (
            "Passed synthetic independent readiness gate"
            if passed
            else "Failed synthetic independent readiness gate"
        ),
        "evaluated_at_utc": report["evaluated_at_utc"],
        "challenge_sha256": report["challenge_sha256"],
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "aggregate_report": str(REPORT_PATH),
        "frozen_artifacts_modified": False,
        "holdout_may_modify_rc1": False,
        "evidence_type": "synthetic independent challenge",
    }
    VERDICT_PATH.write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("RELIGIOUSLY OFFENSIVE CONTENT V2 RC1 INDEPENDENT CHALLENGE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Challenge SHA-256: {report['challenge_sha256']}")
    print(f"Records: {len(results)}")
    print(f"Development overlap: {overlap_count}")
    print(f"Exact accuracy: {exact_accuracy * 100:.2f}%")
    print(f"Religious precision: {metrics['precision'] * 100:.2f}%")
    print(f"Religious recall: {metrics['recall'] * 100:.2f}%")
    print(f"Safe specificity: {metrics['specificity'] * 100:.2f}%")
    print(f"Boundary accuracy: {boundary_accuracy * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"False positives: {metrics['false_positives']}")
    print(f"False negatives: {metrics['false_negatives']}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Processing errors: {processing_errors}")
    print()
    print("GROUP RESULTS")
    print("-" * 60)
    for group, result in group_results.items():
        print(f"{group}: {result['correct']}/{result['records']}")
    print()
    print("INDEPENDENT GATE CHECKS")
    print("-" * 60)
    for name, value in checks.items():
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
    print("This holdout may not be used to modify RC1.")


if __name__ == "__main__":
    main()
