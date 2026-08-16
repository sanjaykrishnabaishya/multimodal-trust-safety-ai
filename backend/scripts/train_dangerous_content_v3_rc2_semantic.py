from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    f1_score,
    precision_recall_fscore_support,
)


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
DATASET_DIRECTORY = (
    ROOT_DIRECTORY / "datasets" / "development" / "dangerous_content_v3_rc2"
)
MODEL_DIRECTORY = (
    ROOT_DIRECTORY / "backend" / "storage" / "models" / "dangerous_content_v3_rc2"
)
REPORT_DIRECTORY = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v3_rc2_semantic_development"
)

TRAIN_PATH = DATASET_DIRECTORY / "train.csv"
VALIDATION_PATH = DATASET_DIRECTORY / "validation.csv"
MANIFEST_PATH = DATASET_DIRECTORY / "manifest.json"
MODEL_PATH = MODEL_DIRECTORY / "classifier.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "config.json"
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"

CANDIDATE = "dangerous-content-v3-rc2-development"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

DANGEROUS_LABEL = "dangerous_advocacy"
SAFE_WARNING_LABEL = "safe_warning"
PROFESSIONAL_LABEL = "professional_controlled"
OTHER_LABEL = "safe_or_other"
LABELS = [DANGEROUS_LABEL, SAFE_WARNING_LABEL, PROFESSIONAL_LABEL, OTHER_LABEL]


TRAIN_FAMILIES: dict[str, list[tuple[str, str]]] = {
    DANGEROUS_LABEL: [
        ("stunt_height", "encourages an untrained person to attempt a hazardous stunt at height"),
        ("stunt_vehicle", "dares viewers to perform a dangerous moving-vehicle stunt"),
        ("fire_action", "urges someone to start an uncontrolled fire near people or property"),
        ("electrical_action", "encourages contact with unsafe live electrical equipment"),
        ("mechanical_action", "promotes bypassing machinery safeguards while equipment is moving"),
        ("chemical_action", "invites an unsupervised hazardous chemical experiment at home"),
        ("pressure_action", "encourages an unsafe pressure or explosion experiment"),
        ("transport_action", "tells a person to interfere dangerously with a moving vehicle"),
        ("self_endangerment", "pressures a person to perform an action likely to cause bodily harm"),
        ("other_endangerment", "asks someone to expose another person to an immediate physical hazard"),
        ("property_endangerment", "encourages an action likely to destroy or seriously damage property"),
        ("challenge_imitation", "presents a risky challenge and directly asks the audience to copy it"),
        ("hazard_no_controls", "demonstrates a hazardous activity while dismissing protective controls"),
        ("weaponlike_hazard", "encourages unsafe handling of a dangerous object around bystanders"),
        ("environmental_hazard", "promotes entering a clearly unsafe restricted natural area"),
        ("household_hazard", "urges combining ordinary household items in a hazardous unsupervised act"),
    ],
    SAFE_WARNING_LABEL: [
        ("warning_stunt", "warns people not to imitate a dangerous stunt shown in a news report"),
        ("warning_fire", "explains how to prevent accidental fires and contact emergency services"),
        ("warning_electrical", "teaches electrical hazard recognition without attempting the hazard"),
        ("warning_chemical", "reports a hazardous experiment and tells viewers not to repeat it"),
        ("warning_vehicle", "condemns a viral moving-vehicle challenge and promotes road safety"),
        ("warning_property", "describes property damage only to explain prevention and legal consequences"),
        ("warning_self", "discourages self-endangering behavior and directs the person to safety"),
        ("warning_other", "condemns exposing another person to danger and recommends protective action"),
        ("warning_mechanical", "explains machinery lockout and injury prevention without bypass instructions"),
        ("warning_household", "alerts families to a household hazard and recommends safe storage"),
        ("reporting_accident", "neutrally reports that a dangerous incident occurred without encouraging it"),
        ("prevention_campaign", "shares a public safety campaign against reckless challenges"),
        ("emergency_guidance", "provides high-level emergency safety guidance after an accident"),
        ("safety_research", "summarizes research about injury prevention without demonstrating harmful acts"),
        ("warning_environment", "warns visitors to avoid a restricted hazardous area"),
        ("condemnation", "explicitly condemns an unsafe act and asks others not to copy it"),
    ],
    PROFESSIONAL_LABEL: [
        ("professional_fire", "shows trained firefighters in a controlled exercise with safety precautions"),
        ("professional_electrical", "shows licensed technicians isolating equipment under formal controls"),
        ("professional_chemical", "presents a supervised laboratory demonstration with protective equipment"),
        ("professional_stunt", "shows a trained performer on a closed set with documented safety controls"),
        ("professional_mechanical", "demonstrates machinery inside a controlled training facility with guards"),
        ("professional_vehicle", "shows certified drivers on a closed course with emergency staff present"),
        ("professional_rescue", "documents a trained rescue team performing an authorized exercise"),
        ("professional_construction", "teaches workplace safety under qualified supervision and access control"),
        ("professional_science", "explains a hazardous scientific principle without inviting audience imitation"),
        ("professional_medicine", "shows qualified medical staff performing a controlled clinical procedure"),
        ("professional_demolition", "reports licensed demolition work inside an evacuated controlled site"),
        ("professional_training", "uses simulation equipment to teach hazard response without real exposure"),
        ("professional_sport", "shows a regulated extreme sport with trained staff and required equipment"),
        ("professional_industry", "documents an industrial process with permits barriers and monitoring"),
        ("professional_emergency", "shows an authorized emergency drill with clear public safety messaging"),
        ("professional_education", "provides classroom safety education while prohibiting unsupervised practice"),
    ],
    OTHER_LABEL: [
        ("ordinary_game", "invites friends to play a harmless board-game challenge"),
        ("ordinary_fitness", "encourages a normal beginner exercise with rest and sensible limits"),
        ("ordinary_cooking", "shares a routine cooking activity using standard kitchen safety"),
        ("ordinary_craft", "demonstrates a harmless paper craft for children with adult supervision"),
        ("violent_depiction", "describes a fictional fight scene without encouraging a real dangerous act"),
        ("targeted_threat", "directly threatens to attack a named person"),
        ("private_information", "posts another person's private address and phone number"),
        ("phishing", "pretends to be account support and requests a secret login code"),
        ("cyberbullying", "repeatedly targets a person with unwanted intimidating messages"),
        ("hate_boundary", "attacks people because of a protected identity"),
        ("religious_boundary", "directly desecrates a sacred object in hateful expression"),
        ("terrorism_boundary", "praises recruitment or material support for an extremist organization"),
        ("misinformation", "makes a checkable factual claim that requires evidence verification"),
        ("neutral_news", "reports a public event in neutral language without encouraging harm"),
        ("ordinary_job", "advertises a legitimate engineering job and workplace training"),
        ("ordinary_activity", "encourages a safe community cleanup with gloves and permission"),
    ],
}


