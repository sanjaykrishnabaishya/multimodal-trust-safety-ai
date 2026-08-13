from __future__ import annotations

import re
from typing import Iterable


TERRORISM_CATEGORY = "Terrorism & Extremism"
NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"

STRONG_DESIGNATION_PATTERNS = (
    r"\b(?:designated|banned|proscribed|listed)\s+(?:terrorist|extremist)\s+"
    r"(?:organization|organisation|group|network|movement)\b",
)

WEAK_ORGANIZATION_PATTERNS = (
    r"\bterrorist\s+(?:organization|organisation|group|network|movement)\b",
    r"\bextremist\s+(?:organization|organisation|group|network|movement)\b",
    r"\b(?:organization|organisation|group|network)\s+(?:may|might|could)\s+be\s+extremist\b",
    r"\b(?:unnamed|unknown|unverified)\s+(?:organization|organisation|group|network)\b",
)

UNKNOWN_STATUS_PATTERNS = (
    r"\b(?:identity|legal status|designation|status)\s+(?:is\s+)?(?:unknown|uncertain|unverified)\b",
    r"\b(?:cannot|can not|could not)\s+be\s+(?:verified|authenticated|confirmed)\b",
    r"\bno\s+official\s+designation\s+source\b",
    r"\binsufficient\s+(?:evidence|information)\b",
    r"\bmay\s+be\s+extremist\b",
    r"\bmight\s+belong\s+to\b",
    r"\bcould\s+refer\s+to\b",
    r"\bidentity\s+and\s+legal\s+status\s+(?:are|remain)\s+(?:unknown|uncertain)\b",
    r"\bmatch\s+is\s+(?:unknown|uncertain|unverified)\b",
)

POSSIBLE_SUBJECT_PATTERNS = (
    r"\b(?:organization|organisation|group|network|movement|symbol)\b",
)

LEGITIMATE_CONTEXT_PATTERNS = (
    r"\b(?:job|jobs|career|careers|vacancy|vacancies|employment|internship|"
    r"internships|apprenticeship|position|positions|role|roles)\b",
    r"\b(?:hire|hires|hiring|recruiter|recruiters|candidate|candidates|"
    r"applicant|applicants|resume|résumé|curriculum vitae|interview|salary)\b",
    r"\b(?:company|corporation|corporate|business|employer|workforce|"
    r"employee|employees|human resources|hr team)\b",
    r"\b(?:software|cloud|customer support|technical support|project team|"
    r"business operations|supply chain|delivery operations|event operations)\b",
    r"\b(?:school|college|university|research laboratory|sports club|"
    r"community group|charity|nonprofit|non-profit|humanitarian|relief work|"
    r"hospital|clinic|healthcare provider)\b",
    r"\bvolunteers?\s+(?:for|at|with)\s+(?:a\s+)?(?:charity|school|hospital|"
    r"community|nonprofit|non-profit|relief|event)\b",
)

RECRUITMENT_PATTERNS = (
    r"\b(?:join|enlist|enrol|enroll|register|sign up|volunteer)\b",
    r"\b(?:recruit|recruits|recruiting|recruited)\b",
    r"\bbecome\s+(?:a\s+)?members?\b",
    r"\bfight\s+(?:for|alongside)\b",
)

GLORIFICATION_PATTERNS = (
    r"\b(?:praise|praises|praised|praising)\b",
    r"\b(?:glorify|glorifies|glorified|glorifying|glorification)\b",
    r"\b(?:celebrate|celebrates|celebrated|celebrating)\b",
    r"\b(?:endorse|endorses|endorsed|endorsing)\b",
    r"\b(?:applaud|applauds|applauded|applauding)\b",
    r"\b(?:honor|honour|honors|honours|honored|honoured)\b",
    r"\b(?:heroic|heroes|martyrs?)\b",
)

FUNDING_SUPPORT_PATTERNS = (
    r"\b(?:donate|donates|donated|donating|donations?)\b",
    r"\b(?:fund|funds|funded|funding|finance|financing)\b",
    r"\b(?:send|transfer|raise)\s+(?:money|funds|crypto|cryptocurrency)\b",
    r"\b(?:material|financial|logistical|operational)\s+(?:aid|assistance|support)\b",
    r"\b(?:weapons?|equipment|transport|safe houses?|supplies)\s+for\b",
    r"\bresources?\s+intended\s+to\s+support\b",
)

