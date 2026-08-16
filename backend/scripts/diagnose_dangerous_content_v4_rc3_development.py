from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
VALIDATION_PATH = (
    ROOT_DIRECTORY
    / "datasets"
    / "development"
    / "dangerous_content_v4_rc3"
    / "validation.csv"
)
MODEL_DIRECTORY = (
    ROOT_DIRECTORY / "backend" / "storage" / "models" / "dangerous_content_v4_rc3"
)
MODEL_PATH = MODEL_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "config.json"
REPORT_PATH = (
    ROOT_DIRECTORY
    / "reports"
    / "evaluation"
    / "dangerous_content"
    / "v4_rc3_contrastive_development"
    / "family_diagnostic.json"
)

DANGEROUS_LABEL = "dangerous_advocacy"


def policy_veto(text: str, configuration: dict[str, Any]) -> bool:
    safe = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in configuration["safe_context_patterns"]
    )
    if not safe:
        return False
    unsafe = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in configuration["unsafe_override_patterns"]
    )
    return not unsafe


def main() -> None:
    if not VALIDATION_PATH.exists() or not MODEL_PATH.exists() or not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "Run the V4 RC3 contrastive development trainer before this diagnostic."
        )

    with VALIDATION_PATH.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    bundle = joblib.load(MODEL_PATH)

    print("DANGEROUS CONTENT V4 RC3 DEVELOPMENT FAMILY DIAGNOSTIC")
    print("=" * 60)
    print("Only development family identifiers and aggregate scores are shown.")
    print("No raw text is printed or stored. No holdout is opened.")
    print()

    encoder = SentenceTransformer(
        configuration["semantic_model_name"],
        revision=configuration["semantic_model_revision"],
        device="cpu",
    )
    embeddings = encoder.encode(
        [row["text"] for row in rows],
        batch_size=32,
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=True,
    )

    boundary_classifier = bundle["boundary_classifier"]
    hazard_classifier = bundle["hazard_classifier"]
    context_classifier = bundle["context_classifier"]
    boundary_probabilities = boundary_classifier.predict_proba(embeddings)
    boundary_classes = [str(value) for value in boundary_classifier.classes_]
    boundary_danger_index = boundary_classes.index("dangerous")
    boundary_scores = boundary_probabilities[:, boundary_danger_index]

    hazard_probabilities = hazard_classifier.predict_proba(embeddings)
    hazard_classes = [str(value) for value in hazard_classifier.classes_]
    hazard_index = hazard_classes.index("hazard_present")
    hazard_scores = hazard_probabilities[:, hazard_index]

    context_probabilities = context_classifier.predict_proba(embeddings)
    context_classes = [str(value) for value in context_classifier.classes_]
    context_danger_index = context_classes.index(DANGEROUS_LABEL)
    context_scores = context_probabilities[:, context_danger_index]
    context_top_indices = np.argmax(context_probabilities, axis=1)
    context_sorted = np.sort(context_probabilities, axis=1)
    context_margins = context_sorted[:, -1] - context_sorted[:, -2]

    owner_set = set(configuration["established_category_owners"])
    family_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for index, row in enumerate(rows):
        vetoed = policy_veto(row["text"], configuration)
        owner_guarded = row["existing_category"] in owner_set
        accepted = bool(
            boundary_scores[index]
            >= float(configuration["boundary_probability_threshold"])
            and hazard_scores[index]
            >= float(configuration["hazard_probability_threshold"])
            and context_top_indices[index] == context_danger_index
            and context_scores[index]
            >= float(configuration["dangerous_context_probability_threshold"])
            and context_margins[index]
            >= float(configuration["minimum_context_margin"])
            and not vetoed
            and not owner_guarded
        )
        expected = row["label"] == DANGEROUS_LABEL
        family_rows[row["family_id"]].append(
            {
                "correct": accepted == expected,
                "accepted": accepted,
                "expected_dangerous": expected,
                "vetoed": vetoed,
                "owner_guarded": owner_guarded,
                "predicted_context": context_classes[int(context_top_indices[index])],
                "boundary_probability": float(boundary_scores[index]),
                "hazard_probability": float(hazard_scores[index]),
                "dangerous_context_probability": float(context_scores[index]),
                "context_margin": float(context_margins[index]),
            }
        )

    summaries: list[dict[str, Any]] = []
    for family_id, values in sorted(family_rows.items()):
        correct = sum(bool(value["correct"]) for value in values)
        if correct == len(values):
            continue
        summaries.append(
            {
                "family_id": family_id,
                "records": len(values),
                "correct": correct,
                "expected_dangerous": bool(values[0]["expected_dangerous"]),
                "accepted_as_dangerous": sum(
                    bool(value["accepted"]) for value in values
                ),
                "policy_vetoed": sum(bool(value["vetoed"]) for value in values),
                "owner_guarded": sum(
                    bool(value["owner_guarded"]) for value in values
                ),
                "predicted_context_counts": dict(
                    Counter(value["predicted_context"] for value in values)
                ),
                "boundary_probability_min": round(
                    min(value["boundary_probability"] for value in values), 4
                ),
                "boundary_probability_max": round(
                    max(value["boundary_probability"] for value in values), 4
                ),
                "dangerous_context_probability_min": round(
                    min(value["dangerous_context_probability"] for value in values), 4
                ),
                "hazard_probability_min": round(
                    min(value["hazard_probability"] for value in values), 4
                ),
                "hazard_probability_max": round(
                    max(value["hazard_probability"] for value in values), 4
                ),
                "dangerous_context_probability_max": round(
                    max(value["dangerous_context_probability"] for value in values), 4
                ),
                "context_margin_min": round(
                    min(value["context_margin"] for value in values), 4
                ),
                "context_margin_max": round(
                    max(value["context_margin"] for value in values), 4
                ),
            }
        )

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "candidate": configuration["candidate"],
        "validation_records": len(rows),
        "imperfect_family_count": len(summaries),
        "imperfect_families": summaries,
        "raw_text_stored_or_printed": False,
        "holdout_opened": False,
        "live_moderation_changed": False,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"Validation records: {len(rows)}")
    print(f"Imperfect families: {len(summaries)}")
    print()
    for summary in summaries:
        print(
            f"{summary['family_id']}: {summary['correct']}/{summary['records']} correct | "
            f"accepted dangerous: {summary['accepted_as_dangerous']} | "
            f"contexts: {summary['predicted_context_counts']}"
        )
        print(
            "  boundary probability: "
            f"{summary['boundary_probability_min']:.4f}-"
            f"{summary['boundary_probability_max']:.4f} | "
            "hazard probability: "
            f"{summary['hazard_probability_min']:.4f}-"
            f"{summary['hazard_probability_max']:.4f} | "
            "danger context: "
            f"{summary['dangerous_context_probability_min']:.4f}-"
            f"{summary['dangerous_context_probability_max']:.4f} | "
            "margin: "
            f"{summary['context_margin_min']:.4f}-"
            f"{summary['context_margin_max']:.4f}"
        )
    print()
    print(f"Report: {REPORT_PATH}")
    print("Raw text stored or printed: False")
    print("Independent holdout opened: False")
    print("Live moderation changed: False")


if __name__ == "__main__":
    main()
