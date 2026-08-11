from __future__ import annotations

import hashlib
import json
import threading
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from scipy.sparse import csr_matrix, hstack
from sentence_transformers import SentenceTransformer

from app.services.cyberbullying_boundary_service import mask_abusive_terms


REPO_ROOT = Path(__file__).resolve().parents[3]
CANDIDATE_DIRECTORY = (
    REPO_ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "cyberbullying-v2-rc2"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
ARTIFACT_PATH = CANDIDATE_DIRECTORY / "classifier_bundle.joblib"
CONFIG_PATH = CANDIDATE_DIRECTORY / "development_config.json"

LABELS = ("targeted_threat", "abusive_words", "safe_or_other")
NORMAL_CATEGORY = "Normal/Ignore"
CYBER_CATEGORY = "Cyberbullying & Harassment"
ABUSIVE_CATEGORY = "Abusive Words"
UNCERTAIN_CATEGORY = "Uncertain"

_LOAD_LOCK = threading.Lock()
_BUNDLE: dict[str, Any] | None = None
_ENCODER: SentenceTransformer | None = None
_MANIFEST: dict[str, Any] | None = None
_VERDICT: dict[str, Any] | None = None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify_candidate() -> tuple[dict[str, Any], dict[str, Any]]:
    for path in (MANIFEST_PATH, VERDICT_PATH, ARTIFACT_PATH, CONFIG_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required RC2 file was not found: {path}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    verdict = json.loads(VERDICT_PATH.read_text(encoding="utf-8"))
    if manifest.get("candidate") != "cyberbullying-v2-rc2":
        raise RuntimeError("Unexpected cyberbullying RC2 manifest.")
    if verdict.get("candidate") != "cyberbullying-v2-rc2":
        raise RuntimeError("Unexpected cyberbullying RC2 verdict.")
    if verdict.get("status") != "passed_independent_readiness_gate":
        raise RuntimeError("Cyberbullying RC2 has not passed its independent gate.")
    if verdict.get("independently_validated_for_controlled_integration") is not True:
        raise RuntimeError("Cyberbullying RC2 is not approved for controlled integration.")
    if verdict.get("automatic_enforcement_allowed") is not False:
        raise RuntimeError("The RC2 automatic-enforcement contract is invalid.")

    frozen_hashes = manifest.get("frozen_file_hashes", {})
    expected_files = {
        "classifier_bundle.joblib": ARTIFACT_PATH,
        "development_config.json": CONFIG_PATH,
    }
    for name, path in expected_files.items():
        expected = frozen_hashes.get(name)
        if not expected or sha256_file(path) != expected:
            raise RuntimeError(f"Frozen cyberbullying RC2 hash mismatch: {name}")

    return manifest, verdict


def _load_runtime() -> tuple[
    dict[str, Any],
    SentenceTransformer,
    dict[str, Any],
    dict[str, Any],
]:
    global _BUNDLE, _ENCODER, _MANIFEST, _VERDICT
    if all(item is not None for item in (_BUNDLE, _ENCODER, _MANIFEST, _VERDICT)):
        return _BUNDLE, _ENCODER, _MANIFEST, _VERDICT  # type: ignore[return-value]

    with _LOAD_LOCK:
        if not all(
            item is not None for item in (_BUNDLE, _ENCODER, _MANIFEST, _VERDICT)
        ):
            manifest, verdict = _verify_candidate()
            bundle = joblib.load(ARTIFACT_PATH)
            required_bundle_keys = {
                "word_vectorizer",
                "char_vectorizer",
                "lexical_classifier",
                "semantic_classifier",
            }
            if not required_bundle_keys.issubset(bundle):
                raise RuntimeError("The frozen RC2 model bundle is incomplete.")
            encoder = SentenceTransformer(
                str(manifest["embedding_model"]),
                revision=str(manifest["embedding_model_revision"]),
                device="cpu",
            )
            _BUNDLE = bundle
            _ENCODER = encoder
            _MANIFEST = manifest
            _VERDICT = verdict

    return _BUNDLE, _ENCODER, _MANIFEST, _VERDICT  # type: ignore[return-value]


def _aligned(probabilities: np.ndarray, classes: np.ndarray) -> np.ndarray:
    indexes = [list(classes).index(label) for label in LABELS]
    return probabilities[:, indexes]


def get_cyberbullying_rc2_status() -> dict[str, Any]:
    try:
        manifest, verdict = _verify_candidate()
        return {
            "available": True,
            "candidate": manifest["candidate"],
            "independently_validated": True,
            "ready_for_controlled_integration": True,
            "automatic_enforcement_allowed": False,
            "selective_accuracy": verdict["metrics"]["selective_accuracy"],
            "coverage": verdict["metrics"]["coverage"],
        }
    except Exception as error:
        return {
            "available": False,
            "candidate": "cyberbullying-v2-rc2",
            "independently_validated": False,
            "ready_for_controlled_integration": False,
            "automatic_enforcement_allowed": False,
            "error": f"{type(error).__name__}: {error}",
        }


def analyze_cyberbullying_rc2(
    text: str,
    input_sources: list[str] | None = None,
) -> dict[str, Any]:
    value = str(text or "").strip()
    sources = list(input_sources or ["text"])
    base: dict[str, Any] = {
        "available": False,
        "candidate": "cyberbullying-v2-rc2",
        "decision": "not_applied",
        "predicted_label": "",
        "primary_category": "",
        "supporting_categories": [],
        "model_score": 0.0,
        "validated_accepted_precision": 0.0,
        "threshold": 1.0,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "masked_text": value,
        "reason": "The RC2 specialist was not applied.",
        "input_sources": sources,
    }
    if not value:
        base["reason"] = "Empty text was not analyzed."
        return base
    if set(sources) == {"visual_description"}:
        base["reason"] = "A text-only RC2 model cannot analyze visual-only evidence."
        return base

    try:
        bundle, encoder, manifest, verdict = _load_runtime()
        word = bundle["word_vectorizer"].transform([value])
        character = bundle["char_vectorizer"].transform([value])
        lexical_features = hstack((word, character), format="csr")
        lexical = _aligned(
            bundle["lexical_classifier"].predict_proba(lexical_features),
            bundle["lexical_classifier"].classes_,
        )
        embedding = encoder.encode(
            [value],
            batch_size=1,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        semantic = _aligned(
            bundle["semantic_classifier"].predict_proba(csr_matrix(embedding)),
            bundle["semantic_classifier"].classes_,
        )
        probabilities = (
            float(manifest["lexical_weight"]) * lexical
            + float(manifest["semantic_weight"]) * semantic
        )[0]
        index = int(probabilities.argmax())
        label = LABELS[index]
        score = float(probabilities[index])
        threshold_info = manifest["selective_thresholds"][label]
        threshold = float(threshold_info["threshold"])
        accepted = bool(threshold_info.get("enabled", False) and score >= threshold)
        external_metrics = verdict["metrics"]["per_label_selective_results"][label]
        accepted_precision = float(external_metrics["accepted_precision"])

        base.update(
            {
                "available": True,
                "predicted_label": label,
                "model_score": round(score, 4),
                "validated_accepted_precision": round(accepted_precision, 4),
                "threshold": threshold,
                "probabilities": {
                    item: round(float(probabilities[position]), 4)
                    for position, item in enumerate(LABELS)
                },
            }
        )

        if not accepted:
            base.update(
                {
                    "decision": "uncertain",
                    "primary_category": UNCERTAIN_CATEGORY,
                    "human_review_required": True,
                    "reason": (
                        "The RC2 label score did not meet its independently "
                        "validated selective threshold."
                    ),
                }
            )
            return base

        if label == "safe_or_other":
            base.update(
                {
                    "decision": "no_boundary_override",
                    "reason": (
                        "The RC2 specialist found no validated cyberbullying or "
                        "abusive-word boundary. It cannot create an Allow decision."
                    ),
                }
            )
            return base

        if label == "targeted_threat":
            base.update(
                {
                    "decision": "accepted_supporting_evidence",
                    "primary_category": CYBER_CATEGORY,
                    "human_review_required": True,
                    "reason": (
                        "The independently validated RC2 specialist detected "
                        "message-level targeted intimidation evidence."
                    ),
                }
            )
            return base

        base.update(
            {
                "decision": "accepted_supporting_evidence",
                "primary_category": ABUSIVE_CATEGORY,
                "human_review_required": True,
                "masked_text": mask_abusive_terms(value),
                "reason": (
                    "The independently validated RC2 specialist detected abusive "
                    "language without sufficient evidence of repeated harassment."
                ),
            }
        )
        return base
    except Exception as error:
        base["reason"] = "RC2 failed safely and made no moderation change."
        base["error"] = f"{type(error).__name__}: {error}"
        return base


def apply_cyberbullying_rc2_fusion(
    *,
    category: str,
    severity: str,
    action: str,
    confidence: float,
    human_review_required: bool,
    reason: str,
    matched_signals: list[str],
    analysis: dict[str, Any],
    safe_context_confirmed: bool = False,
) -> dict[str, Any]:
    result = {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": confidence,
        "human_review_required": human_review_required,
        "reason": reason,
        "matched_signals": list(matched_signals),
        "decision_applied": False,
        "fusion_status": "not_applied",
    }
    if not analysis.get("available", False):
        result["fusion_status"] = "unavailable"
        return result

    if safe_context_confirmed:
        result["fusion_status"] = "blocked_by_confirmed_safe_context"
        return result

    decision = str(analysis.get("decision", "not_applied"))
    predicted_category = str(analysis.get("primary_category", ""))
    score = float(analysis.get("model_score", 0.0))
    signal = "cyberbullying_rc2:" + str(
        analysis.get("predicted_label", "unknown")
    )

    if decision == "no_boundary_override":
        result["fusion_status"] = "safe_signal_no_override"
        return result

    if decision == "uncertain":
        if category == NORMAL_CATEGORY:
            result.update(
                {
                    "category": UNCERTAIN_CATEGORY,
                    "severity": "Unknown",
                    "action": "Refer to human review",
                    "confidence": round(max(0.50, min(score, 0.69)), 2),
                    "human_review_required": True,
                    "reason": str(analysis["reason"]),
                    "matched_signals": list(dict.fromkeys(matched_signals + [signal])),
                    "decision_applied": True,
                    "fusion_status": "uncertain_referred_to_review",
                }
            )
        else:
            result["fusion_status"] = "uncertain_did_not_override_existing_category"
        return result

    if decision != "accepted_supporting_evidence":
        return result

    if predicted_category == CYBER_CATEGORY:
        allowed = {NORMAL_CATEGORY, ABUSIVE_CATEGORY, CYBER_CATEGORY}
        if category not in allowed:
            result["fusion_status"] = "blocked_by_category_isolation"
            return result
        result.update(
            {
                "category": CYBER_CATEGORY,
                "severity": "High",
                "action": "Refer to human review",
                "confidence": round(score, 2),
                "human_review_required": True,
                "reason": str(analysis["reason"]),
                "matched_signals": list(dict.fromkeys(matched_signals + [signal])),
                "decision_applied": True,
                "fusion_status": "targeted_threat_applied",
            }
        )
        return result

    if predicted_category == ABUSIVE_CATEGORY:
        if category == CYBER_CATEGORY:
            result.update(
                {
                    "human_review_required": True,
                    "matched_signals": list(dict.fromkeys(matched_signals + [signal])),
                    "decision_applied": True,
                    "fusion_status": "abusive_words_support_cyberbullying_primary",
                }
            )
            return result
        if category != NORMAL_CATEGORY and category != ABUSIVE_CATEGORY:
            result["fusion_status"] = "blocked_by_category_isolation"
            return result
        result.update(
            {
                "category": ABUSIVE_CATEGORY,
                "severity": "Medium",
                "action": "Mask abusive terms and refer to human review",
                "confidence": round(score, 2),
                "human_review_required": True,
                "reason": str(analysis["reason"]),
                "matched_signals": list(dict.fromkeys(matched_signals + [signal])),
                "decision_applied": True,
                "fusion_status": "abusive_words_applied",
            }
        )
    return result