PROPAGANDA_PATTERNS = (
    r"\b(?:share|shares|shared|sharing|distribute|distributes|distributed|"
    r"distributing|spread|spreads|spreading|promote|promotes|promoting)\b"
    r".{0,45}\b(?:propaganda|recruitment material|manifesto|links?|videos?)\b",
    r"\b(?:propaganda|recruitment material)\b.{0,45}"
    r"\b(?:share|distribute|spread|promote)\b",
)

SAFE_FRAMING_PATTERNS = (
    r"\b(?:news|journalistic|media|court|police)\s+(?:report|reporting|article|coverage)\b",
    r"\b(?:academic|scholarly)\s+(?:paper|analysis|research|study|discussion)\b",
    r"\b(?:documentary|museum|archive|historical|history)\b",
    r"\bpublic[- ]safety\s+(?:message|warning|campaign)\b",
    r"\b(?:educational|education|research)\s+(?:purpose|context|material)\b",
    r"\brecords?\s+allegations?\b",
)

SAFE_POSITION_PATTERNS = (
    r"\b(?:condemn|condemns|condemned|condemning|condemnation)\b",
    r"\bwithout\s+(?:endorsing|praising|supporting|promoting)\b",
    r"\b(?:does not|doesn't|did not|didn't)\s+(?:endorse|praise|support|promote)\b",
    r"\b(?:warn|warns|warned|warning)\s+(?:people|users|readers|the public)?\s*not\s+to\b",
    r"\b(?:neutral|critically|critical|opposes|opposed|opposing)\b",
    r"\bcontains?\s+no\s+(?:recruitment|praise|assistance|support)\b",
    r"\bno\s+(?:recruitment|praise|assistance|support|endorsement)\b",
)


def normalize_text(text: str) -> str:
    normalized = str(text or "").casefold()
    normalized = normalized.replace("’", "'").replace("‘", "'")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized.strip()


def matched_labels(
    text: str,
    labelled_patterns: Iterable[tuple[str, tuple[str, ...]]],
) -> list[str]:
    return [
        label
        for label, patterns in labelled_patterns
        if any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)
    ]


def has_match(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, flags=re.IGNORECASE) for pattern in patterns)


def decision(
    *,
    category: str | None,
    status: str,
    confidence: float,
    action: str,
    human_review_required: bool,
    behavior_families: list[str],
    designation_evidence: str,
    safe_context_detected: bool,
    reason: str,
) -> dict[str, object]:
    return {
        "available": True,
        "category": category,
        "status": status,
        "confidence": round(confidence, 2),
        "action": action,
        "human_review_required": human_review_required,
        "behavior_families": behavior_families,
        "designation_evidence": designation_evidence,
        "safe_context_detected": safe_context_detected,
        "organization_registry_used": False,
        "official_source_data_used": False,
        "supporting_evidence_only": True,
        "automatic_enforcement_allowed": False,
        "neutral_mention_is_violation": False,
        "reason": reason,
    }


