from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, precision_recall_fscore_support


CANDIDATE = "religiously-offensive-v4-rc3-development"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
LABELS = (
    "religiously_offensive",
    "protected_followers_hate_boundary",
    "safe_reporting_or_criticism",
    "no_religious_override",
)

ROOT = Path(__file__).resolve().parents[2]
RC2_DEVELOPMENT = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v3_rc2"
    / "development.csv"
)
RC2_VERDICT = (
    ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "religiously-offensive-v3-rc2"
    / "independent_evaluation_verdict.json"
)
DATASET_DIRECTORY = (
    ROOT / "datasets" / "development" / "religiously_offensive_v4_rc3"
)
TRAIN_DATASET = DATASET_DIRECTORY / "train.csv"
VALIDATION_DATASET = DATASET_DIRECTORY / "validation.csv"
MODEL_DIRECTORY = (
    ROOT / "backend" / "storage" / "models" / "religiously_offensive_v4_rc3"
)
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v4_rc3_semantic_development"
)
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"


OBJECTS = (
    "holy book",
    "sacred manuscript",
    "religious scripture",
    "consecrated icon",
    "sacred emblem",
    "religious symbol",
    "devotional image",
    "holy statue",
    "prayer beads",
    "ceremonial object",
    "sacred banner",
    "religious flag",
    "worship artefact",
    "sacred monument",
    "holy text",
    "devotional relic",
    "religious carving",
    "sacred painting",
    "consecrated object",
    "holy scripture",
)
OBJECT_ACTIONS = (
    "burn",
    "incinerate",
    "scorch",
    "torch",
    "destroy",
    "desecrate",
    "profane",
    "deface",
    "disfigure",
    "smash",
    "shatter",
    "crush",
    "tear apart",
    "rip up",
    "shred",
    "trample",
    "stomp on",
    "drag through mud",
    "cover with obscene graffiti",
    "mutilate",
)
FIGURES = (
    "deity",
    "prophet",
    "religious figure",
    "spiritual leader",
    "revered teacher",
    "sacred figure",
    "faith founder",
    "religious leader",
    "venerated holy person",
    "religious figurehead",
    "divine figure",
    "revered faith leader",
)
FIGURE_ACTIONS = (
    "mock",
    "ridicule",
    "vilify",
    "demean",
    "humiliate",
    "insult",
    "degrade",
    "revile",
    "deride",
    "slander",
    "lampoon",
    "publish an obscene caricature of",
    "circulate a degrading depiction of",
    "share an abusive morphed image of",
)
PLACES = (
    "temple",
    "church",
    "mosque",
    "gurudwara",
    "gurdwara",
    "shrine",
    "chapel",
    "monastery",
    "sanctuary",
    "altar",
    "prayer hall",
    "prayer space",
    "place of worship",
    "worship building",
    "religious building",
    "sacred site",
    "devotional sanctuary",
    "consecrated worship centre",
)
PLACE_ACTIONS = (
    "burn",
    "torch",
    "destroy",
    "damage",
    "demolish",
    "raze",
    "level",
    "wreck",
    "vandalize",
    "deface",
    "desecrate",
    "profane",
    "tear down",
    "dismantle",
    "cover with obscene messages",
    "smash fixtures inside",
)

FOLLOWERS = (
    "religious followers",
    "followers of the faith",
    "adherents of that religion",
    "people of that faith",
    "religious believers",
    "worshippers",
    "members of the faith community",
    "religious community",
    "members of the religious group",
    "families of that faith",
    "workers of that religion",
    "students of that faith",
    "members of the sect",
    "people because of their religion",
)
FOLLOWER_ATTACKS = (
    "are inferior",
    "are parasites",
    "are not human",
    "are criminals by nature",
    "are inherently dangerous",
    "should not exist",
    "must be excluded from society",
    "should be expelled",
    "must be forced to leave",
    "should be denied employment",
    "must be denied housing",
    "should be denied education",
    "must lose their civil rights",
    "should be segregated",
    "must be attacked",
    "should be harmed",
)

