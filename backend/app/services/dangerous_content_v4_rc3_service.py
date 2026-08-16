from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT_DIRECTORY = Path(__file__).resolve().parents[3]
MODEL_DIRECTORY = (
    ROOT_DIRECTORY / "backend" / "storage" / "models" / "dangerous_content_v4_rc3"
)
MODEL_PATH = MODEL_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = MODEL_DIRECTORY / "config.json"

DANGEROUS_LABEL = "dangerous_advocacy"
DANGEROUS_CATEGORY = "Dangerous Content"
DANGEROUS_ACTION = "Remove and send for human review"


def _no_override(
    status: str,
    *,
    available: bool = True,
    predicted_context: str | None = None,
    boundary_probability: float = 0.0,
    hazard_probability: float = 0.0,
    dangerous_context_probability: float = 0.0,
    context_margin: float = 0.0,
    policy_veto: str | None = None,
    warning: str | None = None,
) -> dict[str, Any]:
    result: dict[str, Any] = {
        "available": available,
        "category": None,
        "action": None,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "dangerous_content_v4_rc3_used": False,
        "status": status,
        "predicted_context": predicted_context,
        "boundary_probability": round(float(boundary_probability), 4),
        "hazard_probability": round(float(hazard_probability), 4),
        "dangerous_context_probability": round(
            float(dangerous_context_probability), 4
        ),
        "context_margin": round(float(context_margin), 4),
        "policy_veto": policy_veto,
    }
    if warning:
        result["warning"] = warning
    return result


@lru_cache(maxsize=1)
def _load_runtime() -> tuple[SentenceTransformer, dict[str, Any], dict[str, Any]]:
    if not MODEL_PATH.exists() or not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "Dangerous Content V4 RC3 development artifacts are unavailable."
        )
    configuration = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    bundle = joblib.load(MODEL_PATH)
    encoder = SentenceTransformer(
        configuration["semantic_model_name"],
        revision=configuration["semantic_model_revision"],
        device="cpu",
    )
    return encoder, bundle, configuration


def _policy_veto(text: str, configuration: dict[str, Any]) -> str | None:
    safe_matches = [
        pattern
        for pattern in configuration["safe_context_patterns"]
        if re.search(pattern, text, flags=re.IGNORECASE)
    ]
    if not safe_matches:
        return None

    unsafe_override = any(
        re.search(pattern, text, flags=re.IGNORECASE)
        for pattern in configuration["unsafe_override_patterns"]
    )
    if unsafe_override:
        return None
    return "explicit_warning_prevention_or_professional_control"


def get_dangerous_content_v4_rc3_status() -> dict[str, Any]:
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


def analyze_dangerous_content_v4_rc3(
    text: str,
    *,
    existing_category: str | None = None,
) -> dict[str, Any]:
    normalized_text = " ".join((text or "").split())
    if not normalized_text:
        return _no_override("empty_text_no_override")

    try:
        encoder, bundle, configuration = _load_runtime()
    except Exception as error:
        return _no_override(
            "specialist_unavailable_no_override",
            available=False,
            warning=f"{type(error).__name__}: {error}",
        )

    if not configuration.get("development_gate_passed", False):
        return _no_override("development_gate_not_passed_no_override")

    established_owners = set(configuration["established_category_owners"])
    if existing_category in established_owners:
        result = _no_override("blocked_by_established_category_owner")
        result["existing_category_owner"] = existing_category
        return result

    veto = _policy_veto(normalized_text, configuration)
    if veto:
        return _no_override("policy_safe_context_veto", policy_veto=veto)

    embedding = encoder.encode(
        [normalized_text],
        convert_to_numpy=True,
        normalize_embeddings=True,
        show_progress_bar=False,
    )

    boundary_classifier = bundle["boundary_classifier"]
    hazard_classifier = bundle["hazard_classifier"]
    context_classifier = bundle["context_classifier"]

    boundary_probabilities = np.asarray(
        boundary_classifier.predict_proba(embedding)[0], dtype=float
    )
    boundary_classes = [str(value) for value in boundary_classifier.classes_]
    dangerous_boundary_index = boundary_classes.index("dangerous")
    boundary_probability = float(
        boundary_probabilities[dangerous_boundary_index]
    )

    hazard_probabilities = np.asarray(
        hazard_classifier.predict_proba(embedding)[0], dtype=float
    )
    hazard_classes = [str(value) for value in hazard_classifier.classes_]
    hazard_index = hazard_classes.index("hazard_present")
    hazard_probability = float(hazard_probabilities[hazard_index])

    context_probabilities = np.asarray(
        context_classifier.predict_proba(embedding)[0], dtype=float
    )
    context_classes = [str(value) for value in context_classifier.classes_]
    ranked_indices = np.argsort(context_probabilities)[::-1]
    top_index = int(ranked_indices[0])
    runner_up_index = int(ranked_indices[1])
    predicted_context = context_classes[top_index]
    context_margin = float(
        context_probabilities[top_index] - context_probabilities[runner_up_index]
    )
    dangerous_context_index = context_classes.index(DANGEROUS_LABEL)
    dangerous_context_probability = float(
        context_probabilities[dangerous_context_index]
    )

    accepted = (
        predicted_context == DANGEROUS_LABEL
        and boundary_probability
        >= float(configuration["boundary_probability_threshold"])
        and hazard_probability
        >= float(configuration["hazard_probability_threshold"])
        and dangerous_context_probability
        >= float(configuration["dangerous_context_probability_threshold"])
        and context_margin >= float(configuration["minimum_context_margin"])
    )
    if not accepted:
        return _no_override(
            "dual_evidence_no_dangerous_override",
            predicted_context=predicted_context,
            boundary_probability=boundary_probability,
            hazard_probability=hazard_probability,
            dangerous_context_probability=dangerous_context_probability,
            context_margin=context_margin,
        )

    confidence = min(
        0.94,
        (boundary_probability + dangerous_context_probability) / 2.0,
    )
    return {
        "available": True,
        "category": DANGEROUS_CATEGORY,
        "action": DANGEROUS_ACTION,
        "human_review_required": True,
        "automatic_enforcement_allowed": False,
        "dangerous_content_v4_rc3_used": True,
        "status": "dual_evidence_dangerous_review_only_candidate",
        "predicted_context": predicted_context,
        "confidence": round(confidence, 4),
        "boundary_probability": round(boundary_probability, 4),
        "hazard_probability": round(hazard_probability, 4),
        "dangerous_context_probability": round(
            dangerous_context_probability, 4
        ),
        "context_margin": round(context_margin, 4),
        "policy_veto": None,
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
    }
