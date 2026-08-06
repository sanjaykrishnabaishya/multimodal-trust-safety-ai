from typing import Any

from app.policy_config import (
    ModerationCategory,
    normalize_category_name,
)
from app.services.moderation_service import (
    apply_context_policy,
    moderate_text,
)

from app.services.private_information_service import (
    analyze_private_information,
)

from app.services.identity_impersonation_service import (
    analyze_identity_impersonation,
)
from app.services.rag_service import (
    RAGProcessingError,
    retrieve_evidence,
)
from app.services.sms_spam_model_service import (
    analyze_sms_spam_probability,
)
from app.services.spam_dictionary_service import (
    analyze_spam_signals,
)


MINIMUM_RAG_SIMILARITY = 0.35
STRONG_RAG_SIMILARITY = 0.62
DEFAULT_RAG_RESULTS = 5

NORMAL_CATEGORY = (
    ModerationCategory.NORMAL_IGNORE.value
)

SPAM_CATEGORY = (
    ModerationCategory
    .SPAM_SCAM_PHISHING
    .value
)

CHILD_EXPLOITATION_CATEGORY = (
    ModerationCategory
    .CHILD_EXPLOITATION
    .value
)


SAFE_CONTEXT_SIGNALS = {
    "context:educational_or_reporting",
    "context:category_exception",
    "context:negation_or_condemnation",
}


def safely_normalize_category(
    category: str,
) -> str:
    try:
        return normalize_category_name(
            category
        )

    except (
        ValueError,
        KeyError,
    ):
        return category


def categories_are_equivalent(
    first_category: str,
    second_category: str,
) -> bool:
    if (
        not first_category
        or not second_category
    ):
        return False

    return (
        safely_normalize_category(
            first_category
        )
        ==
        safely_normalize_category(
            second_category
        )
    )


def build_rag_consensus(
    evidence: list[dict],
) -> dict[str, Any]:
    qualified_results = [
        result
        for result in evidence
        if (
            result.get("category")
            and float(
                result.get(
                    "similarity",
                    0.0,
                )
            )
            >= MINIMUM_RAG_SIMILARITY
        )
    ]

    if not qualified_results:
        return {
            "category": "",
            "agreement": 0.0,
            "top_similarity": 0.0,
            "supporting_results": 0,
            "qualified_results": 0,
        }

    category_weights: dict[
        str,
        float,
    ] = {}

    category_counts: dict[
        str,
        int,
    ] = {}

    for result in qualified_results:
        category = (
            safely_normalize_category(
                str(result["category"])
            )
        )

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
        category_weights[
            consensus_category
        ]
        / total_weight
        if total_weight > 0
        else 0.0
    )

    supporting_similarities = [
        float(result["similarity"])
        for result in qualified_results
        if categories_are_equivalent(
            str(result["category"]),
            consensus_category,
        )
    ]

    top_similarity = (
        max(supporting_similarities)
        if supporting_similarities
        else 0.0
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
            category_counts[
                consensus_category
            ]
        ),
        "qualified_results": len(
            qualified_results
        ),
    }


def retrieve_rag_safely(
    text: str,
) -> tuple[
    list[dict],
    str | None,
]:
    try:
        evidence = retrieve_evidence(
            query=text,
            top_k=DEFAULT_RAG_RESULTS,
        )

        return evidence, None

    except RAGProcessingError as exc:
        return [], str(exc)