OFFENSIVE_EVENTS = (
    "vandals burned a holy book",
    "someone defaced a sacred symbol",
    "an attacker damaged a prayer hall",
    "a group mocked a prophet",
    "a person smashed a religious statue",
    "a crowd vandalized a place of worship",
    "an account posted an obscene caricature of a deity",
    "a visitor tore a religious scripture",
    "someone covered a shrine with abusive graffiti",
    "an individual trampled a sacred banner",
    "a fire damaged a temple",
    "a user circulated a degrading image of a religious leader",
)

PERSONAL_OR_OTHER = (
    "a football player was called foolish",
    "a customer insulted a shop manager",
    "a student mocked another student's haircut",
    "an employee was humiliated over a mistake",
    "a user posted an abusive reply about clothing",
    "a critic ridiculed a film performance",
    "a scammer requested an OTP for a fake prize",
    "a post exposed somebody's private address",
    "a file installed password-stealing software",
    "an account impersonated a bank employee",
    "a video depicted a graphic physical assault",
    "a seller advertised illegal weapons",
    "a message threatened a former partner",
    "an article made an unsupported medical claim",
    "an inbox received unsolicited advertising",
    "a site distributed a copyrighted film",
    "an image contained explicit adult nudity",
    "a post promoted an extremist organization",
    "a document contained a routine project agenda",
    "a family visited a museum on holiday",
)

NEUTRAL_RELIGIOUS = (
    "The family visited a temple during their holiday.",
    "A religious book is displayed behind glass in the museum.",
    "The choir performed inside the church.",
    "Visitors quietly entered the mosque for a guided tour.",
    "A student described the architecture of a shrine.",
    "The documentary shows a peaceful prayer ceremony.",
    "A scholar compares two religious philosophies respectfully.",
    "The community restored an old sacred painting.",
    "A guide explained the history of the monastery.",
    "The article announces the opening time of a place of worship.",
    "Volunteers cleaned the prayer hall before the event.",
    "The exhibition presents ceremonial objects with attribution.",
)

NEUTRAL_TRAIN_SUBJECTS = (
    "the historic temple",
    "the neighborhood church",
    "the city mosque",
    "the local gurudwara",
    "the mountain shrine",
    "the old monastery",
    "the prayer hall",
    "the sacred painting",
    "the religious manuscript",
    "the ceremonial object",
    "the community chapel",
    "the place of worship",
    "the religious monument",
    "the devotional artwork",
    "the sacred statue",
)
NEUTRAL_TRAIN_PREDICATES = (
    "opened to visitors this morning",
    "was photographed for an architecture project",
    "appears in a respectful museum catalogue",
    "was carefully restored by conservators",
    "is discussed in a neutral history lesson",
    "will host a peaceful community gathering",
    "is protected as an important cultural site",
    "was described without criticism or insult",
    "is included in an academic research archive",
    "was cleaned before the public ceremony",
    "is shown in a travel documentary",
    "remains on display with proper attribution",
)


def normalize(text: str) -> str:
    return " ".join(str(text).casefold().split())


def text_hash(text: str) -> str:
    return hashlib.sha256(normalize(text).encode("utf-8")).hexdigest()


def read_rc2_development() -> list[dict[str, str]]:
    if not RC2_DEVELOPMENT.is_file():
        raise FileNotFoundError(f"RC2 development dataset is missing: {RC2_DEVELOPMENT}")
    with RC2_DEVELOPMENT.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mapped: list[dict[str, str]] = []
    for row in rows:
        group = row["group"]
        if row["religious_violation"].casefold() == "true":
            label = "religiously_offensive"
        elif group == "protected_followers_hate_boundary":
            label = "protected_followers_hate_boundary"
        elif group == "safe_reporting_education_and_criticism":
            label = "safe_reporting_or_criticism"
        else:
            label = "no_religious_override"
        mapped.append(
            {
                "split": "train",
                "label": label,
                "family": f"prior_rc2_development::{group}",
                "text": row["text"],
            }
        )
    return mapped


