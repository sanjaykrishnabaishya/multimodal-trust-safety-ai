from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT_DIRECTORY = Path(__file__).resolve().parents[3]
MODEL_DIRECTORY = (
    ROOT_DIRECTORY / "backend" / "storage" / "models" / "dangerous_content_v3_rc2"
)
MODEL_PATH = MODEL_DIRECTORY / "classifier.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "config.json"

DANGEROUS_CATEGORY = "Dangerous Content"
DANGEROUS_ACTION = "Remove and send for human review"


def _no_override(
    *,
    status: str,
    available: bool,
    predicted_label: str | None = None,
    confidence: float = 0.0,
    dangerous_probability: float = 0.0,
    score_margin: float = 0.0,
    warning: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": available,
        "category": None,
        "action": None,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "dangerous_content_v3_rc2_used": False,
        "status": status,
        "predicted_label": predicted_label,
        "confidence": round(float(confidence), 4),
        "dangerous_probability": round(float(dangerous_probability), 4),
        "score_margin": round(float(score_margin), 4),
    }
    if warning:
        result["warning"] = warning
    return result


@lru_cache(maxsize=1)
def _load_runtime() -> tuple[SentenceTransformer, Any, dict[str, Any]]:
    if not MODEL_PATH.exists() or not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "Dangerous Content V3 RC2 development artifacts are unavailable."
        )

    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    classifier = joblib.load(MODEL_PATH)
    encoder = SentenceTransformer(
        configuration["semantic_model_name"],
        revision=configuration["semantic_model_revision"],
        device="cpu",
    )
    return encoder, classifier, configuration


def get_dangerous_content_v3_rc2_status() -> dict[str, Any]:
    try:
        _, _, configuration = _load_runtime()
    except Exception as error:
        return {
            "available": False,
            "development_gate_passed": False,
            "connected_to_live_moderation": False,
            "automatic_enforcement_allowed": False,
            "error": f"{type(error).__name__}: {error}",
        }

    return {
        "available": True,
        "candidate": configuration["candidate"],
        "development_gate_passed": bool(
            configuration.get("development_gate_passed", False)
        ),
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "permitted_active_category": DANGEROUS_CATEGORY,
    }


def analyze_dangerous_content_v3_rc2(text: str) -> dict[str, Any]:
    normalized_text = " ".join((text or "").split())
    if not normalized_text:
        return _no_override(status="empty_text_no_override", available=True)

    try:
        encoder, classifier, configuration = _load_runtime()
    except Exception as error:
        return _no_override(
            status="specialist_unavailable_no_override",
            available=False,
            warning=f"{type(error).__name__}: {error}",
        )

    if not configuration.get("development_gate_passed", False):
        return _no_override(
            status="development_gate_not_passed_no_override",
            available=True,
        )

    embedding = encoder.encode(
        [normalized_text],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    probabilities = np.asarray(classifier.predict_proba(embedding)[0], dtype=float)
    class_names = [str(value) for value in classifier.classes_]

    ranked_indices = np.argsort(probabilities)[::-1]
    top_index = int(ranked_indices[0])
    runner_up_index = int(ranked_indices[1])
    predicted_label = class_names[top_index]
    confidence = float(probabilities[top_index])
    score_margin = confidence - float(probabilities[runner_up_index])

    dangerous_label = configuration["dangerous_label"]
    dangerous_index = class_names.index(dangerous_label)
    dangerous_probability = float(probabilities[dangerous_index])
    threshold = float(configuration["dangerous_probability_threshold"])
    minimum_margin = float(configuration["minimum_score_margin"])

    accepted = (
        predicted_label == dangerous_label
        and dangerous_probability >= threshold
        and score_margin >= minimum_margin
    )
    if not accepted:
        return _no_override(
            status="semantic_no_dangerous_override",
            available=True,
            predicted_label=predicted_label,
            confidence=confidence,
            dangerous_probability=dangerous_probability,
            score_margin=score_margin,
        )

    return {
        "available": True,
        "category": DANGEROUS_CATEGORY,
        "action": DANGEROUS_ACTION,
        "human_review_required": True,
        "automatic_enforcement_allowed": False,
        "dangerous_content_v3_rc2_used": True,
        "status": "dangerous_content_review_only_candidate",
        "predicted_label": predicted_label,
        "confidence": round(min(confidence, 0.94), 4),
        "raw_confidence": round(confidence, 4),
        "dangerous_probability": round(dangerous_probability, 4),
        "score_margin": round(score_margin, 4),
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
    }