def apply_spam_dictionary_decision(
    *,
    baseline: dict[str, Any],
    spam_analysis: dict[str, Any],
) -> tuple[
    dict[str, Any],
    bool,
]:
    if not spam_analysis.get(
        "is_likely_spam",
        False,
    ):
        return baseline, False

    baseline_category = (
        safely_normalize_category(
            str(
                baseline.get(
                    "category",
                    NORMAL_CATEGORY,
                )
            )
        )
    )

    if baseline_category not in {
        NORMAL_CATEGORY,
        SPAM_CATEGORY,
    }:
        return baseline, False

    confidence = float(
        spam_analysis.get(
            "confidence",
            0.70,
        )
    )

    signal_groups = set(
        spam_analysis.get(
            "signal_groups",
            [],
        )
    )

    high_risk_groups = {
        "credential_request",
        "money_request",
        "prize_or_return",
    }

    high_risk_detected = bool(
        signal_groups
        & high_risk_groups
    )

    if high_risk_detected:
        severity = "High"
        action = "Block and warn"

        human_review_required = (
            confidence < 0.80
        )

        reason = (
            "Multiple scam or phishing "
            "signals were detected together "
            "with financial, credential, "
            "payment, prize, urgency, contact, "
            "or multilingual evidence."
        )

    else:
        severity = "Medium"

        action = (
            "Limit distribution and warn"
        )

        human_review_required = (
            confidence < 0.72
        )

        reason = (
            "Multiple unsolicited, repetitive, "
            "promotional, urgency, contact, "
            "gibberish, or multilingual spam "
            "signals were detected together."
        )

    baseline_signals = list(
        baseline.get(
            "matched_signals",
            [],
        )
    )

    spam_signals = list(
        spam_analysis.get(
            "matched_signals",
            [],
        )
    )

    updated_baseline = dict(
        baseline
    )

    updated_baseline.update(
        {
            "category": SPAM_CATEGORY,
            "severity": severity,
            "action": action,
            "confidence": confidence,
            "human_review_required": (
                human_review_required
            ),
            "reason": reason,
            "matched_signals": list(
                dict.fromkeys(
                    baseline_signals
                    + spam_signals
                )
            ),
        }
    )

    return updated_baseline, True


def apply_sms_spam_specialist(
    *,
    text: str,
    source_context: str,
    input_sources: list[str],
    baseline: dict[str, Any],
    spam_analysis: dict[str, Any],
) -> tuple[
    dict[str, Any],
    bool,
    dict[str, Any],
]:
    model_analysis = (
        analyze_sms_spam_probability(
            text
        )
    )

    if not model_analysis.get(
        "available",
        False,
    ):
        return (
            baseline,
            False,
            model_analysis,
        )

    spam_probability = float(
        model_analysis.get(
            "spam_probability",
            0.0,
        )
    )

    model_threshold = float(
        model_analysis.get(
            "threshold",
            1.0,
        )
    )

    baseline_category = (
        safely_normalize_category(
            str(
                baseline.get(
                    "category",
                    NORMAL_CATEGORY,
                )
            )
        )
    )

    baseline_signals = list(
        baseline.get(
            "matched_signals",
            [],
        )
    )

    safe_context_detected = any(
        signal
        in SAFE_CONTEXT_SIGNALS
        for signal in baseline_signals
    )

    direct_text_available = any(
        source in input_sources
        for source in (
            "text",
            "extracted_text",
        )
    )

    derived_text_available = any(
        source in input_sources
        for source in (
            "ocr_text",
            "audio_transcript",
        )
    )



    visual_only = (
        "visual_description"
        in input_sources
        and not direct_text_available
        and not derived_text_available
    )

    if visual_only:
        model_analysis[
            "fusion_status"
        ] = (
            "Not applied because the "
            "available evidence is visual-only."
        )

        return (
            baseline,
            False,
            model_analysis,
        )

    required_threshold = (
        model_threshold
    )

    if (
        derived_text_available
        and not direct_text_available
    ):
        required_threshold = max(
            required_threshold,
            0.80,
        )

    dictionary_supports_spam = bool(
        spam_analysis.get(
            "is_likely_spam",
            False,
        )
    )

    rule_supports_spam = (
        baseline_category
        == SPAM_CATEGORY
    )

    another_category_detected = (
        baseline_category
        not in {
            NORMAL_CATEGORY,
            SPAM_CATEGORY,
        }
    )

    if another_category_detected:
        model_analysis[
            "fusion_status"
        ] = (
            "Not applied because another "
            "category has stronger rule evidence."
        )

        return (
            baseline,
            False,
            model_analysis,
        )

    if safe_context_detected:
        model_analysis[
            "fusion_status"
        ] = (
            "Not applied because negation, "
            "reporting, educational, or "
            "exception context was detected."
        )

        return (
            baseline,
            False,
            model_analysis,
        )

    if (
        spam_probability
        < required_threshold
    ):
        model_analysis[
            "fusion_status"
        ] = (
            "Not applied because the spam "
            "probability did not meet the "
            "required threshold."
        )

        model_analysis[
            "required_fusion_threshold"
        ] = round(
            required_threshold,
            4,
        )

        return (
            baseline,
            False,
            model_analysis,
        )

    if (
        derived_text_available
        and not direct_text_available
        and not dictionary_supports_spam
        and not rule_supports_spam
        and spam_probability < 0.90
    ):
        model_analysis[
            "fusion_status"
        ] = (
            "Not applied because OCR or "
            "transcript-only evidence requires "
            "dictionary, rule, or very-high "
            "model support."
        )

        model_analysis[
            "required_fusion_threshold"
        ] = 0.90

        return (
            baseline,
            False,
            model_analysis,
        )

    confidence = min(
        0.98,
        max(
            float(
                baseline.get(
                    "confidence",
                    0.0,
                )
            ),
            spam_probability,
        ),
    )

    specialist_signal = (
        "sms_spam_specialist:"
        f"{spam_probability:.4f}"
    )

    policy = apply_context_policy(
        category=SPAM_CATEGORY,
        source_context=source_context,
        confidence=confidence,
        matched_signals=(
            baseline_signals
            + [specialist_signal]
        ),
    )

    reason = (
        "The calibrated SMS spam specialist "
        "produced a spam probability of "
        f"{spam_probability:.2%}."
    )

    if dictionary_supports_spam:
        reason += (
            " The multilingual spam dictionary "
            "also supports the decision."
        )

    if rule_supports_spam:
        reason += (
            " The policy rule engine also "
            "supports the decision."
        )

    updated_baseline = dict(
        baseline
    )

    updated_baseline.update(
        {
            "category": SPAM_CATEGORY,
            "severity": policy[
                "severity"
            ],
            "action": policy[
                "action"
            ],
            "confidence": round(
                confidence,
                2,
            ),
            "human_review_required": (
                policy[
                    "human_review_required"
                ]
            ),
            "reason": reason,
            "matched_signals": list(
                dict.fromkeys(
                    baseline_signals
                    + [specialist_signal]
                )
            ),
        }
    )

    model_analysis[
        "fusion_status"
    ] = "Applied"

    model_analysis[
        "required_fusion_threshold"
    ] = round(
        required_threshold,
        4,
    )

    return (
        updated_baseline,
        True,
        model_analysis,
    )