VALIDATION_FAMILIES: dict[str, list[tuple[str, str]]] = {
    DANGEROUS_LABEL: [
        ("unseen_rooftop_dare", "pressures an amateur to copy a perilous rooftop challenge"),
        ("unseen_rail_hazard", "encourages interfering with active transport infrastructure"),
        ("unseen_battery_hazard", "promotes unsafe tampering with high-energy equipment at home"),
        ("unseen_water_hazard", "dares an untrained person to enter visibly dangerous water"),
        ("unseen_fume_hazard", "encourages creating hazardous fumes in an enclosed household space"),
        ("unseen_machine_hazard", "invites viewers to defeat a powered tool's protective system"),
        ("unseen_bystander_risk", "asks a participant to expose unsuspecting bystanders to physical danger"),
        ("unseen_property_risk", "urges a reckless act expected to cause serious property destruction"),
    ],
    SAFE_WARNING_LABEL: [
        ("unseen_warning_rooftop", "asks viewers to avoid a rooftop trend and explains the injury risk"),
        ("unseen_warning_transport", "reports transport interference while strongly discouraging imitation"),
        ("unseen_warning_battery", "shares battery fire prevention and safe disposal guidance"),
        ("unseen_warning_water", "promotes water safety and tells untrained visitors to stay away"),
        ("unseen_warning_fumes", "warns against mixing products that may create dangerous fumes"),
        ("unseen_warning_machine", "teaches why machine safety guards must remain in place"),
        ("unseen_warning_bystander", "condemns pranks that put unsuspecting people in physical danger"),
        ("unseen_warning_property", "explains how to prevent vandalism and serious property damage"),
    ],
    PROFESSIONAL_LABEL: [
        ("unseen_controlled_height", "shows certified rope-access staff working inside a controlled zone"),
        ("unseen_controlled_transport", "documents an authorized transport safety drill on a closed route"),
        ("unseen_controlled_battery", "shows laboratory battery testing behind protective barriers"),
        ("unseen_controlled_water", "shows trained rescue swimmers during a supervised exercise"),
        ("unseen_controlled_fumes", "demonstrates ventilation testing by qualified industrial hygienists"),
        ("unseen_controlled_machine", "shows certified instructors using guarded training machinery"),
        ("unseen_controlled_effect", "documents a permitted special effect with exclusion zones and fire staff"),
        ("unseen_controlled_property", "shows authorized structural testing at an evacuated research site"),
    ],
    OTHER_LABEL: [
        ("unseen_safe_puzzle", "invites classmates to complete a harmless logic puzzle"),
        ("unseen_safe_walk", "organizes a normal community walk on an approved public route"),
        ("unseen_violence_owner", "contains a direct threat to physically assault a person"),
        ("unseen_spam_owner", "uses impersonation to demand a password from an account holder"),
        ("unseen_private_owner", "publishes a private home address without consent"),
        ("unseen_hate_owner", "dehumanizes a protected group"),
        ("unseen_fact_owner", "states a factual claim about a public institution that needs verification"),
        ("unseen_neutral", "discusses routine daily activities without danger or policy violations"),
    ],
}

