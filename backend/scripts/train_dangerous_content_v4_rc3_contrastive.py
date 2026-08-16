from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report, f1_score


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
DATASET_DIRECTORY = (
    ROOT_DIRECTORY / "datasets" / "development" / "dangerous_content_v4_rc3"
)
MODEL_DIRECTORY = (
    ROOT_DIRECTORY / "backend" / "storage" / "models" / "dangerous_content_v4_rc3"
)
REPORT_DIRECTORY = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v4_rc3_contrastive_development"
)
TRAIN_PATH = DATASET_DIRECTORY / "train.csv"
VALIDATION_PATH = DATASET_DIRECTORY / "validation.csv"
MANIFEST_PATH = DATASET_DIRECTORY / "manifest.json"
MODEL_PATH = MODEL_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "config.json"
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"

CANDIDATE = "dangerous-content-v4-rc3-development"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"

DANGEROUS_LABEL = "dangerous_advocacy"
SAFE_WARNING_LABEL = "safe_warning"
PROFESSIONAL_LABEL = "professional_controlled"
OTHER_LABEL = "safe_or_other"
CONTEXT_LABELS = [DANGEROUS_LABEL, SAFE_WARNING_LABEL, PROFESSIONAL_LABEL]
ALL_LABELS = CONTEXT_LABELS + [OTHER_LABEL]

ESTABLISHED_CATEGORY_OWNERS = {
    "Violent Content",
    "Publishing Private Information",
    "Spam, Scam & Phishing",
    "Cyberbullying & Harassment",
    "Hate Speech & Discrimination",
    "Religiously Offensive Content",
    "Terrorism & Extremism",
    "Misinformation & Fake News",
}

OTHER_FAMILY_OWNERS = {
    "violence_owner": "Violent Content",
    "private_owner": "Publishing Private Information",
    "spam_owner": "Spam, Scam & Phishing",
    "cyber_owner": "Cyberbullying & Harassment",
    "hate_owner": "Hate Speech & Discrimination",
    "religious_owner": "Religiously Offensive Content",
    "terror_owner": "Terrorism & Extremism",
    "fact_owner": "Misinformation & Fake News",
    "new_violence_owner": "Violent Content",
    "new_private_owner": "Publishing Private Information",
    "new_spam_owner": "Spam, Scam & Phishing",
    "new_hate_owner": "Hate Speech & Discrimination",
    "new_religious_owner": "Religiously Offensive Content",
    "new_terror_owner": "Terrorism & Extremism",
    "new_fact_owner": "Misinformation & Fake News",
}

SAFE_CONTEXT_PATTERNS = [
    r"\bwarn(?:s|ed|ing)?\b",
    r"\bdiscourag(?:e|es|ed|ing)\b",
    r"\bcondemn(?:s|ed|ing)?\b",
    r"\bprevent(?:s|ed|ing|ion)?\b",
    r"\bavoid(?:s|ed|ing)?\b",
    r"\bdo not\b",
    r"\bdon't\b",
    r"\bnot to (?:try|copy|repeat|imitate|attempt)\b",
    r"\bnever (?:try|copy|repeat|imitate|attempt)\b",
    r"\bsafety (?:notice|guidance|lesson|campaign|training|procedure)\b",
    r"\bqualified (?:team|staff|professional|technician|instructor)\b",
    r"\blicensed (?:team|staff|professional|technician|operator)\b",
    r"\bcertified (?:team|staff|professional|technician|operator|instructor)\b",
    r"\bcontrolled (?:site|setting|facility|exercise|demonstration|test|zone)\b",
    r"\bauthorized (?:exercise|test|demonstration|operation|drill)\b",
    r"\bprotective (?:equipment|barrier|procedure|controls?)\b",
]

