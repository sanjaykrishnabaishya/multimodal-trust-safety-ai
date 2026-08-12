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
from app.services.targeted_threat_service import (
    analyze_targeted_threat,
)
from app.services.cyberbullying_rc2_service import (
    analyze_cyberbullying_rc2,
    apply_cyberbullying_rc2_fusion,
)
from app.services.hate_speech_v7_service import (
    analyze_hate_speech_v7,
    apply_hate_speech_v7_fusion,
)
from app.services.religiously_offensive_v7_rc6_fusion import (
    analyze_religiously_offensive_v7_rc6_for_fusion,
    apply_religiously_offensive_v7_rc6_fusion,
)
from app.services.violent_content_service import (
    analyze_violent_content,
)
from app.services.fact_check_fusion_service import (
    analyze_fact_check_for_fusion,
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


    violent_content_analysis = analyze_violent_content(text)
    targeted_threat_analysis = analyze_targeted_threat(text)
    cyberbullying_rc2_analysis = analyze_cyberbullying_rc2(
        text,
        input_sources,
    )
    hate_speech_v7_analysis = analyze_hate_speech_v7(
        text,
        input_sources,
    )
    religiously_offensive_v7_rc6_analysis = (
        analyze_religiously_offensive_v7_rc6_for_fusion(
            text,
            input_sources,
        )
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

    violent_content_detected = bool(
        violent_content_analysis.get("detected", False)
    )
    violent_content_safe_override = bool(
        violent_content_analysis.get("safe_override_allowed", False)
    )
    violent_content_decision_applied = False

    if violent_content_safe_override and category == "Violent Content":
        category = NORMAL_CATEGORY
        severity = "None"
        action = "Allow"
        confidence = max(0.78, min(confidence, 0.90))
        human_review_required = False
        reason = str(violent_content_analysis.get("reason", reason))
        matched_signals.append(
            "violent_content_specialist:safe_context_override"
        )
        violent_content_decision_applied = True

    if violent_content_detected:
        violence_category = str(
            violent_content_analysis.get("category", "Violent Content")
        )
        violence_signal = (
            "violent_content_specialist:"
            + str(violent_content_analysis.get("decision_type", "detected"))
        )
        matched_signals.append(violence_signal)

        if category in {NORMAL_CATEGORY, violence_category}:
            category = violence_category
            severity = str(violent_content_analysis.get("severity", "High"))
            action = str(
                violent_content_analysis.get("action", "Refer to human review")
            )
            confidence = max(
                confidence,
                float(violent_content_analysis.get("confidence", 0.75)),
            )
            human_review_required = bool(
                violent_content_analysis.get("human_review_required", True)
            )
            reason = str(violent_content_analysis.get("reason", reason))
            violent_content_decision_applied = True
        else:
            human_review_required = True
            reason = (
                f"{reason} The violence specialist also found supporting "
                "evidence, but it did not replace the existing primary category."
            )

    targeted_threat_detected = bool(
        targeted_threat_analysis.get("detected", False)
    )
    targeted_threat_boundary_applied = False

    if targeted_threat_detected:
        threat_category = str(
            targeted_threat_analysis.get(
                "category", "Cyberbullying & Harassment"
            )
        )
        matched_signals.append(
            "targeted_threat_boundary:targeted_intimidation"
        )

        if category in {
            NORMAL_CATEGORY,
            "Violent Content",
            threat_category,
        }:
            category = threat_category
            severity = str(targeted_threat_analysis.get("severity", "High"))
            action = str(
                targeted_threat_analysis.get(
                    "action", "Limit, flag, and send for human review"
                )
            )
            confidence = max(
                confidence,
                float(targeted_threat_analysis.get("confidence", 0.85)),
            )
            human_review_required = True
            reason = str(targeted_threat_analysis.get("reason", reason))
            targeted_threat_boundary_applied = True
        else:
            human_review_required = True
            reason = (
                f"{reason} Targeted physical-intimidation evidence was also "
                "detected, but it did not replace the existing primary category."
            )

    cyberbullying_rc2_fusion = apply_cyberbullying_rc2_fusion(
        category=category,
        severity=severity,
        action=action,
        confidence=confidence,
        human_review_required=human_review_required,
        reason=reason,
        matched_signals=matched_signals,
        analysis=cyberbullying_rc2_analysis,
        safe_context_confirmed=(
            (
                safe_context_detected
                and not direct_action_detected
            )
            or bool(
                identity_impersonation_analysis.get(
                    "safe_context_signals",
                    [],
                )
            )
        ),
    )
    category = str(cyberbullying_rc2_fusion["category"])
    severity = str(cyberbullying_rc2_fusion["severity"])
    action = str(cyberbullying_rc2_fusion["action"])
    confidence = float(cyberbullying_rc2_fusion["confidence"])
    human_review_required = bool(
        cyberbullying_rc2_fusion["human_review_required"]
    )
    reason = str(cyberbullying_rc2_fusion["reason"])
    matched_signals = list(cyberbullying_rc2_fusion["matched_signals"])
    cyberbullying_rc2_applied = bool(
        cyberbullying_rc2_fusion["decision_applied"]
    )

    hate_speech_v7_fusion = apply_hate_speech_v7_fusion(
        category=category,
        severity=severity,
        action=action,
        confidence=confidence,
        human_review_required=human_review_required,
        reason=reason,
        matched_signals=matched_signals,
        analysis=hate_speech_v7_analysis,
        safe_context_confirmed=(
            safe_context_detected
            and not direct_action_detected
        ),
    )
    category = str(hate_speech_v7_fusion["category"])
    severity = str(hate_speech_v7_fusion["severity"])
    action = str(hate_speech_v7_fusion["action"])
    confidence = float(hate_speech_v7_fusion["confidence"])
    human_review_required = bool(
        hate_speech_v7_fusion["human_review_required"]
    )
    reason = str(hate_speech_v7_fusion["reason"])
    matched_signals = list(hate_speech_v7_fusion["matched_signals"])
    hate_speech_v7_applied = bool(
        hate_speech_v7_fusion["decision_applied"]
    )

    religiously_offensive_v7_rc6_fusion = (
        apply_religiously_offensive_v7_rc6_fusion(
            category=category,
            severity=severity,
            action=action,
            confidence=confidence,
            human_review_required=human_review_required,
            reason=reason,
            matched_signals=matched_signals,
            analysis=religiously_offensive_v7_rc6_analysis,
            safe_context_confirmed=(
                safe_context_detected
                and not direct_action_detected
            ),
        )
    )
    category = str(religiously_offensive_v7_rc6_fusion["category"])
    severity = str(religiously_offensive_v7_rc6_fusion["severity"])
    action = str(religiously_offensive_v7_rc6_fusion["action"])
    confidence = float(religiously_offensive_v7_rc6_fusion["confidence"])
    human_review_required = bool(
        religiously_offensive_v7_rc6_fusion["human_review_required"]
    )
    reason = str(religiously_offensive_v7_rc6_fusion["reason"])
    matched_signals = list(
        religiously_offensive_v7_rc6_fusion["matched_signals"]
    )
    religiously_offensive_v7_rc6_applied = bool(
        religiously_offensive_v7_rc6_fusion["decision_applied"]
    )

    fact_check_result: dict[str, Any]
    fact_check_error = ""

    if violent_content_safe_override:
        fact_check_result = {
            "fact_check_router_used": False,
            "fact_check_analysis_used": False,
            "decision_override_allowed": False,
            "route_reason": (
                "Fact-check routing was suppressed for a confirmed violence "
                "metaphor, prevention statement, or documented threat report."
            ),
            "category": "",
            "evidence_status": "NOT_ROUTED",
            "confidence": 0.0,
            "action": "",
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "analysis": {},
        }
    else:
        try:
            fact_check_result = analyze_fact_check_for_fusion(
                text=text,
                current_category=safely_normalize_category(category),
            )
        except Exception as error:
            fact_check_error = f"{type(error).__name__}: {error}"
            fact_check_result = {
                "fact_check_router_used": True,
                "fact_check_analysis_used": False,
                "decision_override_allowed": False,
                "route_reason": "Fact-check processing failed safely.",
                "category": "",
                "evidence_status": "ERROR",
                "confidence": 0.0,
                "action": "",
                "human_review_required": False,
                "automatic_enforcement_allowed": False,
                "analysis": {},
            }

    fact_check_analysis_used = bool(
        fact_check_result.get("fact_check_analysis_used", False)
    )

    fact_check_override_allowed = bool(
        fact_check_result.get("decision_override_allowed", False)
    )

    if fact_check_analysis_used and fact_check_override_allowed:
        fact_check_category = str(
            fact_check_result.get("category", "Uncertain")
        )
        fact_check_status = str(
            fact_check_result.get(
                "evidence_status",
                "NOT_ENOUGH_INFO",
            )
        )
        fact_check_confidence = min(
            0.80,
            float(fact_check_result.get("confidence", 0.50)),
        )
        fact_check_analysis = dict(
            fact_check_result.get("analysis", {})
        )

        category = fact_check_category
        confidence = fact_check_confidence
        action = str(
            fact_check_result.get(
                "action",
                "Refer to human review",
            )
        )
        human_review_required = bool(
            fact_check_result.get(
                "human_review_required",
                True,
            )
        )

        if fact_check_status == "SUPPORTS":
            severity = "None"
        elif fact_check_status == "REFUTES":
            severity = (
                "High"
                if fact_check_analysis.get("high_impact_claim", False)
                else "Medium"
            )
        else:
            severity = "Unknown"

        reason = str(
            fact_check_analysis.get(
                "reason",
                (
                    "The fact-check component could not reach a "
                    "sufficiently supported conclusion."
                ),
            )
        )

        matched_signals.append(
            "fact_check_rc2:" + fact_check_status.casefold()
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
                ["fact_check_rc2"]
                if fact_check_analysis_used
                else []
            )
            + (
                ["violent_content_specialist"]
                if violent_content_decision_applied
                else []
            )
            + (
                ["targeted_threat_boundary"]
                if targeted_threat_boundary_applied
                else []
            )
            + (
                ["cyberbullying_abusive_rc2"]
                if cyberbullying_rc2_applied
                else []
            )
            + (
                ["hate_speech_v7_rc1"]
                if hate_speech_v7_applied
                else []
            )
            + (
                ["religiously_offensive_v7_rc6"]
                if religiously_offensive_v7_rc6_applied
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

    if fact_check_error:
        warnings.append(
            f"Fact-check warning: {fact_check_error}"
        )

    if fact_check_analysis_used:
        warnings.extend(
            str(item)
            for item in fact_check_result.get(
                "analysis",
                {},
            ).get("warnings", [])
            if str(item).strip()
        )

    warnings = list(dict.fromkeys(warnings))

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

        "targeted_threat_boundary_used": (
            targeted_threat_boundary_applied
        ),
        "targeted_threat": targeted_threat_analysis,
        "hate_speech_v7_used": hate_speech_v7_applied,
        "hate_speech_v7": hate_speech_v7_analysis,
        "hate_speech_v7_fusion_status": (
            hate_speech_v7_fusion["fusion_status"]
        ),
        "religiously_offensive_v7_rc6_used": (
            religiously_offensive_v7_rc6_applied
        ),
        "religiously_offensive_v7_rc6": (
            religiously_offensive_v7_rc6_analysis
        ),
        "religiously_offensive_v7_rc6_fusion_status": (
            religiously_offensive_v7_rc6_fusion["fusion_status"]
        ),
        "cyberbullying_rc2_used": cyberbullying_rc2_applied,
        "cyberbullying_rc2": cyberbullying_rc2_analysis,
        "cyberbullying_rc2_fusion_status": (
            cyberbullying_rc2_fusion["fusion_status"]
        ),
        "violent_content_specialist_used": (
            violent_content_decision_applied
        ),
        "violent_content_specialist": (
            violent_content_analysis
        ),
        "fact_check_used": fact_check_analysis_used,
        "fact_check": fact_check_result,
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