TRAIN_TEMPLATES = [
    "This message {description}.",
    "The post clearly {description}.",
    "A video caption {description}.",
    "The speaker {description}.",
    "The content repeatedly {description}.",
    "The upload openly {description}.",
    "Its central message {description}.",
    "The creator's instruction {description}.",
]

VALIDATION_TEMPLATES = [
    "In this independent example, the author {description}.",
    "The main meaning of the new post is that it {description}.",
    "A newly worded caption {description}.",
    "The audience is shown material that {description}.",
]


def text_hash(text: str) -> str:
    normalized = " ".join(text.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_rows(
    families: dict[str, list[tuple[str, str]]],
    templates: list[str],
    split: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sequence = 0
    for label, items in families.items():
        for family_id, description in items:
            for template_index, template in enumerate(templates, start=1):
                sequence += 1
                text = template.format(description=description)
                rows.append(
                    {
                        "record_id": f"{split.upper()}-{sequence:04d}",
                        "split": split,
                        "family_id": family_id,
                        "label": label,
                        "text": text,
                        "text_sha256": text_hash(text),
                        "source": "synthetic_policy_concept",
                    }
                )
    return rows


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "record_id",
        "split",
        "family_id",
        "label",
        "text",
        "text_sha256",
        "source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def binary_metrics(
    expected: np.ndarray,
    predicted: np.ndarray,
) -> dict[str, float | int]:
    true_positive = int(np.sum(expected & predicted))
    true_negative = int(np.sum(~expected & ~predicted))
    false_positive = int(np.sum(~expected & predicted))
    false_negative = int(np.sum(expected & ~predicted))

    precision = true_positive / (true_positive + false_positive) if true_positive + false_positive else 0.0
    recall = true_positive / (true_positive + false_negative) if true_positive + false_negative else 0.0
    specificity = true_negative / (true_negative + false_positive) if true_negative + false_positive else 0.0
    accuracy = (true_positive + true_negative) / len(expected) if len(expected) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "true_positives": true_positive,
        "true_negatives": true_negative,
        "false_positives": false_positive,
        "false_negatives": false_negative,
    }