def add_examples(
    rows: list[dict[str, str]],
    split: str,
    label: str,
    family: str,
    frame: str,
    left: tuple[str, ...],
    right: tuple[str, ...],
    count: int,
    offset: int,
) -> None:
    for index in range(count):
        first = left[(index + offset) % len(left)]
        second = right[(index * 3 + offset) % len(right)]
        rows.append(
            {
                "split": split,
                "label": label,
                "family": family,
                "text": frame.format(first=first, second=second),
            }
        )


def generate_policy_examples() -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    religious_specs = (
        ("object", OBJECT_ACTIONS, OBJECTS),
        ("figure", FIGURE_ACTIONS, FIGURES),
        ("place", PLACE_ACTIONS, PLACES),
    )
    train_frames = (
        "The post urges its audience to {first} the {second}.",
        "A public account tells supporters they should {first} a {second}.",
        "The creator encourages viewers to {first} that {second} as an insult.",
        "A message celebrates a plan to {first} the community's {second}.",
    )
    validation_frames = (
        "During the broadcast, the host calls on listeners to {first} a {second}.",
        "An online campaign asks participants to {first} the local {second}.",
    )
    for kind, actions, targets in religious_specs:
        for frame_index, frame in enumerate(train_frames):
            add_examples(
                rows,
                "train",
                "religiously_offensive",
                f"religious_{kind}_train_frame_{frame_index}",
                frame,
                actions,
                targets,
                20,
                frame_index,
            )
        for frame_index, frame in enumerate(validation_frames):
            add_examples(
                rows,
                "validation",
                "religiously_offensive",
                f"religious_{kind}_validation_frame_{frame_index}",
                frame,
                actions,
                targets,
                10,
                frame_index + 7,
            )

    follower_train_frames = (
        "The message says {first} {second}.",
        "An account publicly claims {first} {second}.",
        "The speaker demands that {first} be treated this way: they {second}.",
        "A post targets {first} and says they {second}.",
    )
    follower_validation_frames = (
        "A campaign singles out {first}, insisting that they {second}.",
        "The broadcast attacks {first} with the claim that they {second}.",
    )
    for index, frame in enumerate(follower_train_frames):
        add_examples(
            rows,
            "train",
            "protected_followers_hate_boundary",
            f"followers_train_frame_{index}",
            frame,
            FOLLOWERS,
            FOLLOWER_ATTACKS,
            60,
            index,
        )
    for index, frame in enumerate(follower_validation_frames):
        add_examples(
            rows,
            "validation",
            "protected_followers_hate_boundary",
            f"followers_validation_frame_{index}",
            frame,
            FOLLOWERS,
            FOLLOWER_ATTACKS,
            30,
            index + 5,
        )

    safe_train_frames = (
        "A news report explains that {first} and condemns the incident.",
        "A history lesson discusses how {first} without supporting it.",
        "An interfaith workshop examines why {first} and promotes respect.",
        "A researcher documents a case where {first} as evidence of abuse.",
    )
    safe_validation_frames = (
        "A court summary records that {first}; it does not endorse the act.",
        "A museum program provides context about an event where {first}.",
    )
    context_words = tuple(
        f"documented incident {index + 1}: {OFFENSIVE_EVENTS[index % len(OFFENSIVE_EVENTS)]}"
        for index in range(60)
    )
    for index, frame in enumerate(safe_train_frames):
        add_examples(
            rows,
            "train",
            "safe_reporting_or_criticism",
            f"safe_train_frame_{index}",
            frame,
            context_words,
            ("unused",),
            60,
            index,
        )
    for index, frame in enumerate(safe_validation_frames):
        add_examples(
            rows,
            "validation",
            "safe_reporting_or_criticism",
            f"safe_validation_frame_{index}",
            frame,
            context_words,
            ("unused",),
            30,
            index + 4,
        )

    other_train_frames = (
        "A routine moderation example states that {first}.",
        "The document neutrally records that {first}.",
        "A user reports a separate issue: {first}.",
        "The example concerns another policy area because {first}.",
    )
    other_validation_frames = (
        "This unrelated case says {first}.",
        "A reviewer receives a report that {first}.",
    )
    other_words = tuple(
        f"policy example {index + 1}: {PERSONAL_OR_OTHER[index % len(PERSONAL_OR_OTHER)]}"
        for index in range(60)
    )
    for index, frame in enumerate(other_train_frames):
        add_examples(
            rows,
            "train",
            "no_religious_override",
            f"other_train_frame_{index}",
            frame,
            other_words,
            ("unused",),
            60,
            index,
        )
    for index, frame in enumerate(other_validation_frames):
        add_examples(
            rows,
            "validation",
            "no_religious_override",
            f"other_validation_frame_{index}",
            frame,
            other_words,
            ("unused",),
            24,
            index + 6,
        )
    neutral_train_frames = (
        "A neutral description notes that {first} {second}.",
        "The visitor guide explains that {first} {second}.",
        "A routine community update says {first} {second}.",
        "The educational catalogue records that {first} {second}.",
    )
    for index, frame in enumerate(neutral_train_frames):
        add_examples(
            rows,
            "train",
            "no_religious_override",
            f"neutral_religious_train_frame_{index}",
            frame,
            NEUTRAL_TRAIN_SUBJECTS,
            NEUTRAL_TRAIN_PREDICATES,
            30,
            index,
        )
    for index, text in enumerate(NEUTRAL_RELIGIOUS):
        rows.append(
            {
                "split": "validation",
                "label": "no_religious_override",
                "family": "neutral_religious_validation",
                "text": text,
            }
        )
    return rows