def fuse_moderation_decision(
    text: str,
    source_context: str,
    input_sources: list[str],
) -> dict[str, Any]:
    baseline = moderate_text(
        text=text,
        source_context=source_context,
    )


    identity_impersonation_analysis = (
        analyze_identity_impersonation(
            text
        )
    )


    private_information_analysis = (
        analyze_private_information(
            text
        )
    )

    spam_analysis = (
        analyze_spam_signals(
            text
        )
    )

    (
        baseline,
        spam_decision_applied,
    ) = apply_spam_dictionary_decision(
        baseline=baseline,
        spam_analysis=spam_analysis,
    )

    (
        baseline,
        sms_specialist_applied,
        sms_specialist_analysis,
    ) = apply_sms_spam_specialist(
        text=text,
        source_context=source_context,
        input_sources=input_sources,
        baseline=baseline,
        spam_analysis=spam_analysis,
    )

    evidence, rag_error = (
        retrieve_rag_safely(
            text
        )
    )

    rag_used = bool(
        evidence
    )

    consensus = build_rag_consensus(
        evidence
    )

    category = (
        safely_normalize_category(
            str(baseline["category"])
        )
    )

    severity = str(
        baseline["severity"]
    )

    action = str(
        baseline["action"]
    )

    confidence = float(
        baseline["confidence"]
    )

    human_review_required = bool(
        baseline[
            "human_review_required"
        ]
    )

    reason = str(
        baseline["reason"]
    )

    matched_signals = list(
        baseline.get(
            "matched_signals",
            [],
        )
    )

    consensus_category = str(
        consensus["category"]
    )

    agreement = float(
        consensus["agreement"]
    )

    top_similarity = float(
        consensus["top_similarity"]
    )

    rule_detected_category = (
        category != NORMAL_CATEGORY
    )

    rag_has_strong_support = (
        bool(consensus_category)
        and consensus_category
        != NORMAL_CATEGORY
        and top_similarity
        >= STRONG_RAG_SIMILARITY
        and agreement >= 0.55
    )

    rag_supports_decision = (
        rule_detected_category
        and categories_are_equivalent(
            consensus_category,
            category,
        )
    )

    rag_conflicts_with_decision = (
        rule_detected_category
        and bool(consensus_category)
        and not categories_are_equivalent(
            consensus_category,
            category,
        )
        and top_similarity
        >= MINIMUM_RAG_SIMILARITY
    )

    if rag_supports_decision:
        confidence = min(
            0.98,
            confidence
            + (0.08 * agreement),
        )

        reason = (
            f"{reason} Retrieved policy "
            "examples support the "
            f"{category} decision."
        )

    elif (
        rag_conflicts_with_decision
        and not spam_decision_applied
        and not sms_specialist_applied
    ):
        human_review_required = True

        confidence = max(
            0.50,
            confidence - 0.08,
        )

        reason = (
            f"{reason} The policy engine "
            f"selected {category}, while "
            "retrieved examples support "
            f"{consensus_category}. The "
            "result requires additional review."
        )

    elif (
        not rule_detected_category
        and rag_has_strong_support
    ):
        category = (
            consensus_category
        )

        policy = apply_context_policy(
            category=category,
            source_context=source_context,
            confidence=top_similarity,
            matched_signals=[],
        )

        severity = str(
            policy["severity"]
        )

        action = str(
            policy["action"]
        )

        confidence = min(
            0.82,
            max(
                0.60,
                top_similarity
                * agreement,
            ),
        )

        human_review_required = True

        matched_signals.append(
            "rag_consensus:"
            f"{consensus_category}"
        )

        reason = (
            "No sufficiently supported rule "
            "combination was detected, but "
            "similar policy examples support "
            f"{consensus_category}. Additional "
            "review is required before enforcement."
        )

    elif (
        category == NORMAL_CATEGORY
        and consensus_category
        == NORMAL_CATEGORY
    ):
        confidence = min(
            0.90,
            confidence
            + (0.08 * agreement),
        )

        reason = (
            f"{reason} Retrieved normal-content "
            "examples also support allowing "
            "the content."
        )

    safe_context_detected = any(
        signal in SAFE_CONTEXT_SIGNALS
        for signal in matched_signals
    )

    direct_action_detected = (
        "context:direct_action"
        in matched_signals
    )

    if (
        category == SPAM_CATEGORY
        and safe_context_detected
        and not direct_action_detected
        and not sms_specialist_applied
    ):
        category = NORMAL_CATEGORY
        severity = "None"
        action = "Allow"

        confidence = max(
            0.75,
            min(
                confidence,
                0.90,
            ),
        )

        human_review_required = False

        reason = (
            "Spam-related terms were mentioned "
            "in a negated, educational, reporting, "
            "warning, or preventative context. "
            "No direct request to send money, "
            "credentials, passwords, or OTPs "
            "was detected."
        )

        matched_signals.append(
            "fusion:safe_context_override"
        )

    private_information_detected = bool(
        private_information_analysis.get(
            "pii_detected",
            False,
        )
    )

    if private_information_detected:
        private_category = str(
            private_information_analysis.get(
                "category",
                "Publishing Private Information",
            )
        )

        private_confidence = float(
            private_information_analysis.get(
                "confidence",
                0.70,
            )
        )

        private_reason = str(
            private_information_analysis.get(
                "reason",
                (
                    "Actionable private information "
                    "was detected."
                ),
            )
        )

        private_signal = (
            "private_information:"
            + ",".join(
                private_information_analysis.get(
                    "information_types",
                    [],
                )
            )
        )

        matched_signals.append(
            private_signal
        )

        if category == NORMAL_CATEGORY:
            category = private_category
            severity = "High"
            action = "Refer to human review"

            confidence = max(
                confidence,
                private_confidence,
            )

            human_review_required = True
            reason = private_reason

        else:
            human_review_required = True

            reason = (
                f"{reason} Actionable private "
                "information was also detected. "
                "Human review is required before "
                "any final enforcement decision."
            )


    identity_impersonation_detected = bool(
        identity_impersonation_analysis.get(
            "detected",
            False,
        )
    )

    if identity_impersonation_detected:
        identity_category = str(
            identity_impersonation_analysis.get(
                "category",
                (
                    "Identity Theft & "
                    "Impersonation"
                ),
            )
        )

        identity_confidence = min(
            0.75,
            float(
                identity_impersonation_analysis.get(
                    "confidence",
                    0.60,
                )
            ),
        )

        identity_signal = (
            "identity_impersonation:"
            + ",".join(
                identity_impersonation_analysis.get(
                    "explicit_signals",
                    [],
                )
                + identity_impersonation_analysis.get(
                    "identity_claim_signals",
                    [],
                )
            )
        )

        matched_signals.append(
            identity_signal
        )

        identity_overlaps_with_scam = bool(
            identity_impersonation_analysis.get(
                "scam_overlap_detected",
                False,
            )
        )

        if category == NORMAL_CATEGORY:
            category = identity_category
            severity = "High"
            action = "Refer to human review"
            confidence = identity_confidence
            human_review_required = True

            reason = (
                "Text signals suggest possible "
                "identity theft or impersonation. "
                "The text-only specialist failed "
                "its independent recall target, so "
                "this is supporting evidence only. "
                "Human review must verify identity "
                "ownership, authorization, deception, "
                "and parody status."
            )

        elif (
            category == SPAM_CATEGORY
            and identity_overlaps_with_scam
        ):
            human_review_required = True

            reason = (
                f"{reason} Possible impersonation "
                "signals were also detected, but "
                "Spam, Scam & Phishing remains the "
                "primary category because the content "
                "requests credentials, money, payment, "
                "or verification."
            )

        else:
            human_review_required = True

            reason = (
                f"{reason} Supporting identity-"
                "impersonation signals were also "
                "detected. Human review is required."
            )

    visual_only = (
        "visual_description"
        in input_sources
        and "text"
        not in input_sources
        and "extracted_text"
        not in input_sources
        and "ocr_text"
        not in input_sources
        and "audio_transcript"
        not in input_sources
    )

    if (
        visual_only
        and category != NORMAL_CATEGORY
    ):
        confidence = min(
            confidence,
            0.75,
        )

        human_review_required = True

        reason = (
            f"{reason} The decision relies "
            "only on a general visual "
            "description."
        )

    if category == (
        CHILD_EXPLOITATION_CATEGORY
    ):
        severity = "Critical"

        action = (
            "Block and immediately escalate"
        )

        human_review_required = True

    decision_sources = list(
        dict.fromkeys(
            input_sources
            + ["rule_engine"]
            + (
                ["private_information_detector"]
                if private_information_detected
                else []
            )
            + (
                ["identity_impersonation_detector"]
                if identity_impersonation_detected
                else []
            )
            + (
                ["spam_dictionary"]
                if spam_analysis.get(
                    "dictionary_matches"
                )
                else []
            )
            + (
                ["sms_spam_specialist"]
                if sms_specialist_applied
                else []
            )
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

    if (
        spam_analysis.get(
            "dictionary_matches"
        )
        and not spam_decision_applied
    ):
        warnings.append(
            "Multilingual spam dictionary "
            "terms were detected, but the "
            "combined contextual evidence "
            "did not meet the automatic "
            "spam threshold."
        )

    if (
        spam_decision_applied
        and rag_conflicts_with_decision
    ):
        warnings.append(
            "RAG evidence conflicts with the "
            "context-supported spam decision."
        )

    return {
        "category": (
            safely_normalize_category(
                category
            )
        ),
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
        "matched_signals": (
            matched_signals
        ),
        "decision_sources": (
            decision_sources
        ),
        "identity_impersonation_detector_used": (
            identity_impersonation_detected
        ),
        "identity_impersonation": (
            identity_impersonation_analysis
        ),
        "private_information_detector_used": (
            private_information_detected
        ),
        "private_information": (
            private_information_analysis
        ),

        "sms_spam_specialist_used": (
            sms_specialist_applied
        ),
        "sms_spam_specialist": (
            sms_specialist_analysis
        ),
        "rag_used": rag_used,
        "rag_consensus": consensus,
        "retrieved_evidence": evidence,
        "fusion_warnings": warnings,
    }