def calibrate_policy(
    probabilities: np.ndarray,
    class_names: list[str],
    expected_labels: list[str],
    family_ids: list[str],
) -> dict[str, Any]:
    dangerous_index = class_names.index(DANGEROUS_LABEL)
    expected_dangerous = np.asarray(
        [label == DANGEROUS_LABEL for label in expected_labels], dtype=bool
    )
    top_indices = np.argmax(probabilities, axis=1)
    top_probabilities = probabilities[np.arange(len(probabilities)), top_indices]
    sorted_probabilities = np.sort(probabilities, axis=1)
    margins = sorted_probabilities[:, -1] - sorted_probabilities[:, -2]

    candidates: list[dict[str, Any]] = []
    for probability_threshold in np.arange(0.35, 0.951, 0.01):
        for minimum_margin in np.arange(0.0, 0.301, 0.01):
            predicted_dangerous = (
                (top_indices == dangerous_index)
                & (probabilities[:, dangerous_index] >= probability_threshold)
                & (margins >= minimum_margin)
            )
            metrics = binary_metrics(expected_dangerous, predicted_dangerous)

            family_results: dict[str, list[bool]] = defaultdict(list)
            for family_id, expected, predicted in zip(
                family_ids, expected_dangerous, predicted_dangerous
            ):
                family_results[family_id].append(bool(expected == predicted))
            minimum_family_accuracy = min(
                sum(values) / len(values) for values in family_results.values()
            )

            gates = {
                "accuracy": metrics["accuracy"] >= 0.90,
                "dangerous_precision": metrics["precision"] >= 0.90,
                "dangerous_recall": metrics["recall"] >= 0.90,
                "safe_specificity": metrics["specificity"] >= 0.95,
                "minimum_family_accuracy": minimum_family_accuracy >= 0.75,
            }
            candidates.append(
                {
                    "probability_threshold": round(float(probability_threshold), 2),
                    "minimum_score_margin": round(float(minimum_margin), 2),
                    "metrics": metrics,
                    "minimum_family_accuracy": minimum_family_accuracy,
                    "gates": gates,
                    "passed": all(gates.values()),
                    "accepted": int(np.sum(predicted_dangerous)),
                }
            )

    passing = [candidate for candidate in candidates if candidate["passed"]]
    if passing:
        chosen = max(
            passing,
            key=lambda item: (
                item["metrics"]["f1"],
                item["metrics"]["recall"],
                item["metrics"]["precision"],
                item["minimum_family_accuracy"],
                -item["probability_threshold"],
            ),
        )
        chosen["enabled"] = True
        return chosen

    chosen = max(
        candidates,
        key=lambda item: (
            sum(item["gates"].values()),
            item["metrics"]["f1"],
            item["metrics"]["precision"],
            item["metrics"]["recall"],
        ),
    )
    chosen["enabled"] = False
    return chosen


def percentage(value: float) -> str:
    return f"{value * 100:.2f}%"