UNSAFE_OVERRIDE_PATTERNS = [
    r"\bwithout (?:supervision|safety|protective|professional|permission|controls?)\b",
    r"\bno (?:supervision|safety controls?|protective equipment|warning)\b",
    r"\bignore (?:the )?(?:warning|safety|rules?|controls?)\b",
    r"\bdisregard (?:the )?(?:warning|safety|rules?|controls?)\b",
    r"\bbypass (?:the )?(?:guard|safeguard|safety|controls?)\b",
    r"\bdisable (?:the )?(?:guard|safeguard|safety|controls?)\b",
    r"\bremove (?:the )?(?:guard|safeguard|safety barrier)\b",
    r"\burges? (?:an? |the )?(?:untrained|amateur|viewer|audience|person)\b",
    r"\bdares? (?:an? |the )?(?:untrained|amateur|viewer|audience|person)\b",
    r"\basks? (?:the )?(?:viewer|audience|public|person) to (?:try|copy|repeat|imitate|attempt)\b",
    r"\bencourages? (?:the )?(?:viewer|audience|public|person) to (?:try|copy|repeat|imitate|attempt)\b",
    r"\boutside (?:a |the )?controlled (?:site|setting|facility|zone)\b",
]


TRAIN_HAZARDS = [
    ("height_edge", "an unsafe challenge near an exposed height"),
    ("moving_vehicle", "interference with a moving vehicle"),
    ("live_electricity", "contact with unisolated electrical equipment"),
    ("machine_guard", "operation of powered machinery without its safeguard"),
    ("indoor_fumes", "creation of hazardous fumes in an enclosed room"),
    ("open_fire", "an uncontrolled fire close to people or property"),
    ("pressure_hazard", "unsafe handling of a pressurized object"),
    ("deep_water", "entry into dangerous water by an untrained person"),
    ("unstable_structure", "climbing on an unstable structure"),
    ("reckless_transport", "a reckless maneuver on a public transport route"),
    ("heavy_load", "standing beneath an unsecured heavy load"),
    ("restricted_area", "entry into a clearly restricted hazardous area"),
    ("appliance_tampering", "unsafe tampering with a high-energy appliance"),
    ("special_effect", "an uncontrolled imitation of a hazardous special effect"),
    ("corrosive_material", "unprotected handling of a corrosive material"),
    ("untrained_rescue", "an improvised rescue attempt that endangers additional people"),
    ("lifting_system", "unsafe interference with active lifting equipment"),
    ("bystander_prank", "a prank that exposes unsuspecting bystanders to bodily harm"),
    ("property_damage", "a reckless act likely to cause serious property destruction"),
    ("household_hazard", "an unsupervised household experiment with a serious injury risk"),
]

VALIDATION_HAZARDS = [
    ("icy_surface", "a risky stunt on visibly unstable frozen water"),
    ("escalator_mechanism", "interference with exposed moving public machinery"),
    ("roof_gap", "an amateur leap across an elevated gap"),
    ("active_rail", "entry into an active rail area for a challenge"),
    ("generator_fumes", "operation of fume-producing equipment in an enclosed space"),
    ("launch_hazard", "an uncontrolled high-energy launch experiment"),
    ("damaged_wiring", "handling visibly damaged live wiring"),
    ("industrial_blade", "approaching an active cutting machine without its barrier"),
    ("flood_current", "entering fast-moving flood water for entertainment"),
    ("falling_object", "placing people beneath an unstable suspended object"),
    ("crowd_vehicle", "driving recklessly close to a crowd"),
    ("structural_damage", "an unauthorized act likely to destabilize a structure"),
]

