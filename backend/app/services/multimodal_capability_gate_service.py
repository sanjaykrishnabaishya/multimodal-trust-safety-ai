from __future__ import annotations

from copy import deepcopy
from typing import Any


NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"
VIOLENT_CATEGORY = "Violent Content"
VISUAL_CONTENT_TYPES = {"image", "video"}
GATE_VERSION = "visual-safety-gate-v1"
VIOLENT_READINESS_GATE_VERSION = "violent-content-v2-rc1-retirement-gate-v1"


def get_multimodal_capability_status() -> dict[str, Any]:
    return {
        "gate_version": GATE_VERSION,
        "text_violent_content_candidate": "violent-content-v2-rc1",
        "text_violent_content_independently_validated": False,
        "text_violent_content_candidate_status": "failed-independent-holdout",
        "text_violent_content_holdout": {
            "records": 100,
            "accuracy_percent": 88.0,
            "recall_percent": 70.0,
            "f1_percent": 82.35,
            "exact_category_action_accuracy_percent": 77.0,
            "passed_readiness_gate": False,
        },
        "visual_description_available": True,
        "visual_violence_independently_validated": False,
        "video_temporal_violence_independently_validated": False,
        "automatic_visual_safety_confirmation_allowed": False,
        "failed_development_candidates": [
            {
                "candidate": "jaranohaal/vit-base-violence-detection",
                "best_accuracy_percent": 60.0,
                "violence_recall_percent": 40.0,
                "status": "rejected",
            },
            {
                "candidate": (
                    "mostafaalazzaly/"
                    "aleris-violence-detector-x3d-resnet18"
                ),
                "status": "rejected-incomplete-preprocessing-contract",
            },
        ],
    }


def apply_violent_content_readiness_gate(
    *,
    decision: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    updated = deepcopy(decision)
    if str(updated.get("category", "")).strip() != VIOLENT_CATEGORY:
        return updated, []

    previous_action = str(updated.get("action", "")).strip()
    updated["action"] = "Refer to human review"
    updated["human_review_required"] = True
    updated["confidence"] = min(
        float(updated.get("confidence", 0.75)),
        0.75,
    )
    updated["reason"] = (
        f"{str(updated.get('reason', '')).strip()} "
        "The frozen Violent Content V2 RC1 candidate did not pass its "
        "independent readiness gate, so this result is supporting evidence "
        "only and requires human review."
    ).strip()
    updated["recommended_action_before_readiness_gate"] = previous_action
    updated["violent_content_candidate_status"] = "failed-independent-holdout"
    updated["automatic_enforcement_allowed"] = False

    matched_signals = list(updated.get("matched_signals", []))
    matched_signals.append("violent_content_v2_rc1_not_ready")
    updated["matched_signals"] = list(dict.fromkeys(matched_signals))

    decision_sources = list(updated.get("decision_sources", []))
    decision_sources.append(VIOLENT_READINESS_GATE_VERSION)
    updated["decision_sources"] = list(dict.fromkeys(decision_sources))

    return updated, [
        "Violent Content V2 RC1 failed its independent readiness gate. "
        "The category is supporting evidence only; no automatic enforcement "
        "or automatic allowance is permitted."
    ]


def apply_multimodal_capability_gate(
    *,
    decision: dict[str, Any],
    content_type: str,
) -> tuple[dict[str, Any], list[str]]:
    updated = deepcopy(decision)
    normalized_content_type = str(content_type).strip().casefold()

    if normalized_content_type not in VISUAL_CONTENT_TYPES:
        return updated, []

    if str(updated.get("category", "")).strip() != NORMAL_CATEGORY:
        return updated, []

    updated["category"] = UNCERTAIN_CATEGORY
    updated["severity"] = "Unknown"
    updated["action"] = "Refer to human review"
    updated["confidence"] = min(
        float(updated.get("confidence", 0.5)),
        0.5,
    )
    updated["human_review_required"] = True
    updated["reason"] = (
        "No violation was found in the extracted text, OCR, transcript, or "
        "general visual description. However, TrustScopeAI does not yet have "
        "an independently validated visual violence detector, so visual "
        "safety cannot be confirmed automatically."
    )

    matched_signals = list(updated.get("matched_signals", []))
    matched_signals.append("visual_safety_not_independently_validated")
    updated["matched_signals"] = list(dict.fromkeys(matched_signals))

    decision_sources = list(updated.get("decision_sources", []))
    decision_sources.append(GATE_VERSION)
    updated["decision_sources"] = list(dict.fromkeys(decision_sources))
    updated["visual_safety_gate_applied"] = True
    updated["automatic_visual_safety_confirmation_allowed"] = False

    warnings = [
        "Visual violence detection is not independently validated. This "
        "image or video cannot be automatically confirmed as safe."
    ]
    return updated, warnings
