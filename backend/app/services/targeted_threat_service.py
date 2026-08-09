from __future__ import annotations

from typing import Any

from app.services.violent_content_service import (
    CONTEXT_PATTERNS,
    DIRECT_THREAT_PATTERNS,
    DOCUMENTED_THREAT_REPORT_PATTERN,
    METAPHOR_PATTERNS,
    NEGATED_PREVENTION_PATTERN,
    matching_names,
    normalize_text,
)


TARGET_CATEGORY = "Cyberbullying & Harassment"


def analyze_targeted_threat(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)
    result: dict[str, Any] = {
        "available": True,
        "detected": False,
        "category": "",
        "confidence": 0.0,
        "severity": "None",
        "action": "",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "decision_type": "none",
        "threat_signals": [],
        "context_signals": [],
        "reason": "No sufficiently supported targeted intimidation signal was detected.",
    }

    if not normalized:
        return result

    threats = matching_names(normalized, DIRECT_THREAT_PATTERNS)
    contexts = matching_names(normalized, CONTEXT_PATTERNS)
    metaphors = matching_names(normalized, METAPHOR_PATTERNS)

    result["threat_signals"] = threats
    result["context_signals"] = contexts

    if not threats:
        return result

    if metaphors:
        result["decision_type"] = "figurative_language"
        result["reason"] = "The apparent threat wording is figurative rather than targeted intimidation."
        return result

    if NEGATED_PREVENTION_PATTERN.search(normalized):
        result["decision_type"] = "prevention"
        result["reason"] = "The text discourages threats or violence."
        return result

    if DOCUMENTED_THREAT_REPORT_PATTERN.search(normalized):
        result["decision_type"] = "documented_report"
        result["reason"] = "A threat is quoted as evidence in a police report."
        return result

    if contexts:
        result["decision_type"] = "fictional_educational_or_reporting_context"
        result["reason"] = (
            "Threatening language appears in fiction, education, reporting, history, "
            "gaming, prevention, or another documented context."
        )
        return result

    result.update(
        {
            "detected": True,
            "category": TARGET_CATEGORY,
            "confidence": min(0.95, 0.90 + (0.02 * (len(threats) - 1))),
            "severity": "High",
            "action": "Limit, flag, and send for human review",
            "human_review_required": True,
            "decision_type": "targeted_intimidation",
            "reason": (
                "The text targets a person with a credible expression of physical harm, "
                "violent intimidation, or encouragement to attack that person."
            ),
        }
    )
    return result