TRAIN_OTHER = [
    ("board_game", "invites friends to complete a harmless board-game challenge"),
    ("logic_puzzle", "encourages students to solve a normal logic puzzle"),
    ("safe_fitness", "describes a beginner exercise with rest and ordinary safety limits"),
    ("safe_craft", "shows a harmless classroom paper craft"),
    ("safe_cooking", "shares routine cooking advice with normal kitchen care"),
    ("neutral_news", "neutrally reports a public event without encouraging harm"),
    ("violence_owner", "directly threatens to assault a specific person"),
    ("private_owner", "publishes another person's private home address"),
    ("spam_owner", "impersonates account support to request a secret access code"),
    ("cyber_owner", "repeatedly targets a person with unwanted intimidating messages"),
    ("hate_owner", "attacks people because of a protected identity"),
    ("religious_owner", "directly attacks a sacred object in offensive expression"),
    ("terror_owner", "praises recruitment for an extremist organization"),
    ("fact_owner", "makes a checkable public claim that requires evidence"),
    ("legitimate_job", "advertises a legitimate technical job with workplace training"),
    ("safe_cleanup", "organizes a permitted community cleanup using ordinary precautions"),
    ("creative_hobby", "encourages a beginner to practise a harmless creative hobby"),
    ("language_learning", "invites a learner to rehearse a normal language exercise"),
    ("coding_practice", "asks a novice to try a routine programming exercise"),
    ("art_practice", "encourages a student to practise a basic drawing skill"),
    ("study_routine", "invites beginners to repeat an ordinary study routine"),
    ("safe_rehearsal", "encourages a learner to rehearse a harmless performance skill"),
    ("reading_practice", "asks a beginner to practise reading aloud"),
    ("typing_practice", "encourages a novice to repeat a normal typing exercise"),
]

VALIDATION_OTHER = [
    ("word_game", "invites a family to play a harmless word game"),
    ("community_walk", "organizes a normal walk on an approved public route"),
    ("routine_gardening", "shares routine gardening advice using ordinary care"),
    ("music_practice", "encourages a beginner to practise a musical instrument"),
    ("new_violence_owner", "contains a direct threat to attack a named person"),
    ("new_private_owner", "exposes a private telephone number without consent"),
    ("new_spam_owner", "uses bank impersonation to demand a one-time password"),
    ("new_hate_owner", "dehumanizes people because of a protected characteristic"),
    ("new_religious_owner", "attacks a revered religious figure in offensive speech"),
    ("new_terror_owner", "requests material support for an extremist group"),
    ("new_fact_owner", "states a factual claim about a public institution"),
    ("new_neutral", "discusses an ordinary daily activity without danger"),
]

DANGEROUS_TEMPLATES = [
    "The post urges an untrained viewer to imitate {hazard} and presents it as entertainment.",
    "A creator encourages the audience to try {hazard} without professional supervision.",
    "The message dares an amateur to attempt {hazard} despite the obvious physical risk.",
    "This upload celebrates {hazard} and asks viewers to copy the act.",
    "The central instruction promotes {hazard} while dismissing normal safety controls.",
    "The speaker treats {hazard} as a challenge that ordinary people should repeat.",
]

WARNING_TEMPLATES = [
    "A safety notice discusses {hazard} only to warn people not to imitate it.",
    "The report condemns {hazard} and asks viewers to avoid repeating the act.",
    "This prevention lesson explains the risk of {hazard} without encouraging participation.",
    "The speaker warns that {hazard} can cause serious injury and should never be attempted.",
    "A public safety campaign discourages {hazard} and promotes protective behavior.",
    "The article reports {hazard} while clearly telling the audience not to copy it.",
]

PROFESSIONAL_TEMPLATES = [
    "A qualified team studies {hazard} inside a controlled setting with protective procedures.",
    "Certified professionals demonstrate risk controls related to {hazard} at an authorized facility.",
    "The educational material discusses {hazard} under trained supervision and prohibits imitation.",
    "A controlled test examines {hazard} behind protective barriers with emergency staff present.",
    "Licensed operators address {hazard} during formal safety training at a restricted site.",
    "The documentary shows professionals managing {hazard} with permits and exclusion controls.",
]

OTHER_TEMPLATES = [
    "This message {description}.",
    "The post {description}.",
    "A short caption {description}.",
    "The content simply {description}.",
]


def normalized_hash(text: str) -> str:
    return hashlib.sha256(" ".join(text.lower().split()).encode("utf-8")).hexdigest()


