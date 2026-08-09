from __future__ import annotations

import re
from typing import Any

from app.policy_config import ModerationCategory
from app.services.fact_check_decision_service import analyze_fact_check
from app.services.fact_check_source_registry import (
    build_fact_check_source_plan,
)
from app.services.structured_claim_service import parse_structured_claim


NORMAL_CATEGORY = ModerationCategory.NORMAL_IGNORE.value
MISINFORMATION_CATEGORY = ModerationCategory.MISINFORMATION.value
UNCERTAIN_CATEGORY = "Uncertain"

MAXIMUM_CLAIM_LENGTH = 5000

DECLARATIVE_PATTERN = re.compile(
    r"\b("
    r"is|are|was|were|has|have|had|"
    r"banned|closed|stopped|ordered|announced|"
    r"reached|located|developed|created|invented|"
    r"discovered|founded|orbits|revolves|"
    r"contains|causes|prevents|approved|rejected"
    r")\b",
    re.IGNORECASE,
)

NON_CLAIM_PATTERN = re.compile(
    r"^\s*("
    r"who|what|when|where|why|how|"
    r"is it|are they|does|do|did|can|could"
    r")\b|[?]\s*$",
    re.IGNORECASE,
)

OPINION_PATTERN = re.compile(
    r"\b("
    r"i think|i believe|in my opinion|"
    r"i feel|seems beautiful|best|worst|"
    r"may be|might be|could be"
    r")\b",
    re.IGNORECASE,
)

REPORTING_CONTEXT_PATTERN = re.compile(
    r"\b("
    r"the article reports|the report describes|"
    r"the documentary discusses|"
    r"the news article mentions|"
    r"someone said|a post claims|"
    r"a message says|according to a post|"
    r"it is rumored|the headline claims"
    r")\b",
    re.IGNORECASE,
)

SECURITY_ADVICE_PATTERN = re.compile(
    r"\b("
    r"never\s+(share|send|reveal|disclose)|"
    r"do\s+not\s+(share|send|reveal|disclose)|"
    r"don't\s+(share|send|reveal|disclose)|"
    r"avoid\s+(sharing|sending|revealing|disclosing)|"
    r"beware\s+of|protect\s+your"
    r")\b.{0,80}\b("
    r"otp|password|pin|cvv|credential|credentials|"
    r"banking details|bank details|account details|"
    r"money|payment|verification code"
    r")\b",
    re.IGNORECASE,
)

PARODY_DISCLOSURE_PATTERN = re.compile(
    r"\b("
    r"clearly\s+marked\s+(parody|satire)|"
    r"(parody|satire|fan|fictional)\s+account|"
    r"this\s+is\s+(a\s+)?(parody|satire)|"
    r"not\s+affiliated\s+with|"
    r"for\s+(parody|satire)\s+purposes"
    r")\b",
    re.IGNORECASE,
)


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def build_skipped_result(reason: str) -> dict[str, Any]:
    return {
        "fact_check_router_used": True,
        "fact_check_analysis_used": False,
        "decision_override_allowed": False,
        "route_reason": reason,
        "category": "",
        "evidence_status": "NOT_EVALUATED",
        "confidence": 0.0,
        "action": "",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "analysis": {},
    }


def should_run_fact_check(
    text: str,
    current_category: str,
) -> tuple[bool, str]:
    claim = normalize_text(text)

    if current_category != NORMAL_CATEGORY:
        return (
            False,
            "Another moderation category already has priority.",
        )

    if len(claim) < 10:
        return False, "The text is too short to verify reliably."

    if len(claim) > MAXIMUM_CLAIM_LENGTH:
        return (
            False,
            "The text must be separated into individual claims.",
        )

    if NON_CLAIM_PATTERN.search(claim):
        return False, "The text appears to be a question."

    if OPINION_PATTERN.search(claim):
        return False, "The text appears to express an opinion."

    if REPORTING_CONTEXT_PATTERN.search(claim):
        return (
            False,
            "The text reports another person's claim without adopting it.",
        )

    if SECURITY_ADVICE_PATTERN.search(claim):
        return (
            False,
            "The text gives protective security advice rather than "
            "asserting a claim that requires fact-checking.",
        )

    if PARODY_DISCLOSURE_PATTERN.search(claim):
        return (
            False,
            "The text is a parody, satire, fan-account, or fictional-account "
            "disclosure handled by the identity-context policy.",
        )

    structured_claim = parse_structured_claim(claim)

    if structured_claim.get(
        "suitable_for_stable_knowledge",
        False,
    ):
        return (
            True,
            "A supported stable-knowledge relation was detected.",
        )

    source_plan = build_fact_check_source_plan(claim)
    topics = list(source_plan.get("topics", []))

    if topics and DECLARATIVE_PATTERN.search(claim):
        return (
            True,
            "A declarative India or world factual claim was detected.",
        )

    return (
        False,
        "No sufficiently clear factual claim was detected.",
    )


def analyze_fact_check_for_fusion(
    text: str,
    current_category: str,
) -> dict[str, Any]:
    should_run, route_reason = should_run_fact_check(
        text=text,
        current_category=current_category,
    )

    if not should_run:
        return build_skipped_result(route_reason)

    analysis = analyze_fact_check(text)

    evidence_status = normalize_text(
        analysis.get("evidence_status", "NOT_ENOUGH_INFO")
    ).upper()

    confidence = min(
        0.80,
        max(
            0.0,
            float(analysis.get("confidence", 0.50)),
        ),
    )

    if evidence_status == "SUPPORTS":
        category = NORMAL_CATEGORY
        action = "Allow"
        human_review_required = False

    elif evidence_status == "REFUTES":
        category = MISINFORMATION_CATEGORY
        action = "Refer to human review"
        human_review_required = True

    else:
        category = UNCERTAIN_CATEGORY
        action = "Refer to human review"
        human_review_required = True

    return {
        "fact_check_router_used": True,
        "fact_check_analysis_used": True,
        "decision_override_allowed": True,
        "route_reason": route_reason,
        "category": category,
        "evidence_status": evidence_status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": human_review_required,
        "automatic_enforcement_allowed": False,
        "analysis": analysis,
    }
