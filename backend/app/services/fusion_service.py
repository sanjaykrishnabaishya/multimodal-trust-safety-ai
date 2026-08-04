from typing import Any

from app.services.moderation_service import (
    apply_context_policy,
    moderate_text,
)
from app.services.rag_service import (
    RAGProcessingError,
    retrieve_evidence,
)


MINIMUM_RAG_SIMILARITY = 0.35
STRONG_RAG_SIMILARITY = 0.62
DEFAULT_RAG_RESULTS = 5


def build_rag_consensus(
    evidence: list[dict],
) -> dict[str, Any]:
    qualified = [
        result
        for result in evidence
        if (
            result.get("category")
            and result.get("similarity", 0)
            >= MINIMUM_RAG_SIMILARITY
        )
    ]

    if not qualified:
        return {
            "category": "",
            "agreement": 0.0,
            "top_similarity": 0.0,
            "supporting_results": 0,
            "qualified_results": 0,
        }

    category_weights: dict[str, float] = {}
    category_counts: dict[str, int] = {}

    for result in qualified:
        category = result["category"]
        similarity = float(
            result["similarity"]
        )

        category_weights[category] = (
            category_weights.get(
                category,
                0.0,
            )
            + similarity
        )

        category_counts[category] = (
            category_counts.get(
                category,
                0,
            )
            + 1
        )

    consensus_category = max(
        category_weights,
        key=category_weights.get,
    )

    total_weight = sum(
        category_weights.values()
    )

    agreement = (
        category_weights[consensus_category]
        / total_weight
        if total_weight > 0
        else 0.0
    )

    top_similarity = max(
        float(result["similarity"])
        for result in qualified
        if (
            result["category"]
            == consensus_category
        )
    )

    return {
        "category": consensus_category,
        "agreement": round(
            agreement,
            4,
        ),
        "top_similarity": round(
            top_similarity,
            4,
        ),
        "supporting_results": (
            category_counts[consensus_category]
        ),
        "qualified_results": len(
            qualified
        ),
    }


def retrieve_rag_safely(
    text: str,
) -> tuple[list[dict], str | None]:
    try:
        evidence = retrieve_evidence(
            query=text,
            top_k=DEFAULT_RAG_RESULTS,
        )

        return evidence, None

    except RAGProcessingError as exc:
        return [], str(exc)


def fuse_moderation_decision(
    text: str,
    source_context: str,
    input_sources: list[str],
) -> dict:
    baseline = moderate_text(
        text=text,
        source_context=source_context,
    )

    evidence, rag_error = retrieve_rag_safely(
        text
    )

    rag_used = bool(evidence)
    consensus = build_rag_consensus(
        evidence
    )

    category = baseline["category"]
    severity = baseline["severity"]
    action = baseline["action"]
    confidence = float(
        baseline["confidence"]
    )
    human_review_required = bool(
        baseline["human_review_required"]
    )
    reason = baseline["reason"]
    matched_signals = list(
        baseline["matched_signals"]
    )

    consensus_category = consensus[
        "category"
    ]
    agreement = float(
        consensus["agreement"]
    )
    top_similarity = float(
        consensus["top_similarity"]
    )

    rule_detected_category = (
        category != "Normal/Ignore"
    )

    rag_has_strong_support = (
        consensus_category
        and consensus_category
        != "Normal/Ignore"
        and top_similarity
        >= STRONG_RAG_SIMILARITY
        and agreement >= 0.55
    )

    if (
        rule_detected_category
        and consensus_category == category
    ):
        confidence = min(
            0.98,
            confidence
            + (0.08 * agreement),
        )

        reason = (
            f"{reason} Retrieved policy examples "
            f"support the {category} decision."
        )

    elif (
        rule_detected_category
        and consensus_category
        and consensus_category
        != category
        and top_similarity
        >= MINIMUM_RAG_SIMILARITY
    ):
        human_review_required = True
        confidence = max(
            0.50,
            confidence - 0.08,
        )

        reason = (
            f"{reason} The rule engine selected "
            f"{category}, while retrieved examples "
            f"most strongly support "
            f"{consensus_category}. Human review "
            f"is required."
        )

    elif (
        not rule_detected_category
        and rag_has_strong_support
    ):
        category = consensus_category

        policy = apply_context_policy(
            category=category,
            source_context=source_context,
            confidence=top_similarity,
            matched_signals=[],
        )

        severity = policy["severity"]
        action = policy["action"]

        confidence = min(
            0.82,
            max(
                0.60,
                top_similarity * agreement,
            ),
        )

        human_review_required = True

        matched_signals.append(
            f"rag_consensus:{category}"
        )

        reason = (
            "No exact rule phrase was detected, "
            f"but semantically similar policy "
            f"examples support the {category} "
            f"category. Human review is required "
            f"before enforcement."
        )

    elif (
        category == "Normal/Ignore"
        and consensus_category
        == "Normal/Ignore"
    ):
        confidence = min(
            0.90,
            confidence
            + (0.08 * agreement),
        )

        reason = (
            f"{reason} Retrieved normal-content "
            f"examples support allowing the content."
        )

    visual_only = (
        "visual_description" in input_sources
        and "text" not in input_sources
        and "extracted_text" not in input_sources
        and "ocr_text" not in input_sources
        and "audio_transcript" not in input_sources
    )

    if (
        visual_only
        and category != "Normal/Ignore"
    ):
        confidence = min(
            confidence,
            0.75,
        )
        human_review_required = True

        reason = (
            f"{reason} The decision relies only "
            f"on a general visual description, "
            f"so human review is required."
        )

    if category in {
        "Child Abuse",
    }:
        severity = "Critical"
        action = "Block and escalate"
        human_review_required = True

    decision_sources = list(
        dict.fromkeys(
            input_sources
            + ["rule_engine"]
            + (
                ["rag"]
                if rag_used
                else []
            )
        )
    )

    warnings: list[str] = []

    if rag_error:
        warnings.append(
            f"RAG warning: {rag_error}"
        )

    return {
        "category": category,
        "severity": severity,
        "action": action,
        "confidence": round(
            confidence,
            2,
        ),
        "human_review_required": (
            human_review_required
        ),
        "reason": reason,
        "matched_signals": matched_signals,
        "decision_sources": (
            decision_sources
        ),
        "rag_used": rag_used,
        "rag_consensus": consensus,
        "retrieved_evidence": evidence,
        "fusion_warnings": warnings,
    }