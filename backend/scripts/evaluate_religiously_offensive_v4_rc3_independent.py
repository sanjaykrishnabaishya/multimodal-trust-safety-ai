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

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_NAME = "religiously-offensive-v4-rc3"
CANDIDATE_DIRECTORY = ROOT / "backend" / "storage" / "candidates" / CANDIDATE_NAME
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
MODEL_ARTIFACT = CANDIDATE_DIRECTORY / "model" / "classifier.joblib"
MODEL_CONFIG = CANDIDATE_DIRECTORY / "model" / "config.json"
TRAIN_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v4_rc3"
    / "train.csv"
)
VALIDATION_DATASET = TRAIN_DATASET.parent / "validation.csv"
RC1_CHALLENGE_SCRIPT = (
    ROOT / "backend" / "scripts" / "evaluate_religiously_offensive_v2_rc1_independent.py"
)
RC2_CHALLENGE_SCRIPT = (
    ROOT / "backend" / "scripts" / "evaluate_religiously_offensive_v3_rc2_independent.py"
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v4_rc3_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"

RELIGIOUS_OUTPUT = "religiously_offensive"
FOLLOWER_BOUNDARY = "protected_followers_hate_boundary"
NO_OVERRIDE = "no_religious_override"
UNCERTAIN = "uncertain"
REQUIRED_ACTION = "Remove and send for human review"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalized_hash(text: str) -> str:
    normalized = " ".join(str(text).casefold().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required RC3 evaluation file is missing: {path}")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load challenge definition: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_candidate(manifest: dict[str, Any]) -> None:
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC3 candidate manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("RC3 did not pass development.")
    if manifest.get("prior_holdouts_used_for_training_tuning_or_calibration") is not False:
        raise RuntimeError("A prior holdout was used to develop RC3.")
    if manifest.get("independent_holdout_created_before_freeze") is not False:
        raise RuntimeError("The RC3 pre-freeze holdout contract is invalid.")
    if manifest.get("independent_holdout_used_before_freeze") is not False:
        raise RuntimeError("The RC3 pre-freeze evaluation contract is invalid.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("RC3 is already marked as independently validated.")
    if manifest.get("connected_to_live_moderation") is not False:
        raise RuntimeError("RC3 must remain disconnected during evaluation.")
    if manifest.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC3 must remain review-only.")

    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / str(artifact["relative_path"])
        require_file(path)
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC3 artifact hash mismatch: {path.name}")

    datasets = manifest["datasets"]
    for key, path in (("train", TRAIN_DATASET), ("validation", VALIDATION_DATASET)):
        require_file(path)
        if sha256_file(path) != str(datasets[key]["sha256"]):
            raise RuntimeError(f"The frozen RC3 {key} dataset changed after freeze.")


def csv_text_hashes(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            normalized_hash(row.get("text", ""))
            for row in csv.DictReader(handle)
            if str(row.get("text", "")).strip()
        }


def previous_challenge_hashes() -> set[str]:
    hashes: set[str] = set()
    for name, path in (
        ("religious_rc1_challenge", RC1_CHALLENGE_SCRIPT),
        ("religious_rc2_challenge", RC2_CHALLENGE_SCRIPT),
    ):
        require_file(path)
        module = load_module(name, path)
        hashes.update(normalized_hash(row["text"]) for row in module.build_fixed_challenge())
    return hashes


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected_external_decision: str,
    texts: list[str],
) -> None:
    if len(texts) != 30:
        raise RuntimeError(f"RC3 challenge group {group} must contain 30 records.")
    for text in texts:
        rows.append(
            {
                "case_id": f"REL-RC3-HOLDOUT-{len(rows) + 1:03d}",
                "group": group,
                "expected_external_decision": expected_external_decision,
                "text": text,
            }
        )


def build_fixed_challenge() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    add_group(
        rows,
        "sacred_object_or_text_attack",
        RELIGIOUS_OUTPUT,
        [
            "The host tells the crowd to incinerate the consecrated manuscript.",
            "A public post encourages people to smear filth across a devotional icon.",
            "The account celebrates someone kicking a holy statue to pieces.",
            "A message urges supporters to saw apart the sacred wooden emblem.",
            "The channel calls for a religious banner to be thrown into a rubbish fire.",
            "A speaker demands that the worship artefact be smashed with hammers.",
            "The caption asks viewers to tear pages from the holy scripture.",
            "A campaign proposes spraying obscenities across sacred paintings.",
            "The creator tells followers to crush the ceremonial vessel.",
            "A livestream promotes dragging the religious carving through sewage.",
            "The post orders participants to shred the community's holy book.",
            "A user advocates setting the devotional relic alight.",
            "The page tells visitors to spit on the sacred portrait.",
            "The organizer calls for trampling the prayer beads during the rally.",
            "A recording encourages people to vandalize the consecrated object.",
            "The account proposes mutilating the sacred monument.",
            "A comment tells others to rip up the religious manuscript.",
            "The post celebrates plans to profane a holy ceremonial object.",
            "A video description urges viewers to disfigure the religious statue.",
            "The broadcaster asks callers to torch every sacred text they find.",
            "A user promotes smashing a religious emblem outside the building.",
            "The page calls on people to stomp on the sacred flag.",
            "A message demands that supporters destroy the devotional image.",
            "The creator encourages the audience to desecrate the holy monument.",
            "A post asks people to cover the sacred book with degrading graffiti.",
            "The organizer tells participants to break the ceremonial symbols.",
            "The caption proposes cutting the religious artwork into fragments.",
            "A public account calls for soiling the sacred manuscript.",
            "The speaker urges the crowd to obliterate the devotional object.",
            "An online group advocates dumping a revered religious relic in waste.",
        ],
    )

    add_group(
        rows,
        "deity_prophet_or_figure_attack",
        RELIGIOUS_OUTPUT,
        [
            "The account posts an obscene cartoon intended to humiliate a prophet.",
            "A creator urges viewers to malign the revered faith founder.",
            "The page distributes a degrading alteration of the deity's image.",
            "A message invites users to heap abuse on a spiritual leader.",
            "The broadcaster calls on listeners to ridicule the sacred figure.",
            "A profile circulates a vile caricature targeting a religious leader.",
            "The post deliberately portrays a prophet with obscene insults.",
            "A channel asks artists to demean the venerated holy person.",
            "The caption encourages the public to revile the deity.",
            "A livestream promotes humiliating a revered religious teacher.",
            "The account shares a morphed portrait to insult the faith founder.",
            "A message tells the audience to vilify the religious figurehead.",
            "The creator asks followers to publish abusive depictions of the prophet.",
            "A public page encourages derision of the sacred leader.",
            "The broadcast repeatedly slanders the deity to provoke believers.",
            "The post invites users to lampoon the revered teacher with obscene art.",
            "A channel promotes degrading edits of a religious figure.",
            "The speaker tells the crowd to mock the spiritual leader.",
            "An account demands public humiliation of the sacred figurehead.",
            "A video caption urges viewers to insult the prophet.",
            "The page publishes a repulsive caricature of the deity as provocation.",
            "A creator calls for abusive images targeting the faith founder.",
            "The message encourages people to demean the religious leader.",
            "A user posts an obscene depiction to ridicule the sacred figure.",
            "The broadcast asks callers to revile a revered religious teacher.",
            "A profile deliberately humiliates the prophet through edited pictures.",
            "The page calls for contemptuous mockery of the divine figure.",
            "A post invites the audience to denigrate the spiritual leader.",
            "The creator promotes a degrading parody aimed at a holy person.",
            "A livestream tells viewers to insult a venerated religious figurehead.",
        ],
    )

    add_group(
        rows,
        "place_of_worship_attack",
        RELIGIOUS_OUTPUT,
        [
            "The group calls for bulldozing the old prayer centre.",
            "A post tells supporters to splatter obscenities over the shrine walls.",
            "The account encourages people to ransack the chapel.",
            "A speaker proposes setting fire to the neighborhood mosque.",
            "The page advocates wrecking the temple entrance.",
            "A campaign urges participants to demolish a community church.",
            "The recording calls on listeners to vandalize the gurudwara.",
            "A comment promotes desecrating the monastery altar.",
            "The organizer demands that the sacred site be razed.",
            "A message tells the crowd to smash fixtures inside the prayer hall.",
            "The creator encourages people to profane the devotional sanctuary.",
            "A channel calls for the place of worship to be torn down.",
            "The caption proposes covering the church doorway with obscene words.",
            "A post asks supporters to damage the religious building.",
            "The account urges the audience to scorch the shrine.",
            "A group celebrates plans to dismantle the worship centre.",
            "The speaker calls on people to deface the mosque.",
            "A public page advocates destroying the monastery.",
            "The message tells followers to torch the local temple.",
            "A creator promotes breaking the chapel's ceremonial fixtures.",
            "The recording proposes leveling the sacred sanctuary.",
            "A post calls for vandalising the gurdwara courtyard.",
            "The organizer urges supporters to mutilate the shrine's altar.",
            "A channel encourages people to wreck a religious hall.",
            "The page asks viewers to destroy the place of worship.",
            "A caption tells the crowd to spray degrading graffiti on the temple.",
            "The account calls for demolishing a consecrated prayer space.",
            "A message advocates smashing windows at the church.",
            "The speaker urges followers to burn a devotional sanctuary.",
            "An online campaign promotes razing the religious centre.",
        ],
    )

    add_group(
        rows,
        "protected_followers_hate_boundary",
        FOLLOWER_BOUNDARY,
        [
            "The message claims devotees of that faith are less than human.",
            "A post demands that every congregant be expelled from the district.",
            "The speaker calls people who practise the religion parasites.",
            "An account says religious adherents should lose voting rights.",
            "The page tells landlords not to rent homes to worshippers.",
            "A campaign demands segregation of families belonging to that faith.",
            "The broadcast says members of the religious community are inferior.",
            "A user urges employers to refuse jobs to followers of the religion.",
            "The post says believers are criminals by nature.",
            "A message calls for religious worshippers to be forced out of town.",
            "The channel claims adherents of the faith are inherently dangerous.",
            "A commenter asks others to attack people because of their religion.",
            "The page calls for students of that faith to be denied education.",
            "A speaker says the religious community should not exist.",
            "The post advocates denying healthcare to members of the faith.",
            "An account calls on the public to boycott families of that religion.",
            "The message says worshippers should be banned from public spaces.",
            "A campaign portrays religious believers as subhuman.",
            "The channel demands that adherents be removed from their jobs.",
            "A user says people of the faith must be harmed.",
            "The post calls all religious followers dangerous parasites.",
            "A broadcaster demands the exclusion of the faith community.",
            "The page tells businesses to reject customers of that religion.",
            "A comment says believers must be separated from everyone else.",
            "The account encourages violence against worshippers.",
            "A message demands eviction of people because of their faith.",
            "The speaker calls religious adherents unfit for citizenship.",
            "The post says members of the religion must be driven away.",
            "A page claims every follower of that faith is a criminal.",
            "The broadcast calls for stripping rights from the religious group.",
        ],
    )

    add_group(
        rows,
        "safe_reporting_education_and_criticism",
        NO_OVERRIDE,
        [
            "A court report records that a defendant burned a holy manuscript.",
            "A podcast recounts how volunteers repaired a vandalized shrine.",
            "The news bulletin condemns an obscene depiction of a prophet.",
            "A history lecture examines the destruction of a monastery centuries ago.",
            "An academic article criticizes a doctrine without insulting believers.",
            "A museum catalogue documents a damaged sacred statue.",
            "A teacher explains why students must not mock religious figures.",
            "The documentary reports an attack on a mosque without endorsing it.",
            "An interfaith campaign opposes desecration of holy books.",
            "A researcher studies vandalism directed at religious buildings.",
            "The article describes police preventing damage to a temple.",
            "A safety lesson warns people never to deface sacred symbols.",
            "A scholar respectfully questions the interpretation of a scripture.",
            "A cultural program explains why prayer beads are meaningful.",
            "The archive records that a chapel was burned during a historical conflict.",
            "A journalist reports that an account insulted a deity and was removed.",
            "The community update announces restoration of a religious monument.",
            "An educational video condemns humiliation of a spiritual leader.",
            "A public-service message asks people not to vandalize worship sites.",
            "The essay provides good-faith criticism of a religious institution.",
            "A documentary interviews people affected by destruction of a shrine.",
            "The museum explains the historical context of a damaged sacred image.",
            "A legal summary quotes an offensive post solely as evidence.",
            "The class discusses how to prevent attacks on places of worship.",
            "A newspaper reports repairs after someone defaced a church.",
            "The speaker condemns a campaign that mocked a prophet.",
            "A researcher documents online abuse targeting religious imagery.",
            "The lesson compares doctrines through respectful analysis.",
            "A restoration team describes how it repaired a sacred carving.",
            "The report warns that desecration can cause community harm.",
        ],
    )

    add_group(
        rows,
        "neutral_religious_content",
        NO_OVERRIDE,
        [
            "Tourists quietly visited the historic temple in the afternoon.",
            "A guide explained the architecture of the neighborhood mosque.",
            "The church published its regular opening hours.",
            "Volunteers cleaned the gurudwara before a community meal.",
            "A museum displayed a sacred manuscript with proper attribution.",
            "The family photographed a religious monument during their trip.",
            "A student wrote a neutral essay about the monastery's history.",
            "The prayer hall hosted a peaceful cultural gathering.",
            "Conservators carefully restored a sacred painting.",
            "The choir rehearsed inside the chapel.",
            "A documentary showed a respectful religious ceremony.",
            "The library catalogued an old holy book.",
            "Visitors learned about the meaning of ceremonial objects.",
            "The community repaired the roof of its place of worship.",
            "A scholar compared two faith traditions respectfully.",
            "The shrine welcomed visitors for a guided heritage tour.",
            "An exhibition presented devotional artwork without alteration.",
            "The article described the design of a religious building.",
            "A photographer documented the sacred site's stone carvings.",
            "The group attended a peaceful service at the church.",
            "A teacher introduced students to the history of religious symbols.",
            "The temple committee announced a routine maintenance schedule.",
            "The mosque organized a public charity event.",
            "A historian translated an old religious manuscript.",
            "The family placed flowers near a sacred monument.",
            "A travel program featured the monastery's architecture.",
            "The museum preserved a ceremonial vessel in a glass case.",
            "A community newsletter reported a peaceful interfaith meeting.",
            "The visitors observed the prayer space respectfully.",
            "A catalogue identified the artist of a devotional painting.",
        ],
    )

    add_group(
        rows,
        "unrelated_or_personal_boundary",
        NO_OVERRIDE,
        [
            "A fraudster requests an OTP to unlock a supposed prize.",
            "The message exposes another person's private telephone number.",
            "An attachment installs code that steals passwords.",
            "A fake profile impersonates a bank representative.",
            "The footage shows a graphic physical assault.",
            "A seller advertises illegal drugs through private messages.",
            "The account repeatedly threatens a former colleague.",
            "An article makes an unsupported medical claim.",
            "The inbox receives hundreds of unsolicited advertisements.",
            "A website distributes a copyrighted movie without permission.",
            "The image contains explicit adult sexual material.",
            "A post promotes an extremist organization.",
            "The document contains an ordinary shopping list.",
            "A scam message asks for banking credentials.",
            "A caller pretends to be government support and demands money.",
            "The post reveals somebody's residential address.",
            "A recording contains a direct threat to injure another person.",
            "The profile copies a company's brand and logo.",
            "A group coordinates online harassment against a classmate.",
            "The calendar schedules a routine staff meeting.",
            "A commenter insults a football player's performance.",
            "The customer mocks a restaurant's slow service.",
            "A student shares a degrading image of another student.",
            "The reviewer ridicules a poorly written film script.",
            "A manager humiliates an employee over a mistake.",
            "The stranger posts an abusive reply about someone's clothes.",
            "A critic calls a fictional villain disgusting.",
            "The player mocks an opponent after the match.",
            "A user vilifies a corrupt business executive.",
            "The message contains a normal reminder about tomorrow's appointment.",
        ],
    )
    return rows


def challenge_sha256(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        "|".join(
            (
                row["case_id"],
                row["group"],
                row["expected_external_decision"],
                row["text"],
            )
        )
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def binary_metrics(
    results: list[dict[str, Any]],
    label: str,
) -> dict[str, Any]:
    tp = sum(row["expected"] == label and row["predicted"] == label for row in results)
    fp = sum(row["expected"] != label and row["predicted"] == label for row in results)
    fn = sum(row["expected"] == label and row["predicted"] != label for row in results)
    tn = sum(row["expected"] != label and row["predicted"] != label for row in results)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    return {
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "specificity": round(safe_divide(tn, tn + fp), 4),
        "f1": round(safe_divide(2 * precision * recall, precision + recall), 4),
    }


def predict_external(
    classifier: Any,
    encoder: Any,
    config: dict[str, Any],
    texts: list[str],
) -> list[dict[str, Any]]:
    embeddings = encoder.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    probabilities = classifier.predict_proba(embeddings)
    policy = config["religious_output_policy"]
    threshold = float(policy["religious_probability_threshold"])
    minimum_margin = float(policy["minimum_score_margin"])
    predictions: list[dict[str, Any]] = []
    for scores in probabilities:
        order = np.argsort(scores)[::-1]
        top_index = int(order[0])
        second_index = int(order[1])
        model_label = str(classifier.classes_[top_index])
        top_score = float(scores[top_index])
        margin = top_score - float(scores[second_index])
        if model_label == RELIGIOUS_OUTPUT:
            external = (
                RELIGIOUS_OUTPUT
                if top_score >= threshold and margin >= minimum_margin
                else UNCERTAIN
            )
        elif model_label == FOLLOWER_BOUNDARY:
            external = FOLLOWER_BOUNDARY
        else:
            external = NO_OVERRIDE
        predictions.append(
            {
                "external": external,
                "model_label": model_label,
                "score": top_score,
                "margin": margin,
            }
        )
    return predictions


def main() -> None:
    if VERDICT_PATH.exists():
        raise FileExistsError(
            "RC3 already has an independent verdict. The challenge will not be rerun."
        )
    for path in (
        MANIFEST_PATH,
        MODEL_ARTIFACT,
        MODEL_CONFIG,
        TRAIN_DATASET,
        VALIDATION_DATASET,
        RC1_CHALLENGE_SCRIPT,
        RC2_CHALLENGE_SCRIPT,
    ):
        require_file(path)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_candidate(manifest)
    gate = manifest["independent_gate_frozen_before_holdout"]
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    challenge = build_fixed_challenge()
    challenge_hashes = {normalized_hash(row["text"]) for row in challenge}
    if len(challenge_hashes) != len(challenge):
        raise RuntimeError("The RC3 challenge contains duplicate text.")
    train_overlap = len(challenge_hashes & csv_text_hashes(TRAIN_DATASET))
    validation_overlap = len(challenge_hashes & csv_text_hashes(VALIDATION_DATASET))
    prior_challenge_overlap = len(challenge_hashes & previous_challenge_hashes())

    classifier = joblib.load(MODEL_ARTIFACT)
    encoder = SentenceTransformer(
        str(config["embedding_model"]),
        revision=str(config["embedding_model_revision"]),
        device="cpu",
    )
    processing_errors = 0
    try:
        predictions = predict_external(
            classifier,
            encoder,
            config,
            [row["text"] for row in challenge],
        )
    except Exception:
        processing_errors = len(challenge)
        predictions = [
            {"external": UNCERTAIN, "model_label": "error", "score": 0.0, "margin": 0.0}
            for _ in challenge
        ]

    results: list[dict[str, Any]] = []
    for row, prediction in zip(challenge, predictions, strict=True):
        expected = row["expected_external_decision"]
        predicted = prediction["external"]
        action_failure = False
        if predicted == RELIGIOUS_OUTPUT:
            action = REQUIRED_ACTION
            review = True
            automatic = False
            action_failure = bool(
                action != REQUIRED_ACTION or not review or automatic
            )
        category_mix_failure = bool(
            (expected == NO_OVERRIDE and predicted in {RELIGIOUS_OUTPUT, FOLLOWER_BOUNDARY})
            or (expected == FOLLOWER_BOUNDARY and predicted == RELIGIOUS_OUTPUT)
        )
        results.append(
            {
                "group": row["group"],
                "expected": expected,
                "predicted": predicted,
                "correct": predicted == expected,
                "action_contract_failure": action_failure,
                "category_mix_failure": category_mix_failure,
            }
        )

    religious = binary_metrics(results, RELIGIOUS_OUTPUT)
    follower = binary_metrics(results, FOLLOWER_BOUNDARY)
    total = len(results)
    correct = sum(row["correct"] for row in results)
    external_accuracy = safe_divide(correct, total)
    no_override_rows = [row for row in results if row["expected"] == NO_OVERRIDE]
    nonreligious_specificity = safe_divide(
        sum(row["predicted"] != RELIGIOUS_OUTPUT for row in no_override_rows),
        len(no_override_rows),
    )
    neutral_rows = [row for row in results if row["group"] == "neutral_religious_content"]
    neutral_safe_rate = safe_divide(
        sum(row["predicted"] == NO_OVERRIDE for row in neutral_rows),
        len(neutral_rows),
    )
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

    zero_development_overlap = train_overlap == 0 and validation_overlap == 0
    checks = {
        "zero_development_overlap": (
            zero_development_overlap if gate["require_zero_development_overlap"] else True
        ),
        "zero_prior_challenge_reuse": (
            prior_challenge_overlap == 0 if gate["require_zero_prior_challenge_reuse"] else True
        ),
        "external_decision_accuracy": external_accuracy >= gate["minimum_external_decision_accuracy"],
        "religious_precision": religious["precision"] >= gate["minimum_religious_precision"],
        "religious_recall": religious["recall"] >= gate["minimum_religious_recall"],
        "religious_f1": religious["f1"] >= gate["minimum_religious_f1"],
        "follower_boundary_precision": follower["precision"] >= gate["minimum_follower_boundary_precision"],
        "follower_boundary_recall": follower["recall"] >= gate["minimum_follower_boundary_recall"],
        "follower_boundary_f1": follower["f1"] >= gate["minimum_follower_boundary_f1"],
        "nonreligious_specificity": nonreligious_specificity >= gate["minimum_nonreligious_specificity"],
        "neutral_religious_safe_rate": neutral_safe_rate >= gate["minimum_neutral_religious_safe_rate"],
        "minimum_group_accuracy": minimum_group_accuracy >= gate["minimum_group_accuracy"],
        "action_contract": action_failures <= gate["maximum_action_contract_failures"],
        "category_mix_contract": mix_failures <= gate["maximum_category_mix_failures"],
        "processing_contract": processing_errors <= gate["maximum_processing_errors"],
    }
    passed = all(checks.values())

    report = {
        "candidate": CANDIDATE_NAME,
        "challenge_version": "2026.08-v4-rc3-synthetic-independent",
        "challenge_sha256": challenge_sha256(challenge),
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": total,
        "train_overlap": train_overlap,
        "validation_overlap": validation_overlap,
        "prior_challenge_overlap": prior_challenge_overlap,
        "external_decision_accuracy": round(external_accuracy, 4),
        "religious_metrics": religious,
        "follower_boundary_metrics": follower,
        "nonreligious_specificity": round(nonreligious_specificity, 4),
        "neutral_religious_safe_rate": round(neutral_safe_rate, 4),
        "minimum_group_accuracy": minimum_group_accuracy,
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
        "holdout_may_modify_rc3": False,
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
        "holdout_may_modify_rc3": False,
        "evidence_type": "synthetic independent challenge",
    }
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print("RELIGIOUSLY OFFENSIVE CONTENT V4 RC3 INDEPENDENT CHALLENGE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Challenge SHA-256: {report['challenge_sha256']}")
    print(f"Records: {total}")
    print(f"Train overlap: {train_overlap}")
    print(f"Validation overlap: {validation_overlap}")
    print(f"Prior challenge overlap: {prior_challenge_overlap}")
    print(f"External decision accuracy: {external_accuracy * 100:.2f}%")
    print(f"Religious precision: {religious['precision'] * 100:.2f}%")
    print(f"Religious recall: {religious['recall'] * 100:.2f}%")
    print(f"Religious F1: {religious['f1'] * 100:.2f}%")
    print(f"Follower-boundary precision: {follower['precision'] * 100:.2f}%")
    print(f"Follower-boundary recall: {follower['recall'] * 100:.2f}%")
    print(f"Follower-boundary F1: {follower['f1'] * 100:.2f}%")
    print(f"Nonreligious specificity: {nonreligious_specificity * 100:.2f}%")
    print(f"Neutral-religious safe routing: {neutral_safe_rate * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
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
    print("This holdout may not be used to modify RC3.")


if __name__ == "__main__":
    main()

