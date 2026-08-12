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
CANDIDATE_NAME = "religiously-offensive-v3-rc2"
CANDIDATE_DIRECTORY = ROOT / "backend" / "storage" / "candidates" / CANDIDATE_NAME
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
FROZEN_SERVICE_PATH = (
    CANDIDATE_DIRECTORY
    / "source_snapshot"
    / "religiously_offensive_v3_rc2_service.py"
)
V1_DEVELOPMENT = (
    ROOT / "datasets" / "development" / "religiously_offensive_v1" / "development.csv"
)
RC2_DEVELOPMENT = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v3_rc2"
    / "development.csv"
)
RC1_CHALLENGE_SCRIPT = (
    ROOT / "backend" / "scripts" / "evaluate_religiously_offensive_v2_rc1_independent.py"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v3_rc2_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"

RELIGIOUS_CATEGORY = "Religiously Offensive Content"
HATE_CATEGORY = "Hate Speech & Discrimination"
REQUIRED_ACTION = "Remove and send for human review"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_hash(text: str) -> str:
    value = " ".join(str(text).casefold().split())
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required independent-evaluation file is missing: {path}")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load the frozen module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_candidate(manifest: dict[str, Any]) -> None:
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected Religiously Offensive Content candidate.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("The frozen candidate did not pass development.")
    if manifest.get("rc1_holdout_used_for_rc2_training_or_tuning") is not False:
        raise RuntimeError("The failed RC1 challenge was used to tune RC2.")
    if manifest.get("independent_holdout_created_before_freeze") is not False:
        raise RuntimeError("The pre-freeze holdout contract is invalid.")
    if manifest.get("independent_holdout_used_before_freeze") is not False:
        raise RuntimeError("The pre-freeze evaluation contract is invalid.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("The candidate is already marked as independently validated.")
    if manifest.get("connected_to_live_moderation") is not False:
        raise RuntimeError("The candidate must remain disconnected during evaluation.")
    if manifest.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The candidate must remain review-only.")

    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / str(artifact["relative_path"])
        require_file(path)
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen artifact hash mismatch: {path.name}")

    dataset = manifest["development_dataset"]
    require_file(RC2_DEVELOPMENT)
    if sha256_file(RC2_DEVELOPMENT) != str(dataset["sha256"]):
        raise RuntimeError("The RC2 development dataset changed after freeze.")


def csv_text_hashes(path: Path) -> set[str]:
    require_file(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            normalized_hash(row.get("text", ""))
            for row in csv.DictReader(handle)
            if str(row.get("text", "")).strip()
        }


def rc1_challenge_hashes() -> set[str]:
    require_file(RC1_CHALLENGE_SCRIPT)
    module = load_module("prior_rc1_challenge_definition", RC1_CHALLENGE_SCRIPT)
    rows = module.build_fixed_challenge()
    return {normalized_hash(row["text"]) for row in rows}


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected_decision: str,
    religious_violation: bool,
    texts: list[str],
) -> None:
    if len(texts) != 20:
        raise RuntimeError(f"Independent group {group} must contain exactly 20 records.")
    for text in texts:
        rows.append(
            {
                "case_id": f"REL-RC2-HOLDOUT-{len(rows) + 1:03d}",
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
        [
            "A livestream host orders the audience to burn a community's holy text.",
            "The caption encourages viewers to crush the sacred emblem underfoot.",
            "A post celebrates plans to rip apart the religious scripture.",
            "The speaker demands that the sacred statue be smashed in public.",
            "An account calls for vandals to deface the religious symbol.",
            "The message proposes dragging the sacred banner through mud.",
            "A user urges the crowd to dismantle the religious monument.",
            "The recording tells supporters to damage every sacred object they find.",
            "A public comment asks people to shred the holy book during the event.",
            "The channel promotes trampling on the religious flag as an insult.",
            "A poster instructs participants to vandalise the sacred image.",
            "The creator says to cover the religious statue with obscene graffiti.",
            "A message advocates throwing the holy scripture into fire.",
            "The account tells followers to mutilate the ceremonial symbol.",
            "A video description calls for wrecking the sacred monument.",
            "The organizer encourages people to torch the religious books.",
            "A comment demands that the sacred symbols be broken and discarded.",
            "The post calls for desecrating the prayer beads at the ceremony.",
            "The speaker proposes incinerating a consecrated manuscript.",
            "A user urges others to stomp on a devotional icon.",
        ],
    )

    add_group(
        rows,
        "deity_prophet_or_figure_attack",
        "religiously_offensive_review_only",
        True,
        [
            "The account publishes an obscene depiction intended to insult the prophet.",
            "A channel repeatedly mocks a deity to provoke worshippers.",
            "The post urges viewers to ridicule the spiritual leader.",
            "A creator circulates a degrading caricature of the religious figure.",
            "The caption deliberately demeans the revered religious teacher.",
            "The message encourages users to humiliate the sacred figure.",
            "A profile shares an abusive depiction of the religious leader.",
            "The speaker tells the crowd to revile the prophet.",
            "An edited image is posted to degrade the deity.",
            "The page encourages obscene insults against the religious figurehead.",
            "A user publicly derides the spiritual leader as a deliberate provocation.",
            "The clip asks viewers to abuse the sacred leader.",
            "A post invites people to vilify the prophet with degrading images.",
            "The account circulates a morphed image to humiliate the religious leader.",
            "A message tells followers to insult the revered teacher.",
            "The page posts an abusive caricature that mocks the deity.",
            "A creator urges the audience to demean the sacred figure.",
            "The caption calls on users to ridicule the religious figure.",
            "A broadcast invites callers to slander a venerated holy person.",
            "The page asks artists to lampoon a revered faith founder.",
        ],
    )

    add_group(
        rows,
        "place_of_worship_attack",
        "religiously_offensive_review_only",
        True,
        [
            "An organizer tells supporters to demolish the prayer hall.",
            "The post advocates defacing a church during the night.",
            "A message calls for vandals to smash the temple entrance.",
            "The account encourages followers to damage the mosque.",
            "A public page urges people to vandalize the gurudwara.",
            "The recording proposes burning the chapel.",
            "A caption tells viewers to wreck the shrine.",
            "The channel promotes desecrating the monastery.",
            "A message encourages people to tear down the sanctuary.",
            "The speaker calls for dismantling the place of worship.",
            "A post tells supporters to torch the religious building.",
            "The page proposes covering the altar with obscene messages.",
            "A livestream urges the audience to raze the sacred site.",
            "The comment demands that people destroy the prayer space.",
            "An account asks users to break fixtures inside the worship building.",
            "A poster calls for vandalising the gurdwara.",
            "The organizer promotes crushing the shrine's altar.",
            "The message calls on the crowd to scorch the mosque doorway.",
            "A group proposes leveling a consecrated worship centre.",
            "The caption encourages people to profane a devotional sanctuary.",
        ],
    )

    add_group(
        rows,
        "protected_followers_hate_boundary",
        "protected_followers_hate_boundary",
        False,
        [
            "The post says religious followers are inferior and should be excluded.",
            "A message calls followers of the faith parasites.",
            "The account says people of that religion are not human.",
            "A speaker claims religious believers are criminals by nature.",
            "The page says worshippers are inherently dangerous.",
            "A comment demands that the faith community be expelled.",
            "The post tells employers to deny the religious community jobs.",
            "A user calls for the religious group to be kept out of housing.",
            "The message says members of the religion should not exist.",
            "An account urges people to boycott families of that faith.",
            "The post says workers of that faith must be refused employment.",
            "A page calls for students of that faith to be denied education.",
            "The speaker says followers of this faith are less than human.",
            "A public message demands that people of this religion be banned.",
            "The account tells users to attack religious followers.",
            "A comment calls for worshippers to be harmed because of their faith.",
            "The post demands that members of that religion be removed from town.",
            "A page says followers of that faith should be forced to leave.",
            "The message says adherents of the faith should lose their civil rights.",
            "A speaker demands segregation of every member of the sect.",
        ],
    )

    add_group(
        rows,
        "safe_reporting_education_and_criticism",
        "safe_reporting_education_or_criticism",
        False,
        [
            "A news report covers the restoration of a sacred statue after vandalism.",
            "The article reports that police stopped an attempt to burn a holy book.",
            "A documentary examines the historical destruction of a prayer hall.",
            "A historian discusses why a religious monument was damaged centuries ago.",
            "A religious studies class explains the harm caused by mocking a prophet.",
            "A researcher documents attacks that defaced sacred symbols.",
            "A museum exhibit shows a repaired religious emblem.",
            "A teacher explains that students must not desecrate holy scripture.",
            "An educational discussion condemns vandalism against a mosque.",
            "An academic discussion respectfully questions a doctrine.",
            "An interfaith group repaired the damaged shrine.",
            "Community representatives condemned insults directed at a deity.",
            "A safety campaign warns against destroying religious objects.",
            "The prevention campaign asks people not to deface places of worship.",
            "A scholar presents good faith criticism without insulting believers.",
            "The essay offers respectful criticism of a religious teaching.",
            "The archive provides historical context for damage to the temple.",
            "The exhibition explains the cultural context of the sacred image.",
            "A podcast recounts how volunteers repaired scripture damaged in a flood.",
            "A court record describes defendants who vandalized a church.",
        ],
    )

    add_group(
        rows,
        "personal_abuse_boundary",
        "no_religious_boundary_override",
        False,
        [
            "The commenter calls a football player foolish and rude.",
            "A customer insults the shop manager over a refund.",
            "The post mocks an actor's latest performance.",
            "A student ridicules another student's haircut.",
            "The message demeans an employee for arriving late.",
            "A user shares a degrading edit of a former friend.",
            "The caller says the driver is dishonest.",
            "A critic describes the restaurant as disgusting.",
            "The supervisor humiliates a worker after a minor error.",
            "A stranger posts an abusive reply about someone's clothes.",
            "The review derides the hotel's poor service.",
            "A fan vilifies the referee after the game.",
            "The account repeatedly insults a local celebrity.",
            "A classmate circulates a morphed image of another classmate.",
            "The customer calls the delivery agent worthless.",
            "A neighbor mocks another person's singing.",
            "The commenter reviles a corrupt business executive.",
            "A player humiliates an opponent after winning.",
            "The writer ridicules a fictional movie villain.",
            "A user posts an obscene insult about an adult acquaintance.",
        ],
    )

    add_group(
        rows,
        "unrelated_category_isolation",
        "no_religious_boundary_override",
        False,
        [
            "The email asks for an OTP to release a fake reward.",
            "A message publishes a private residential address.",
            "The attachment installs software that steals passwords.",
            "A profile impersonates a tax officer and demands money.",
            "The video depicts a graphic physical assault.",
            "A post advertises an illegal weapon sale.",
            "The account repeatedly threatens a former partner.",
            "An article makes an unsupported claim about a medicine.",
            "The inbox contains hundreds of unsolicited advertisements.",
            "A website distributes a copyrighted film without permission.",
            "The image contains explicit adult nudity.",
            "A message promotes an extremist organization.",
            "The document contains a normal grocery list.",
            "A seller offers stolen banking credentials.",
            "The caller pretends to be customer support and requests a transfer.",
            "A comment exposes another person's telephone number.",
            "The recording contains a direct threat to injure somebody.",
            "A fake account copies a company's brand identity.",
            "The post coordinates online harassment against a classmate.",
            "The calendar invitation schedules a routine project meeting.",
        ],
    )
    return rows


def challenge_sha256(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        "|".join(
            (
                row["case_id"],
                row["group"],
                row["expected_decision"],
                row["text"],
            )
        )
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    if VERDICT_PATH.exists():
        raise FileExistsError(
            "RC2 already has an independent verdict. The challenge will not be rerun."
        )
    for path in (
        MANIFEST_PATH,
        FROZEN_SERVICE_PATH,
        V1_DEVELOPMENT,
        RC2_DEVELOPMENT,
        RC1_CHALLENGE_SCRIPT,
    ):
        require_file(path)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_candidate(manifest)
    gate = manifest["independent_gate_frozen_before_holdout"]
    frozen = load_module("frozen_religiously_offensive_v3_rc2", FROZEN_SERVICE_PATH)
    challenge = build_fixed_challenge()

    challenge_hashes = {normalized_hash(row["text"]) for row in challenge}
    if len(challenge_hashes) != len(challenge):
        raise RuntimeError("The RC2 challenge contains duplicate text.")
    v1_overlap = len(challenge_hashes & csv_text_hashes(V1_DEVELOPMENT))
    rc2_development_overlap = len(challenge_hashes & csv_text_hashes(RC2_DEVELOPMENT))
    rc1_challenge_overlap = len(challenge_hashes & rc1_challenge_hashes())

    results: list[dict[str, Any]] = []
    processing_errors = 0
    for row in challenge:
        try:
            output = frozen.analyze_religiously_offensive_v3_rc2(row["text"])
        except Exception:
            processing_errors += 1
            output = {
                "decision": "processing_error",
                "detected": False,
                "primary_category": "",
                "boundary_category": "",
                "action": "",
                "human_review_required": False,
                "automatic_enforcement_allowed": False,
            }

        detected = bool(output.get("detected", False))
        expected = row["expected_decision"]
        predicted = str(output.get("decision", ""))
        action_failure = bool(
            detected
            and (
                output.get("action") != REQUIRED_ACTION
                or not bool(output.get("human_review_required", False))
                or bool(output.get("automatic_enforcement_allowed", False))
            )
        )
        category_mix_failure = bool(
            (not row["religious_violation"] and output.get("primary_category") == RELIGIOUS_CATEGORY)
            or (
                expected == "protected_followers_hate_boundary"
                and predicted == expected
                and output.get("boundary_category") != HATE_CATEGORY
            )
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

    total = len(results)
    exact_correct = sum(row["correct"] for row in results)
    positives = [row for row in results if row["religious_violation"]]
    negatives = [row for row in results if not row["religious_violation"]]
    tp = sum(row["religious_violation"] and row["detected"] for row in results)
    tn = sum(not row["religious_violation"] and not row["detected"] for row in results)
    fp = sum(not row["religious_violation"] and row["detected"] for row in results)
    fn = sum(row["religious_violation"] and not row["detected"] for row in results)
    accuracy = safe_divide(exact_correct, total)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    boundary_accuracy = safe_divide(sum(row["correct"] for row in negatives), len(negatives))
    action_failures = sum(row["action_contract_failure"] for row in results)
    mix_failures = sum(row["category_mix_failure"] for row in results)

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in results:
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
    zero_development_overlap = v1_overlap == 0 and rc2_development_overlap == 0

    checks = {
        "zero_development_overlap": (
            zero_development_overlap if gate["require_zero_development_overlap"] else True
        ),
        "zero_rc1_challenge_reuse": rc1_challenge_overlap == 0,
        "overall_accuracy": accuracy >= gate["minimum_overall_accuracy"],
        "religious_precision": precision >= gate["minimum_religious_precision"],
        "religious_recall": recall >= gate["minimum_religious_recall"],
        "safe_specificity": specificity >= gate["minimum_safe_specificity"],
        "boundary_accuracy": boundary_accuracy >= gate["minimum_boundary_accuracy"],
        "minimum_group_accuracy": minimum_group_accuracy >= gate["minimum_group_accuracy"],
        "action_contract": action_failures <= gate["maximum_action_contract_failures"],
        "category_mix_contract": mix_failures <= gate["maximum_category_mix_failures"],
        "processing_contract": processing_errors <= gate["maximum_processing_errors"],
    }
    passed = all(checks.values())

    report = {
        "candidate": CANDIDATE_NAME,
        "challenge_version": "2026.08-v3-rc2-synthetic-independent",
        "challenge_sha256": challenge_sha256(challenge),
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": total,
        "v1_development_overlap": v1_overlap,
        "rc2_development_overlap": rc2_development_overlap,
        "rc1_challenge_overlap": rc1_challenge_overlap,
        "exact_accuracy": round(accuracy, 4),
        "religious_precision": round(precision, 4),
        "religious_recall": round(recall, 4),
        "safe_specificity": round(specificity, 4),
        "boundary_accuracy": round(boundary_accuracy, 4),
        "minimum_group_accuracy": minimum_group_accuracy,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "group_results": group_results,
        "action_contract_failures": action_failures,
        "category_mix_failures": mix_failures,
        "processing_errors": processing_errors,
        "independent_gate": gate,
        "gate_checks": checks,
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_challenge_dataset_stored": False,
        "individual_predictions_stored": False,
        "individual_predictions_printed": False,
        "holdout_may_modify_rc2": False,
        "evaluation_limit": "Synthetic challenge evidence; not external or real-world accuracy.",
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

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
        "holdout_may_modify_rc2": False,
        "evidence_type": "synthetic independent challenge",
    }
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print("RELIGIOUSLY OFFENSIVE CONTENT V3 RC2 INDEPENDENT CHALLENGE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Challenge SHA-256: {report['challenge_sha256']}")
    print(f"Records: {total}")
    print(f"V1 development overlap: {v1_overlap}")
    print(f"RC2 development overlap: {rc2_development_overlap}")
    print(f"RC1 challenge overlap: {rc1_challenge_overlap}")
    print(f"Exact accuracy: {accuracy * 100:.2f}%")
    print(f"Religious precision: {precision * 100:.2f}%")
    print(f"Religious recall: {recall * 100:.2f}%")
    print(f"Safe specificity: {specificity * 100:.2f}%")
    print(f"Boundary accuracy: {boundary_accuracy * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
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
    print("No raw challenge dataset or individual predictions were stored or printed.")
    print("This is synthetic evidence, not external or real-world accuracy.")
    print("This holdout may not be used to modify RC2.")


if __name__ == "__main__":
    main()