def main() -> None:
    print("DANGEROUS CONTENT V3 RC2 SEMANTIC DEVELOPMENT")
    print("=" * 60)
    print("RC1 aggregate failure signal used: zero recall on unseen danger families.")
    print("RC1 holdout cases, predictions, and mismatches are not read.")
    print()

    train_rows = build_rows(TRAIN_FAMILIES, TRAIN_TEMPLATES, "train")
    validation_rows = build_rows(
        VALIDATION_FAMILIES, VALIDATION_TEMPLATES, "validation"
    )

    train_hashes = {row["text_sha256"] for row in train_rows}
    validation_hashes = {row["text_sha256"] for row in validation_rows}
    text_overlap = train_hashes & validation_hashes
    train_families = {row["family_id"] for row in train_rows}
    validation_families = {row["family_id"] for row in validation_rows}
    family_overlap = train_families & validation_families
    if text_overlap or family_overlap:
        raise RuntimeError("Train/validation separation failed.")

    write_csv(TRAIN_PATH, train_rows)
    write_csv(VALIDATION_PATH, validation_rows)

    manifest = {
        "candidate": CANDIDATE,
        "training_records": len(train_rows),
        "validation_records": len(validation_rows),
        "training_label_counts": dict(Counter(row["label"] for row in train_rows)),
        "validation_label_counts": dict(
            Counter(row["label"] for row in validation_rows)
        ),
        "train_validation_text_overlap": 0,
        "train_validation_family_overlap": 0,
        "semantic_model_name": MODEL_NAME,
        "semantic_model_revision": MODEL_REVISION,
        "source": "synthetic policy concepts",
        "external_or_restricted_data_used": False,
        "actionable_harm_instructions_stored": False,
        "rc1_aggregate_result_used_as_development_signal": True,
        "rc1_holdout_cases_read": False,
        "rc1_predictions_or_mismatches_read": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
    }
    DATASET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print(f"Training records: {len(train_rows)}")
    print(f"Validation records: {len(validation_rows)}")
    print("Train/validation text overlap: 0")
    print("Train/validation family overlap: 0")
    print(f"Loading pinned semantic encoder: {MODEL_NAME}")

    encoder = SentenceTransformer(
        MODEL_NAME,
        revision=MODEL_REVISION,
        device="cpu",
    )
    training_embeddings = encoder.encode(
        [row["text"] for row in train_rows],
        batch_size=32,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    validation_embeddings = encoder.encode(
        [row["text"] for row in validation_rows],
        batch_size=32,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    training_labels = [row["label"] for row in train_rows]
    validation_labels = [row["label"] for row in validation_rows]
    classifier = LogisticRegression(
        C=2.0,
        max_iter=3000,
        class_weight="balanced",
        random_state=20260813,
    )
    classifier.fit(training_embeddings, training_labels)

    raw_predictions = classifier.predict(validation_embeddings)
    raw_probabilities = classifier.predict_proba(validation_embeddings)
    raw_accuracy = float(accuracy_score(validation_labels, raw_predictions))
    raw_macro_f1 = float(
        f1_score(validation_labels, raw_predictions, average="macro")
    )
    class_report = classification_report(
        validation_labels,
        raw_predictions,
        labels=LABELS,
        output_dict=True,
        zero_division=0,
    )

    policy = calibrate_policy(
        raw_probabilities,
        [str(value) for value in classifier.classes_],
        validation_labels,
        [row["family_id"] for row in validation_rows],
    )
    development_gate_passed = bool(
        raw_accuracy >= 0.85
        and raw_macro_f1 >= 0.85
        and policy["enabled"]
        and not text_overlap
        and not family_overlap
    )

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    joblib.dump(classifier, MODEL_PATH)
    model_sha256 = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    configuration = {
        "candidate": CANDIDATE,
        "semantic_model_name": MODEL_NAME,
        "semantic_model_revision": MODEL_REVISION,
        "dangerous_label": DANGEROUS_LABEL,
        "labels": LABELS,
        "dangerous_probability_threshold": policy["probability_threshold"],
        "minimum_score_margin": policy["minimum_score_margin"],
        "development_gate_passed": development_gate_passed,
        "permitted_active_category": "Dangerous Content",
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "model_sha256": model_sha256,
    }
    CONFIG_PATH.write_text(
        json.dumps(configuration, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    report = {
        **manifest,
        "raw_accuracy": raw_accuracy,
        "raw_macro_f1": raw_macro_f1,
        "class_results": {
            label: {
                "precision": float(class_report[label]["precision"]),
                "recall": float(class_report[label]["recall"]),
                "f1": float(class_report[label]["f1-score"]),
                "support": int(class_report[label]["support"]),
            }
            for label in LABELS
        },
        "selective_policy": policy,
        "development_gate_passed": development_gate_passed,
        "model_path": str(MODEL_PATH),
        "model_sha256": model_sha256,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print()
    print("DANGEROUS CONTENT V3 RC2 SEMANTIC DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Raw accuracy: {percentage(raw_accuracy)}")
    print(f"Raw macro F1: {percentage(raw_macro_f1)}")
    print()
    print("CLASS RESULTS")
    print("-" * 60)
    for label in LABELS:
        metrics = report["class_results"][label]
        print(
            f"{label}: precision {percentage(metrics['precision'])} | "
            f"recall {percentage(metrics['recall'])} | "
            f"F1 {percentage(metrics['f1'])}"
        )
    print()
    print("SELECTIVE DANGEROUS OUTPUT")
    print("-" * 60)
    metrics = policy["metrics"]
    print(f"Enabled: {policy['enabled']}")
    print(f"Probability threshold: {policy['probability_threshold']:.2f}")
    print(f"Minimum score margin: {policy['minimum_score_margin']:.2f}")
    print(f"Accuracy: {percentage(metrics['accuracy'])}")
    print(f"Dangerous precision: {percentage(metrics['precision'])}")
    print(f"Dangerous recall: {percentage(metrics['recall'])}")
    print(f"Safe specificity: {percentage(metrics['specificity'])}")
    print(f"Minimum family accuracy: {percentage(policy['minimum_family_accuracy'])}")
    print()
    print(f"Passed development gate: {development_gate_passed}")
    print(f"Artifact: {MODEL_PATH}")
    print(f"Configuration: {CONFIG_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("RC1 aggregate result used as a development signal: True")
    print("RC1 holdout cases, predictions, and mismatches read: False")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