def analyze_terrorism_extremism(text: str) -> dict[str, object]:
    normalized = normalize_text(text)
    if not normalized:
        return decision(
            category=None,
            status="no_boundary_override",
            confidence=0.0,
            action="No boundary override",
            human_review_required=False,
            behavior_families=[],
            designation_evidence="none",
            safe_context_detected=False,
            reason="No readable text was provided.",
        )

    behavior_families = matched_labels(
        normalized,
        (
            ("recruitment_or_membership", RECRUITMENT_PATTERNS),
            ("praise_or_glorification", GLORIFICATION_PATTERNS),
            ("funding_or_operational_support", FUNDING_SUPPORT_PATTERNS),
            ("propaganda_distribution", PROPAGANDA_PATTERNS),
        ),
    )
    strong_designation = has_match(normalized, STRONG_DESIGNATION_PATTERNS)
    weak_organization = has_match(normalized, WEAK_ORGANIZATION_PATTERNS)
    unknown_status = has_match(normalized, UNKNOWN_STATUS_PATTERNS)
    possible_subject = has_match(normalized, POSSIBLE_SUBJECT_PATTERNS)
    legitimate_context = has_match(normalized, LEGITIMATE_CONTEXT_PATTERNS)
    safe_framing = has_match(normalized, SAFE_FRAMING_PATTERNS)
    safe_position = has_match(normalized, SAFE_POSITION_PATTERNS)
    safe_context = safe_framing and safe_position

    if legitimate_context and not (
        strong_designation or weak_organization or unknown_status
    ):
        return decision(
            category=None,
            status="legitimate_recruitment_or_operational_context",
            confidence=0.94,
            action="No boundary override",
            human_review_required=False,
            behavior_families=behavior_families,
            designation_evidence="none",
            safe_context_detected=True,
            reason=(
                "Recruitment or operational-support language appears in an "
                "ordinary employment, business, education, charity, or "
                "community context."
            ),
        )

    if legitimate_context and (
        strong_designation or weak_organization or unknown_status
    ):
        return decision(
            category=UNCERTAIN_CATEGORY,
            status="conflicting_legitimate_and_extremist_context",
            confidence=0.52,
            action="Refer to human review",
            human_review_required=True,
            behavior_families=behavior_families,
            designation_evidence=(
                "claimed_designation_requires_verification"
                if strong_designation
                else "unverified"
            ),
            safe_context_detected=True,
            reason=(
                "Ordinary organizational context conflicts with an extremist "
                "label. The label cannot be accepted as fact without verified "
                "evidence."
            ),
        )

    if safe_context:
        return decision(
            category=NORMAL_CATEGORY,
            status="safe_reporting_education_history_or_condemnation",
            confidence=0.92,
            action="Allow",
            human_review_required=False,
            behavior_families=behavior_families,
            designation_evidence=(
                "explicit_designation_in_safe_context"
                if strong_designation
                else "none"
            ),
            safe_context_detected=True,
            reason=(
                "The content uses reporting, educational, historical, or "
                "condemnation framing and does not endorse or assist terrorism."
            ),
        )

    if safe_framing and behavior_families:
        return decision(
            category=UNCERTAIN_CATEGORY,
            status="conflicting_context_requires_review",
            confidence=0.55,
            action="Refer to human review",
            human_review_required=True,
            behavior_families=behavior_families,
            designation_evidence=(
                "explicit_designation" if strong_designation else "unverified"
            ),
            safe_context_detected=True,
            reason=(
                "Reporting-style framing and apparent promotional behavior "
                "conflict, so a reviewer must determine the actual context."
            ),
        )

    if unknown_status and (
        behavior_families
        or weak_organization
        or strong_designation
        or possible_subject
    ):
        return decision(
            category=UNCERTAIN_CATEGORY,
            status="organization_status_unverified",
            confidence=0.58,
            action="Refer to human review",
            human_review_required=True,
            behavior_families=behavior_families,
            designation_evidence="unverified",
            safe_context_detected=False,
            reason=(
                "The text raises a possible extremist association, but the "
                "organization identity or legal status is not verified."
            ),
        )

    if behavior_families and strong_designation:
        confidence = min(0.94, 0.88 + 0.02 * (len(behavior_families) - 1))
        return decision(
            category=TERRORISM_CATEGORY,
            status="terrorism_behavior_review_only",
            confidence=confidence,
            action="Block and escalate",
            human_review_required=True,
            behavior_families=behavior_families,
            designation_evidence="explicit_designation_in_user_content",
            safe_context_detected=False,
            reason=(
                "The text explicitly describes a banned/designated terrorist "
                "or extremist organization and contains recruitment, praise, "
                "funding, propaganda distribution, or operational support."
            ),
        )

    if behavior_families and weak_organization:
        return decision(
            category=UNCERTAIN_CATEGORY,
            status="possible_extremist_behavior_unverified",
            confidence=0.56,
            action="Refer to human review",
            human_review_required=True,
            behavior_families=behavior_families,
            designation_evidence="unverified",
            safe_context_detected=False,
            reason=(
                "Potential recruitment, praise, or support is present, but no "
                "verified designation evidence is available."
            ),
        )

    return decision(
        category=None,
        status="no_boundary_override",
        confidence=0.0,
        action="No boundary override",
        human_review_required=False,
        behavior_families=behavior_families,
        designation_evidence="none",
        safe_context_detected=False,
        reason=(
            "The terrorism specialist found insufficient evidence and does not "
            "replace any category owned by another specialist."
        ),
    )


def get_terrorism_extremism_status() -> dict[str, object]:
    return {
        "available": True,
        "candidate": "terrorism-extremism-v2-behavior-only",
        "organization_registry_used": False,
        "official_source_data_used": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
