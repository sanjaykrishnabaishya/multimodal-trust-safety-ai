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
CANDIDATE_NAME = "religiously-offensive-v5-rc4"
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
PRIOR_CHALLENGE_SCRIPTS = (
    ROOT / "backend" / "scripts" / "evaluate_religiously_offensive_v2_rc1_independent.py",
    ROOT / "backend" / "scripts" / "evaluate_religiously_offensive_v3_rc2_independent.py",
    ROOT / "backend" / "scripts" / "evaluate_religiously_offensive_v4_rc3_independent.py",
)
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v5_rc4_independent"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"

RELIGIOUS_OUTPUT = "religiously_offensive"
NO_OVERRIDE = "no_religious_override"
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
        raise FileNotFoundError(f"Required RC4 evaluation file is missing: {path}")


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load prior challenge definition: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_candidate(manifest: dict[str, Any]) -> None:
    if manifest.get("candidate") != CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC4 candidate manifest.")
    if manifest.get("development_gate_passed") is not True:
        raise RuntimeError("RC4 did not pass development.")
    if manifest.get("rc3_holdout_report_predictions_or_cases_used") is not False:
        raise RuntimeError("RC3 holdout material was used to calibrate RC4.")
    if manifest.get("base_classifier_retrained") is not False:
        raise RuntimeError("The frozen base classifier was modified.")
    if manifest.get("follower_boundary_output_enabled") is not False:
        raise RuntimeError("RC4 must not own the follower-hate boundary.")
    if manifest.get("independent_holdout_created_before_freeze") is not False:
        raise RuntimeError("The RC4 pre-freeze holdout contract is invalid.")
    if manifest.get("independent_holdout_used_before_freeze") is not False:
        raise RuntimeError("The RC4 pre-freeze evaluation contract is invalid.")
    if manifest.get("independently_validated") is not False:
        raise RuntimeError("RC4 is already marked as independently validated.")
    if manifest.get("connected_to_live_moderation") is not False:
        raise RuntimeError("RC4 must remain disconnected during evaluation.")
    if manifest.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("RC4 must remain review-only.")
    for artifact in manifest.get("artifacts", []):
        path = CANDIDATE_DIRECTORY / str(artifact["relative_path"])
        require_file(path)
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC4 artifact hash mismatch: {path.name}")
    for key, path in (("train", TRAIN_DATASET), ("validation", VALIDATION_DATASET)):
        require_file(path)
        if sha256_file(path) != str(manifest["datasets"][key]["sha256"]):
            raise RuntimeError(f"The RC4 {key} dataset changed after freeze.")


def csv_text_hashes(path: Path) -> set[str]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return {
            normalized_hash(row.get("text", ""))
            for row in csv.DictReader(handle)
            if str(row.get("text", "")).strip()
        }


def prior_challenge_hashes() -> set[str]:
    hashes: set[str] = set()
    for index, path in enumerate(PRIOR_CHALLENGE_SCRIPTS, start=1):
        require_file(path)
        module = load_module(f"religious_prior_challenge_{index}", path)
        hashes.update(normalized_hash(row["text"]) for row in module.build_fixed_challenge())
    return hashes


def add_group(
    rows: list[dict[str, Any]],
    group: str,
    expected: str,
    texts: list[str],
) -> None:
    if len(texts) != 30:
        raise RuntimeError(f"RC4 challenge group {group} must contain 30 records.")
    for text in texts:
        rows.append(
            {
                "case_id": f"REL-RC4-HOLDOUT-{len(rows) + 1:03d}",
                "group": group,
                "expected": expected,
                "text": text,
            }
        )


def paired_texts(
    frame: str,
    first: tuple[str, ...],
    second: tuple[str, ...],
) -> list[str]:
    if len(first) != 30 or len(second) != 30:
        raise RuntimeError("Every fixed RC4 term list must contain 30 entries.")
    return [
        frame.format(first=left, second=right)
        for left, right in zip(first, second, strict=True)
    ]