def deduplicate(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[str] = set()
    unique: list[dict[str, str]] = []
    for row in rows:
        digest = text_hash(row["text"])
        if digest in seen:
            continue
        seen.add(digest)
        unique.append(row)
    return unique


def save_dataset(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["split", "label", "family", "text"])
        writer.writeheader()
        writer.writerows(rows)


def runtime_predictions(
    probabilities: np.ndarray,
    classes: np.ndarray,
    threshold: float,
    margin: float,
) -> np.ndarray:
    predicted: list[str] = []
    for scores in probabilities:
        order = np.argsort(scores)[::-1]
        top_index = int(order[0])
        second_index = int(order[1])
        top_label = str(classes[top_index])
        top_score = float(scores[top_index])
        score_margin = top_score - float(scores[second_index])
        if top_label == "religiously_offensive" and (
            top_score < threshold or score_margin < margin
        ):
            predicted.append("uncertain")
        else:
            predicted.append(top_label)
    return np.array(predicted)


def evaluate_policy(
    truth: np.ndarray,
    probabilities: np.ndarray,
    classes: np.ndarray,
) -> tuple[dict[str, Any], np.ndarray, dict[str, Any]]:
    best: tuple[tuple[float, ...], dict[str, Any], np.ndarray, dict[str, Any]] | None = None
    binary_truth = truth == "religiously_offensive"
    for threshold in np.arange(0.35, 0.91, 0.01):
        for margin in np.arange(0.00, 0.31, 0.02):
            predicted = runtime_predictions(
                probabilities,
                classes,
                float(threshold),
                float(margin),
            )
            report = classification_report(
                truth,
                predicted,
                labels=list(LABELS),
                output_dict=True,
                zero_division=0,
            )
            binary_predicted = predicted == "religiously_offensive"
            precision, recall, f1, _ = precision_recall_fscore_support(
                binary_truth,
                binary_predicted,
                average="binary",
                zero_division=0,
            )
            nonreligious_specificity = float(
                np.mean(~binary_predicted[~binary_truth])
            )
            accuracy = float(np.mean(predicted == truth))
            macro_f1 = float(report["macro avg"]["f1-score"])
            every_class_metrics = all(
                float(report[label]["precision"]) >= 0.85
                and float(report[label]["recall"]) >= 0.85
                and float(report[label]["f1-score"]) >= 0.85
                for label in LABELS
            )
            qualifies = bool(
                accuracy >= 0.85
                and macro_f1 >= 0.85
                and precision >= 0.85
                and recall >= 0.85
                and nonreligious_specificity >= 0.90
                and every_class_metrics
            )
            policy = {
                "religious_probability_threshold": round(float(threshold), 2),
                "minimum_score_margin": round(float(margin), 2),
                "religious_precision": round(float(precision), 4),
                "religious_recall": round(float(recall), 4),
                "religious_f1": round(float(f1), 4),
                "nonreligious_specificity": round(nonreligious_specificity, 4),
                "accuracy": round(accuracy, 4),
                "macro_f1": round(macro_f1, 4),
                "passed_development_gate": qualifies,
            }
            rank = (
                float(qualifies),
                accuracy,
                macro_f1,
                float(precision),
                float(recall),
                float(threshold),
            )
            if best is None or rank > best[0]:
                best = (rank, policy, predicted, report)
    if best is None:
        raise RuntimeError("Unable to calibrate the RC3 religious-output policy.")
    return best[1], best[2], best[3]


def main() -> None:
    if not RC2_VERDICT.is_file():
        raise FileNotFoundError(f"RC2 verdict is missing: {RC2_VERDICT}")
    verdict = json.loads(RC2_VERDICT.read_text(encoding="utf-8"))
    if verdict.get("candidate") != "religiously-offensive-v3-rc2":
        raise RuntimeError("Unexpected RC2 predecessor verdict.")
    if verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("RC3 development is only permitted after the RC2 failure.")

    prior_rows = read_rc2_development()
    generated = generate_policy_examples()
    all_rows = deduplicate([*prior_rows, *generated])
    train = [row for row in all_rows if row["split"] == "train"]
    validation = [row for row in all_rows if row["split"] == "validation"]
    train_hashes = {text_hash(row["text"]) for row in train}
    validation_hashes = {text_hash(row["text"]) for row in validation}
    text_overlap = train_hashes & validation_hashes
    train_families = {row["family"] for row in train}
    validation_families = {row["family"] for row in validation}
    family_overlap = train_families & validation_families
    if text_overlap:
        raise RuntimeError("RC3 train and validation text overlap.")
    if family_overlap:
        raise RuntimeError(f"RC3 template-family overlap: {sorted(family_overlap)}")

    save_dataset(TRAIN_DATASET, train)
    save_dataset(VALIDATION_DATASET, validation)

    train_text = [row["text"] for row in train]
    validation_text = [row["text"] for row in validation]
    train_labels = np.array([row["label"] for row in train])
    validation_labels = np.array([row["label"] for row in validation])

    print("RELIGIOUSLY OFFENSIVE CONTENT V4 RC3 SEMANTIC DEVELOPMENT")
    print("=" * 60)
    print(f"Training records: {len(train)}")
    print(f"Validation records: {len(validation)}")
    print(f"Train/validation text overlap: {len(text_overlap)}")
    print(f"Train/validation family overlap: {len(family_overlap)}")
    print("RC1/RC2 holdout reports or predictions read: False")
    print(f"Loading pinned semantic encoder: {MODEL_NAME}")

    encoder = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")
    train_embeddings = encoder.encode(
        train_text,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    validation_embeddings = encoder.encode(
        validation_text,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    classifier = LogisticRegression(
        C=2.0,
        class_weight="balanced",
        max_iter=4000,
        random_state=42,
    )
    classifier.fit(train_embeddings, train_labels)
    probabilities = classifier.predict_proba(validation_embeddings)
    policy, predictions, report = evaluate_policy(
        validation_labels,
        probabilities,
        classifier.classes_,
    )

    neutral_indices = [
        index
        for index, row in enumerate(validation)
        if row["family"] == "neutral_religious_validation"
    ]
    neutral_harmful_outputs = sum(
        predictions[index]
        in {"religiously_offensive", "protected_followers_hate_boundary"}
        for index in neutral_indices
    )
    neutral_safe_rate = (
        1.0 - neutral_harmful_outputs / len(neutral_indices)
        if neutral_indices
        else 0.0
    )
    policy["neutral_religious_records"] = len(neutral_indices)
    policy["neutral_religious_harmful_overrides"] = neutral_harmful_outputs
    policy["neutral_religious_safe_rate"] = round(neutral_safe_rate, 4)
    policy["passed_development_gate"] = bool(
        policy["passed_development_gate"]
        and neutral_safe_rate >= 0.95
    )

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, MODEL_ARTIFACT)
    config = {
        "candidate": CANDIDATE,
        "embedding_model": MODEL_NAME,
        "embedding_model_revision": MODEL_REVISION,
        "labels": list(LABELS),
        "religious_output_policy": policy,
        "default_if_religious_score_rejected": "uncertain",
        "permitted_active_output": "Religiously Offensive Content only",
        "protected_follower_boundary": "Hate Speech & Discrimination",
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "connected_to_live_moderation": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    MODEL_CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    group_results: dict[str, dict[str, Any]] = {}
    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(validation):
        grouped_indices[row["family"]].append(index)
    for family, indices in sorted(grouped_indices.items()):
        correct = sum(predictions[index] == validation_labels[index] for index in indices)
        group_results[family] = {
            "records": len(indices),
            "correct": int(correct),
            "accuracy": round(correct / len(indices), 4),
        }

    report_payload = {
        "candidate": CANDIDATE,
        "training_records": len(train),
        "validation_records": len(validation),
        "training_label_counts": dict(Counter(train_labels)),
        "validation_label_counts": dict(Counter(validation_labels)),
        "train_validation_text_overlap": len(text_overlap),
        "train_validation_family_overlap": len(family_overlap),
        "policy": policy,
        "classification_report": report,
        "validation_family_results": group_results,
        "passed_development_gate": policy["passed_development_gate"],
        "rc1_or_rc2_holdout_used_for_training_tuning_or_calibration": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "evidence_limit": "Development evidence only; not independent accuracy.",
    }
    REPORT_PATH.write_text(json.dumps(report_payload, indent=2) + "\n", encoding="utf-8")

    print()
    print("RELIGIOUSLY OFFENSIVE CONTENT V4 RC3 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Accuracy: {policy['accuracy'] * 100:.2f}%")
    print(f"Macro F1: {policy['macro_f1'] * 100:.2f}%")
    print(f"Religious precision: {policy['religious_precision'] * 100:.2f}%")
    print(f"Religious recall: {policy['religious_recall'] * 100:.2f}%")
    print(f"Nonreligious specificity: {policy['nonreligious_specificity'] * 100:.2f}%")
    print(f"Religious probability threshold: {policy['religious_probability_threshold']:.2f}")
    print(f"Minimum score margin: {policy['minimum_score_margin']:.2f}")
    print(f"Neutral-religious safe routing: {neutral_safe_rate * 100:.2f}%")
    print(f"Neutral-religious harmful overrides: {neutral_harmful_outputs}")
    print()
    print("CLASS RESULTS")
    print("-" * 60)
    for label in LABELS:
        values = report[label]
        print(
            f"{label}: precision {values['precision'] * 100:.2f}% | "
            f"recall {values['recall'] * 100:.2f}% | "
            f"F1 {values['f1-score'] * 100:.2f}%"
        )
    print()
    print(f"Passed development gate: {policy['passed_development_gate']}")
    print(f"Artifact: {MODEL_ARTIFACT}")
    print(f"Configuration: {MODEL_CONFIG}")
    print(f"Report: {REPORT_PATH}")
    print("RC1/RC2 holdout used for training, tuning, or calibration: False")
    print("Live moderation changed: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