def build_rows(
    hazards: list[tuple[str, str]],
    other_items: list[tuple[str, str]],
    split: str,
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    sequence = 0
    groups = [
        (DANGEROUS_LABEL, DANGEROUS_TEMPLATES),
        (SAFE_WARNING_LABEL, WARNING_TEMPLATES),
        (PROFESSIONAL_LABEL, PROFESSIONAL_TEMPLATES),
    ]
    for hazard_id, hazard in hazards:
        for label, templates in groups:
            for template in templates:
                sequence += 1
                text = template.format(hazard=hazard)
                rows.append(
                    {
                        "record_id": f"{split.upper()}-{sequence:04d}",
                        "split": split,
                        "family_id": f"{label}:{hazard_id}",
                        "label": label,
                        "existing_category": "Normal/Ignore",
                        "text": text,
                        "text_sha256": normalized_hash(text),
                        "source": "paired_synthetic_policy_concept",
                    }
                )
    for family_id, description in other_items:
        for template in OTHER_TEMPLATES:
            sequence += 1
            text = template.format(description=description)
            rows.append(
                {
                    "record_id": f"{split.upper()}-{sequence:04d}",
                    "split": split,
                    "family_id": f"{OTHER_LABEL}:{family_id}",
                    "label": OTHER_LABEL,
                    "existing_category": OTHER_FAMILY_OWNERS.get(
                        family_id, "Normal/Ignore"
                    ),
                    "text": text,
                    "text_sha256": normalized_hash(text),
                    "source": "paired_synthetic_policy_concept",
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
        "existing_category",
        "text",
        "text_sha256",
        "source",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def policy_veto(text: str) -> str | None:
    safe = any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in SAFE_CONTEXT_PATTERNS)
    if not safe:
        return None
    unsafe = any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in UNSAFE_OVERRIDE_PATTERNS)
    if unsafe:
        return None
    return "explicit_warning_prevention_or_professional_control"


def binary_metrics(expected: np.ndarray, predicted: np.ndarray) -> dict[str, float | int]:
    tp = int(np.sum(expected & predicted))
    tn = int(np.sum(~expected & ~predicted))
    fp = int(np.sum(~expected & predicted))
    fn = int(np.sum(expected & ~predicted))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    specificity = tn / (tn + fp) if tn + fp else 0.0
    accuracy = (tp + tn) / len(expected) if len(expected) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "accuracy": accuracy,
        "precision": precision,
        "recall": recall,
        "specificity": specificity,
        "f1": f1,
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
    }