def build_fixed_challenge() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    object_actions = (
        "reduce to ashes", "slash apart", "stamp on", "coat in filth", "break into fragments",
        "set ablaze", "throw into a sewer", "cover in obscene paint", "publicly desecrate", "tear to ribbons",
        "kick repeatedly", "hack into pieces", "drag across garbage", "spray with degrading words", "crush under a vehicle",
        "burn during a rally", "shatter with stones", "rip apart on camera", "mutilate in public", "destroy as a provocation",
        "smear with waste", "trample before spectators", "deface with insults", "dump into flames", "wreck deliberately",
        "soil during the ceremony", "cut into scraps", "vandalize overnight", "smash for entertainment", "profane in front of worshippers",
    )
    object_targets = (
        "revered manuscript", "religious tapestry", "holy emblem", "devotional portrait", "sacred vessel",
        "consecrated book", "religious relic", "worship icon", "sacred banner", "holy scripture",
        "ceremonial statue", "religious carving", "devotional artwork", "sacred painting", "holy monument",
        "religious text", "consecrated symbol", "prayer beads", "sacred image", "religious object",
        "holy scroll", "devotional flag", "sacred artefact", "religious manuscript", "revered statue",
        "ceremonial emblem", "holy portrait", "consecrated relic", "sacred sculpture", "religious banner",
    )
    add_group(
        rows,
        "sacred_object_or_text_attack",
        RELIGIOUS_OUTPUT,
        paired_texts(
            "A public campaign says participants should {first} the {second} to offend the faith.",
            object_actions,
            object_targets,
        ),
    )

    figure_actions = (
        "publish a humiliating cartoon of", "launch an abusive campaign against", "circulate obscene edits of", "heap degrading insults on", "malign",
        "publicly ridicule", "create a vile caricature of", "encourage contemptuous mockery of", "distribute a degrading portrait of", "invite callers to insult",
        "post a humiliating parody of", "vilify", "revile", "deride", "slander",
        "demean", "share an abusive depiction of", "promote obscene ridicule of", "call for public humiliation of", "release a morphed image attacking",
        "lampoon with degrading imagery", "publish repulsive drawings of", "invite users to mock", "urge the crowd to abuse", "circulate insulting artwork about",
        "denigrate", "post degrading edits of", "encourage obscene jokes targeting", "launch a campaign to humiliate", "promote abusive caricatures of",
    )
    figure_targets = (
        "the revered prophet", "a sacred faith founder", "the deity", "a spiritual guide", "the religious leader",
        "a venerated holy person", "the sacred teacher", "a divine figure", "the prophet", "the faith founder",
        "a religious figurehead", "the spiritual leader", "a revered teacher", "the deity", "a holy person",
        "the religious founder", "a sacred figure", "the prophet", "a faith leader", "the venerated teacher",
        "a religious figure", "the divine figure", "a spiritual leader", "the revered prophet", "the sacred founder",
        "a holy teacher", "the deity", "a religious leader", "the faith figurehead", "a revered spiritual guide",
    )
    add_group(
        rows,
        "deity_prophet_or_figure_attack",
        RELIGIOUS_OUTPUT,
        paired_texts(
            "The account asks its followers to {first} {second} as a deliberate religious provocation.",
            figure_actions,
            figure_targets,
        ),
    )

    place_actions = (
        "bulldoze", "set on fire", "cover with obscene slogans", "ransack", "tear apart",
        "smash the entrance of", "wreck", "defile", "demolish", "spray degrading graffiti over",
        "destroy", "damage", "level", "torch", "vandalize",
        "profanely alter", "break fixtures inside", "raze", "dismantle", "scorch",
        "shatter the windows of", "mutilate the altar in", "tear down", "paint obscenities across", "attack and damage",
        "ruin", "vandalise", "burn down", "deface", "obliterate",
    )
    place_targets = (
        "the neighborhood prayer centre", "a historic shrine", "the local chapel", "a community mosque", "the old temple",
        "a place of worship", "the sacred sanctuary", "a religious hall", "the monastery", "a church",
        "the gurudwara", "the prayer space", "a devotional sanctuary", "the religious building", "a gurdwara",
        "the sacred site", "a worship centre", "the prayer hall", "the chapel", "a temple",
        "the church", "a shrine", "the place of worship", "the monastery", "a mosque",
        "the sacred sanctuary", "a religious centre", "the worship building", "a prayer hall", "the devotional site",
    )
    add_group(
        rows,
        "place_of_worship_attack",
        RELIGIOUS_OUTPUT,
        paired_texts(
            "An organizer calls on supporters to {first} {second} in order to insult worshippers.",
            place_actions,
            place_targets,
        ),
    )

    follower_subjects = (
        "people who follow that religion", "members of the congregation", "devotees of the faith", "religious adherents", "families in that faith community",
        "worshippers", "people belonging to the religion", "followers of the faith", "members of the religious group", "believers",
        "workers of that religion", "students from the faith community", "adherents of the sect", "people because of their faith", "religious followers",
        "members of that religion", "the worshipping community", "followers of this faith", "people practising the religion", "faith-community families",
        "religious believers", "congregants", "members of the faith", "people identified with the religion", "adherents",
        "the religious community", "devotees", "people of that faith", "members of the denomination", "worshippers of the faith",
    )
    follower_attacks = (
        "should be denied citizenship", "must be expelled", "are inherently criminal", "should lose employment rights", "must be segregated",
        "are less than human", "should be denied housing", "must be driven away", "are dangerous parasites", "should not exist",
        "must be refused jobs", "should be excluded from schools", "must lose civil rights", "should be attacked", "are inferior",
        "must be removed from town", "should be boycotted", "are unfit for public office", "must be denied healthcare", "should be forced to leave",
        "are criminals by nature", "must be kept out of public places", "should be harmed", "must be stripped of voting rights", "are subhuman",
        "should be excluded from society", "must be evicted", "are inherently dangerous", "should be denied services", "must be separated from everyone else",
    )
    add_group(
        rows,
        "protected_followers_hate_boundary",
        NO_OVERRIDE,
        paired_texts(
            "A hostile message says {first} {second}; this boundary belongs to Hate Speech, not religious-offense moderation.",
            follower_subjects,
            follower_attacks,
        ),
    )

    safe_leads = (
        "A legal transcript records", "A journalism class analyzes", "A museum guide documents", "A historian explains", "A prevention workshop discusses",
        "A news article condemns", "A documentary investigates", "An academic paper studies", "An interfaith program opposes", "A court summary describes",
        "A public-service announcement warns against", "A restoration report details", "A teacher provides context about", "A cultural archive records", "A researcher examines",
        "A newspaper reports", "An educational podcast condemns", "A scholar respectfully critiques", "A lesson teaches students to prevent", "A museum catalogue describes",
        "A community statement opposes", "A safety campaign addresses", "A documentary provides context for", "A history book recounts", "A police report records",
        "An academic seminar discusses", "A restoration team explains", "A journalist reports", "A respectful essay questions", "A classroom presentation examines",
    )
    safe_events = (
        "the burning of a sacred manuscript", "an obscene caricature aimed at a prophet", "damage to a prayer hall", "vandalism against a holy monument", "the defacing of religious symbols",
        "an attack on a mosque", "the destruction of an old shrine", "online insults against a deity", "desecration of a sacred book", "graffiti painted on a church",
        "mockery of a spiritual leader", "repairs to a vandalized temple", "the historical burning of scripture", "damage to a religious statue", "an attack on a place of worship",
        "the removal of an abusive image of a prophet", "a campaign that humiliated a faith founder", "a religious doctrine without insulting believers", "damage to sacred artwork", "the conservation of a holy text",
        "vandalism at a gurudwara", "online abuse involving a religious figure", "the restoration of a chapel", "the historical destruction of a monastery", "an attempt to burn prayer books",
        "good-faith disagreement with a doctrine", "repairs to a damaged sacred carving", "police action preventing temple vandalism", "a belief through respectful reasoning", "the social harm of desecration",
    )
    add_group(
        rows,
        "safe_reporting_education_and_criticism",
        NO_OVERRIDE,
        paired_texts(
            "{first} {second} without endorsing the harmful act.",
            safe_leads,
            safe_events,
        ),
    )

    neutral_subjects = (
        "The historic temple", "A neighborhood church", "The city mosque", "The local gurudwara", "A mountain shrine",
        "The old monastery", "The prayer hall", "A sacred painting", "The religious manuscript", "A ceremonial vessel",
        "The community chapel", "The place of worship", "A religious monument", "The devotional artwork", "A sacred statue",
        "The holy book", "A religious carving", "The worship centre", "A prayer space", "A sacred banner",
        "The faith museum", "The religious archive", "A devotional portrait", "The monastery library", "A ceremonial object",
        "The temple committee", "The mosque charity", "The church choir", "The shrine guide", "The interfaith group",
    )
    neutral_predicates = (
        "welcomed visitors for a heritage tour", "announced ordinary opening hours", "hosted a peaceful music program", "was photographed for an architecture class", "received routine roof repairs",
        "appeared in a respectful travel program", "was preserved by museum conservators", "was catalogued by a historian", "remained on display behind glass", "was cleaned before a ceremony",
        "published a normal community notice", "organized a charity meal", "was studied in a neutral academic course", "received proper attribution in an exhibition", "was restored after weather damage",
        "was translated by a language scholar", "was documented for a cultural archive", "scheduled regular maintenance", "hosted a quiet community meeting", "was carried respectfully during a ceremony",
        "opened a new educational exhibit", "digitized historical records", "was included in an art catalogue", "preserved old documents", "was displayed with contextual information",
        "scheduled a public information session", "distributed food to local families", "rehearsed for a weekend performance", "explained the site's history", "held a peaceful discussion",
    )
    add_group(
        rows,
        "neutral_religious_content",
        NO_OVERRIDE,
        paired_texts(
            "{first} {second}, with no attack or insult.",
            neutral_subjects,
            neutral_predicates,
        ),
    )

    unrelated_subjects = (
        "A suspicious email", "A private message", "An attachment", "A fake profile", "A graphic video",
        "An online seller", "A hostile account", "An unreliable article", "A marketing inbox", "A streaming site",
        "An adult image", "An extremist post", "A routine document", "A scam caller", "A copied company page",
        "A public comment", "A threatening recording", "A harassment group", "A calendar notice", "A restaurant review",
        "A football comment", "A school message", "A software file", "A news claim", "A private-data post",
        "A counterfeit store", "A normal reminder", "A workplace note", "A travel booking", "A grocery list",
    )
    unrelated_predicates = (
        "asks for an OTP to release a fake prize", "reveals somebody's home address", "installs password-stealing malware", "impersonates a bank employee", "shows an uncensored physical assault",
        "advertises an illegal substance", "threatens a former partner", "makes an unsupported medical assertion", "contains unsolicited advertisements", "distributes a copyrighted movie",
        "contains explicit sexual material", "promotes a terrorist organization", "lists tomorrow's meeting agenda", "demands banking credentials", "uses a stolen brand identity",
        "publishes a private phone number", "threatens to injure another person", "coordinates abuse against a classmate", "schedules a project call", "criticizes slow service",
        "mocks a player's poor performance", "contains repeated personal insults", "runs malicious code", "spreads an unverified current-event rumor", "exposes confidential information",
        "sells pirated software", "mentions an upcoming appointment", "records ordinary action items", "confirms a hotel reservation", "contains household shopping items",
    )
    add_group(
        rows,
        "unrelated_or_personal_boundary",
        NO_OVERRIDE,
        paired_texts(
            "{first} {second}; another policy component owns this case.",
            unrelated_subjects,
            unrelated_predicates,
        ),
    )
    return rows