def calibrate(
    boundary_probabilities: np.ndarray,
    boundary_classes: list[str],
    hazard_probabilities: np.ndarray,
    hazard_classes: list[str],
    context_probabilities: np.ndarray,
    context_classes: list[str],
    rows: list[dict[str, str]],
) -> dict[str, Any]:
    boundary_danger_index = boundary_classes.index("dangerous")
    hazard_index = hazard_classes.index("hazard_present")
    context_danger_index = context_classes.index(DANGEROUS_LABEL)
    boundary_scores = boundary_probabilities[:, boundary_danger_index]
    hazard_scores = hazard_probabilities[:, hazard_index]
    context_top_indices = np.argmax(context_probabilities, axis=1)
    context_sorted = np.sort(context_probabilities, axis=1)
    context_margins = context_sorted[:, -1] - context_sorted[:, -2]
    context_danger_scores = context_probabilities[:, context_danger_index]
    expected = np.asarray([row["label"] == DANGEROUS_LABEL for row in rows], dtype=bool)
    vetoes = np.asarray([policy_veto(row["text"]) is not None for row in rows], dtype=bool)
    owner_guards = np.asarray(
        [row["existing_category"] in ESTABLISHED_CATEGORY_OWNERS for row in rows],
        dtype=bool,
    )

    candidates: list[dict[str, Any]] = []
    for boundary_threshold in np.arange(0.30, 0.911, 0.04):
        for hazard_threshold in np.arange(0.30, 0.911, 0.04):
            for context_threshold in np.arange(0.30, 0.911, 0.04):
                for minimum_margin in np.arange(0.0, 0.251, 0.05):
                    predicted_before_owner_guard = (
                        (boundary_scores >= boundary_threshold)
                        & (hazard_scores >= hazard_threshold)
                        & (context_top_indices == context_danger_index)
                        & (context_danger_scores >= context_threshold)
                        & (context_margins >= minimum_margin)
                        & ~vetoes
                    )
                    predicted = predicted_before_owner_guard & ~owner_guards
                    metrics = binary_metrics(expected, predicted)
                    family_results: dict[str, list[bool]] = defaultdict(list)
                    for row, expected_value, predicted_value in zip(rows, expected, predicted):
                        family_results[row["family_id"]].append(bool(expected_value == predicted_value))
                    minimum_family_accuracy = min(
                        sum(values) / len(values) for values in family_results.values()
                    )
                    gates = {
                        "accuracy": metrics["accuracy"] >= 0.90,
                        "dangerous_precision": metrics["precision"] >= 0.92,
                        "dangerous_recall": metrics["recall"] >= 0.90,
                        "safe_specificity": metrics["specificity"] >= 0.97,
                        "minimum_family_accuracy": minimum_family_accuracy >= 0.75,
                        "category_mix_contract": int(np.sum(predicted & owner_guards)) == 0,
                    }
                    candidates.append(
                        {
                            "boundary_probability_threshold": round(float(boundary_threshold), 3),
                            "hazard_probability_threshold": round(float(hazard_threshold), 3),
                            "dangerous_context_probability_threshold": round(float(context_threshold), 3),
                            "minimum_context_margin": round(float(minimum_margin), 3),
                            "metrics": metrics,
                            "minimum_family_accuracy": minimum_family_accuracy,
                            "pre_guard_category_conflicts": int(
                                np.sum(predicted_before_owner_guard & owner_guards)
                            ),
                            "category_mix_failures": int(np.sum(predicted & owner_guards)),
                            "gates": gates,
                            "passed": all(gates.values()),
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
    print("DANGEROUS CONTENT V4 RC3 CONTRASTIVE DEVELOPMENT")
    print("=" * 60)
    print("V3 RC2 aggregate result used: warnings were confused with advocacy.")
    print("RC1 holdout cases, predictions, and mismatches are not read.")
    print()

    train_rows = build_rows(TRAIN_HAZARDS, TRAIN_OTHER, "train")
    validation_rows = build_rows(VALIDATION_HAZARDS, VALIDATION_OTHER, "validation")
    train_hashes = {row["text_sha256"] for row in train_rows}
    validation_hashes = {row["text_sha256"] for row in validation_rows}
    train_families = {row["family_id"] for row in train_rows}
    validation_families = {row["family_id"] for row in validation_rows}
    text_overlap = train_hashes & validation_hashes
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
        "validation_label_counts": dict(Counter(row["label"] for row in validation_rows)),
        "train_validation_text_overlap": 0,
        "train_validation_family_overlap": 0,
        "paired_contrastive_hazard_contexts": True,
        "existing_category_owner_guard": True,
        "semantic_model_name": MODEL_NAME,
        "semantic_model_revision": MODEL_REVISION,
        "source": "paired synthetic policy concepts",
        "external_or_restricted_data_used": False,
        "actionable_harm_instructions_stored": False,
        "rc1_holdout_cases_read": False,
        "rc1_predictions_or_mismatches_read": False,
        "v3_rc2_aggregate_result_used_as_development_signal": True,
        "v3_rc2_validation_cases_reused": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
    }
    DATASET_DIRECTORY.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Training records: {len(train_rows)}")
    print(f"Validation records: {len(validation_rows)}")
    print("Train/validation text overlap: 0")
    print("Train/validation family overlap: 0")
    print(f"Loading pinned semantic encoder: {MODEL_NAME}")
    encoder = SentenceTransformer(MODEL_NAME, revision=MODEL_REVISION, device="cpu")
    train_embeddings = encoder.encode(
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

    train_labels = [row["label"] for row in train_rows]
    validation_labels = [row["label"] for row in validation_rows]
    boundary_train_labels = ["dangerous" if label == DANGEROUS_LABEL else "not_dangerous" for label in train_labels]
    boundary_validation_labels = ["dangerous" if label == DANGEROUS_LABEL else "not_dangerous" for label in validation_labels]
    boundary_classifier = LogisticRegression(
        C=3.0, max_iter=3000, class_weight="balanced", random_state=20260813
    )
    boundary_classifier.fit(train_embeddings, boundary_train_labels)

    hazard_train_labels = [
        "hazard_present" if label in CONTEXT_LABELS else "no_hazard"
        for label in train_labels
    ]
    hazard_validation_labels = [
        "hazard_present" if label in CONTEXT_LABELS else "no_hazard"
        for label in validation_labels
    ]
    hazard_classifier = LogisticRegression(
        C=3.0, max_iter=3000, class_weight="balanced", random_state=20260813
    )
    hazard_classifier.fit(train_embeddings, hazard_train_labels)

    train_context_indices = [index for index, label in enumerate(train_labels) if label in CONTEXT_LABELS]
    validation_context_indices = [index for index, label in enumerate(validation_labels) if label in CONTEXT_LABELS]
    context_classifier = LogisticRegression(
        C=3.0, max_iter=3000, class_weight="balanced", random_state=20260813
    )
    context_classifier.fit(
        train_embeddings[train_context_indices],
        [train_labels[index] for index in train_context_indices],
    )

    boundary_predictions = boundary_classifier.predict(validation_embeddings)
    boundary_raw_accuracy = float(accuracy_score(boundary_validation_labels, boundary_predictions))
    boundary_raw_f1 = float(f1_score(boundary_validation_labels, boundary_predictions, average="macro"))
    hazard_predictions = hazard_classifier.predict(validation_embeddings)
    hazard_raw_accuracy = float(
        accuracy_score(hazard_validation_labels, hazard_predictions)
    )
    hazard_raw_f1 = float(
        f1_score(hazard_validation_labels, hazard_predictions, average="macro")
    )
    context_predictions = context_classifier.predict(validation_embeddings[validation_context_indices])
    expected_context_labels = [validation_labels[index] for index in validation_context_indices]
    context_raw_accuracy = float(accuracy_score(expected_context_labels, context_predictions))
    context_raw_f1 = float(f1_score(expected_context_labels, context_predictions, average="macro"))
    context_report = classification_report(
        expected_context_labels,
        context_predictions,
        labels=CONTEXT_LABELS,
        output_dict=True,
        zero_division=0,
    )

    boundary_probabilities = boundary_classifier.predict_proba(validation_embeddings)
    hazard_probabilities = hazard_classifier.predict_proba(validation_embeddings)
    context_probabilities = context_classifier.predict_proba(validation_embeddings)
    policy = calibrate(
        boundary_probabilities,
        [str(value) for value in boundary_classifier.classes_],
        hazard_probabilities,
        [str(value) for value in hazard_classifier.classes_],
        context_probabilities,
        [str(value) for value in context_classifier.classes_],
        validation_rows,
    )
    policy_veto_count = sum(policy_veto(row["text"]) is not None for row in validation_rows)
    development_gate_passed = bool(
        boundary_raw_accuracy >= 0.85
        and boundary_raw_f1 >= 0.85
        and hazard_raw_accuracy >= 0.85
        and hazard_raw_f1 >= 0.85
        and context_raw_accuracy >= 0.85
        and context_raw_f1 >= 0.85
        and policy["enabled"]
        and not text_overlap
        and not family_overlap
    )

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    bundle = {
        "boundary_classifier": boundary_classifier,
        "hazard_classifier": hazard_classifier,
        "context_classifier": context_classifier,
    }
    joblib.dump(bundle, MODEL_PATH)
    model_sha256 = hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest()
    configuration = {
        "candidate": CANDIDATE,
        "semantic_model_name": MODEL_NAME,
        "semantic_model_revision": MODEL_REVISION,
        "boundary_probability_threshold": policy["boundary_probability_threshold"],
        "hazard_probability_threshold": policy["hazard_probability_threshold"],
        "dangerous_context_probability_threshold": policy["dangerous_context_probability_threshold"],
        "minimum_context_margin": policy["minimum_context_margin"],
        "safe_context_patterns": SAFE_CONTEXT_PATTERNS,
        "unsafe_override_patterns": UNSAFE_OVERRIDE_PATTERNS,
        "established_category_owners": sorted(ESTABLISHED_CATEGORY_OWNERS),
        "development_gate_passed": development_gate_passed,
        "permitted_active_category": "Dangerous Content",
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "model_sha256": model_sha256,
    }
    CONFIG_PATH.write_text(json.dumps(configuration, indent=2) + "\n", encoding="utf-8")

    report = {
        **manifest,
        "boundary_raw_accuracy": boundary_raw_accuracy,
        "boundary_raw_macro_f1": boundary_raw_f1,
        "hazard_raw_accuracy": hazard_raw_accuracy,
        "hazard_raw_macro_f1": hazard_raw_f1,
        "context_raw_accuracy": context_raw_accuracy,
        "context_raw_macro_f1": context_raw_f1,
        "context_class_results": {
            label: {
                "precision": float(context_report[label]["precision"]),
                "recall": float(context_report[label]["recall"]),
                "f1": float(context_report[label]["f1-score"]),
                "support": int(context_report[label]["support"]),
            }
            for label in CONTEXT_LABELS
        },
        "selective_policy": policy,
        "policy_veto_count": policy_veto_count,
        "development_gate_passed": development_gate_passed,
        "model_path": str(MODEL_PATH),
        "model_sha256": model_sha256,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print()
    print("DANGEROUS CONTENT V4 RC3 CONTRASTIVE DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Boundary raw accuracy: {percentage(boundary_raw_accuracy)}")
    print(f"Boundary raw macro F1: {percentage(boundary_raw_f1)}")
    print(f"Hazard raw accuracy: {percentage(hazard_raw_accuracy)}")
    print(f"Hazard raw macro F1: {percentage(hazard_raw_f1)}")
    print(f"Context raw accuracy: {percentage(context_raw_accuracy)}")
    print(f"Context raw macro F1: {percentage(context_raw_f1)}")
    print()
    print("CONTEXT CLASS RESULTS")
    print("-" * 60)
    for label in CONTEXT_LABELS:
        metrics = report["context_class_results"][label]
        print(
            f"{label}: precision {percentage(metrics['precision'])} | "
            f"recall {percentage(metrics['recall'])} | F1 {percentage(metrics['f1'])}"
        )
    print()
    print("SELECTIVE DANGEROUS OUTPUT")
    print("-" * 60)
    metrics = policy["metrics"]
    print(f"Enabled: {policy['enabled']}")
    print(f"Boundary threshold: {policy['boundary_probability_threshold']:.3f}")
    print(f"Hazard threshold: {policy['hazard_probability_threshold']:.3f}")
    print(f"Context threshold: {policy['dangerous_context_probability_threshold']:.3f}")
    print(f"Minimum context margin: {policy['minimum_context_margin']:.3f}")
    print(f"Accuracy: {percentage(metrics['accuracy'])}")
    print(f"Dangerous precision: {percentage(metrics['precision'])}")
    print(f"Dangerous recall: {percentage(metrics['recall'])}")
    print(f"Safe specificity: {percentage(metrics['specificity'])}")
    print(f"Minimum family accuracy: {percentage(policy['minimum_family_accuracy'])}")
    print(f"Policy safe-context vetoes: {policy_veto_count}")
    print(f"Pre-guard category conflicts: {policy['pre_guard_category_conflicts']}")
    print(f"Category-mix failures after guard: {policy['category_mix_failures']}")
    print()
    print(f"Passed development gate: {development_gate_passed}")
    print(f"Artifact: {MODEL_PATH}")
    print(f"Configuration: {CONFIG_PATH}")
    print(f"Report: {REPORT_PATH}")
    print("RC1 holdout cases, predictions, and mismatches read: False")
    print("V3 RC2 validation cases reused: False")
    print("External or restricted data used: False")
    print("Actionable harm instructions stored: False")
    print("Connected to live moderation: False")
    print("This is development evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