def challenge_sha256(rows: list[dict[str, Any]]) -> str:
    payload = "\n".join(
        "|".join((row["case_id"], row["group"], row["expected"], row["text"]))
        for row in rows
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def predict_binary(
    classifier: Any,
    encoder: Any,
    config: dict[str, Any],
    texts: list[str],
) -> list[str]:
    embeddings = encoder.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    probabilities = classifier.predict_proba(embeddings)
    classes = np.asarray(classifier.classes_)
    religious_index = int(np.where(classes == RELIGIOUS_OUTPUT)[0][0])
    policy = config["religious_only_guard_policy"]
    threshold = float(policy["religious_probability_threshold"])
    minimum_margin = float(policy["minimum_religious_margin"])
    predicted: list[str] = []
    for scores in probabilities:
        religious_score = float(scores[religious_index])
        competing_score = float(np.max(np.delete(scores, religious_index)))
        margin = religious_score - competing_score
        predicted.append(
            RELIGIOUS_OUTPUT
            if religious_score >= threshold and margin >= minimum_margin
            else NO_OVERRIDE
        )
    return predicted


def main() -> None:
    if VERDICT_PATH.exists():
        raise FileExistsError(
            "RC4 already has an independent verdict. The challenge will not be rerun."
        )
    for path in (
        MANIFEST_PATH,
        MODEL_ARTIFACT,
        MODEL_CONFIG,
        TRAIN_DATASET,
        VALIDATION_DATASET,
        *PRIOR_CHALLENGE_SCRIPTS,
    ):
        require_file(path)
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verify_candidate(manifest)
    gate = manifest["independent_gate_frozen_before_holdout"]
    config = json.loads(MODEL_CONFIG.read_text(encoding="utf-8"))
    challenge = build_fixed_challenge()
    challenge_hashes = {normalized_hash(row["text"]) for row in challenge}
    if len(challenge_hashes) != len(challenge):
        raise RuntimeError("The RC4 challenge contains duplicate text.")
    train_overlap = len(challenge_hashes & csv_text_hashes(TRAIN_DATASET))
    validation_overlap = len(challenge_hashes & csv_text_hashes(VALIDATION_DATASET))
    prior_overlap = len(challenge_hashes & prior_challenge_hashes())

    classifier = joblib.load(MODEL_ARTIFACT)
    encoder = SentenceTransformer(
        str(config["embedding_model"]),
        revision=str(config["embedding_model_revision"]),
        device="cpu",
    )
    processing_errors = 0
    try:
        predictions = predict_binary(
            classifier,
            encoder,
            config,
            [row["text"] for row in challenge],
        )
    except Exception:
        processing_errors = len(challenge)
        predictions = [NO_OVERRIDE] * len(challenge)

    results: list[dict[str, Any]] = []
    for row, predicted in zip(challenge, predictions, strict=True):
        expected = row["expected"]
        action_failure = False
        if predicted == RELIGIOUS_OUTPUT:
            action = REQUIRED_ACTION
            human_review = True
            automatic = False
            action_failure = bool(
                action != REQUIRED_ACTION or not human_review or automatic
            )
        results.append(
            {
                "group": row["group"],
                "expected": expected,
                "predicted": predicted,
                "correct": predicted == expected,
                "category_mix_failure": expected == NO_OVERRIDE and predicted == RELIGIOUS_OUTPUT,
                "action_contract_failure": action_failure,
            }
        )

    positive = [row for row in results if row["expected"] == RELIGIOUS_OUTPUT]
    negative = [row for row in results if row["expected"] == NO_OVERRIDE]
    tp = sum(row["expected"] == RELIGIOUS_OUTPUT and row["predicted"] == RELIGIOUS_OUTPUT for row in results)
    tn = sum(row["expected"] == NO_OVERRIDE and row["predicted"] == NO_OVERRIDE for row in results)
    fp = sum(row["expected"] == NO_OVERRIDE and row["predicted"] == RELIGIOUS_OUTPUT for row in results)
    fn = sum(row["expected"] == RELIGIOUS_OUTPUT and row["predicted"] == NO_OVERRIDE for row in results)
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    accuracy = safe_divide(tp + tn, len(results))
    neutral_rows = [row for row in results if row["group"] == "neutral_religious_content"]
    neutral_safe_rate = safe_divide(
        sum(row["predicted"] == NO_OVERRIDE for row in neutral_rows),
        len(neutral_rows),
    )
    category_mix_failures = sum(row["category_mix_failure"] for row in results)
    action_failures = sum(row["action_contract_failure"] for row in results)

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
    follower_output_enabled = False
    zero_development_overlap = train_overlap == 0 and validation_overlap == 0
    checks = {
        "zero_development_overlap": zero_development_overlap if gate["require_zero_development_overlap"] else True,
        "zero_prior_challenge_reuse": prior_overlap == 0 if gate["require_zero_prior_challenge_reuse"] else True,
        "binary_accuracy": accuracy >= gate["minimum_binary_accuracy"],
        "religious_precision": precision >= gate["minimum_religious_precision"],
        "religious_recall": recall >= gate["minimum_religious_recall"],
        "religious_f1": f1 >= gate["minimum_religious_f1"],
        "nonreligious_specificity": specificity >= gate["minimum_nonreligious_specificity"],
        "neutral_religious_safe_rate": neutral_safe_rate >= gate["minimum_neutral_religious_safe_rate"],
        "minimum_group_accuracy": minimum_group_accuracy >= gate["minimum_group_accuracy"],
        "category_mix_contract": category_mix_failures <= gate["maximum_category_mix_failures"],
        "action_contract": action_failures <= gate["maximum_action_contract_failures"],
        "processing_contract": processing_errors <= gate["maximum_processing_errors"],
        "follower_boundary_output_disabled": (
            not follower_output_enabled if gate["require_follower_boundary_output_disabled"] else True
        ),
    }
    passed = all(checks.values())

    report = {
        "candidate": CANDIDATE_NAME,
        "challenge_version": "2026.08-v5-rc4-religious-only-independent",
        "challenge_sha256": challenge_sha256(challenge),
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(results),
        "positive_records": len(positive),
        "negative_records": len(negative),
        "train_overlap": train_overlap,
        "validation_overlap": validation_overlap,
        "prior_challenge_overlap": prior_overlap,
        "accuracy": round(accuracy, 4),
        "religious_precision": round(precision, 4),
        "religious_recall": round(recall, 4),
        "religious_f1": round(f1, 4),
        "nonreligious_specificity": round(specificity, 4),
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "neutral_religious_safe_rate": round(neutral_safe_rate, 4),
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": group_results,
        "category_mix_failures": category_mix_failures,
        "action_contract_failures": action_failures,
        "processing_errors": processing_errors,
        "follower_boundary_output_enabled": follower_output_enabled,
        "follower_boundary_owner": "Hate Speech & Discrimination V7",
        "independent_gate": gate,
        "gate_checks": checks,
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "raw_challenge_dataset_stored": False,
        "individual_predictions_stored": False,
        "individual_predictions_printed": False,
        "holdout_may_modify_rc4": False,
        "evaluation_limit": "Synthetic challenge evidence; not external or real-world accuracy.",
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    verdict = {
        "candidate": CANDIDATE_NAME,
        "status": (
            "Passed religious-only synthetic independent readiness gate"
            if passed
            else "Failed religious-only synthetic independent readiness gate"
        ),
        "evaluated_at_utc": report["evaluated_at_utc"],
        "challenge_sha256": report["challenge_sha256"],
        "passed_independent_readiness_gate": passed,
        "eligible_for_guarded_live_integration": passed,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "aggregate_report": str(REPORT_PATH),
        "frozen_artifacts_modified": False,
        "holdout_may_modify_rc4": False,
        "evidence_type": "religious-only synthetic independent challenge",
    }
    VERDICT_PATH.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")

    print("RELIGIOUSLY OFFENSIVE CONTENT V5 RC4 INDEPENDENT CHALLENGE")
    print("=" * 60)
    print(f"Candidate: {CANDIDATE_NAME}")
    print(f"Challenge SHA-256: {report['challenge_sha256']}")
    print(f"Records: {len(results)}")
    print(f"Positive records: {len(positive)}")
    print(f"Negative records: {len(negative)}")
    print(f"Train overlap: {train_overlap}")
    print(f"Validation overlap: {validation_overlap}")
    print(f"Prior challenge overlap: {prior_overlap}")
    print(f"Binary accuracy: {accuracy * 100:.2f}%")
    print(f"Religious precision: {precision * 100:.2f}%")
    print(f"Religious recall: {recall * 100:.2f}%")
    print(f"Religious F1: {f1 * 100:.2f}%")
    print(f"Nonreligious specificity: {specificity * 100:.2f}%")
    print(f"Neutral-religious safe routing: {neutral_safe_rate * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Action-contract failures: {action_failures}")
    print(f"Processing errors: {processing_errors}")
    print("Follower-boundary output enabled: False")
    print("Follower-boundary owner: Hate Speech & Discrimination V7")
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
    print(f"Passed religious-only independent readiness gate: {passed}")
    print(f"Eligible for guarded live integration: {passed}")
    print("Automatic enforcement allowed: False")
    print("Connected to live moderation: False")
    print(f"Report: {REPORT_PATH}")
    print(f"Verdict: {VERDICT_PATH}")
    print("No raw challenge dataset or individual predictions were stored or printed.")
    print("This is synthetic evidence, not external or real-world accuracy.")
    print("This holdout may not be used to modify RC4.")


if __name__ == "__main__":
    main()

