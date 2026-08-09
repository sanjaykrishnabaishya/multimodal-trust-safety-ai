from __future__ import annotations

from typing import Any

from app.services.stable_knowledge_service import (
    retrieve_stable_knowledge_evidence,
)
from app.services.structured_claim_service import parse_structured_claim
from app.services.structured_evidence_service import (
    retrieve_structured_evidence,
)


CONCLUSIVE_VERDICTS = {"SUPPORTS", "REFUTES"}
VALID_VERDICTS = {
    "SUPPORTS",
    "REFUTES",
    "NOT_DETERMINED",
    "NOT_ENOUGH_INFO",
    "CONFLICTING_EVIDENCE",
}
CONFIDENCE_CAP = 0.80
MAXIMUM_EVIDENCE_ITEMS = 8


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def normalize_verdict(value: Any) -> str:
    verdict = normalize_text(value).upper().replace(" ", "_")
    return verdict if verdict in VALID_VERDICTS else "NOT_DETERMINED"


def evidence_identity(item: dict[str, Any]) -> tuple[str, str, str]:
    return (
        normalize_text(item.get("source_id", "")).casefold(),
        normalize_text(item.get("source_url", "")).casefold(),
        normalize_text(
            item.get("excerpt", item.get("reason", ""))
        ).casefold(),
    )


def evidence_priority(item: dict[str, Any]) -> tuple[int, int, int, float]:
    structured_verdict = normalize_verdict(
        item.get(
            "structured_relation_verdict",
            item.get("stable_relation_verdict", ""),
        )
    )
    return (
        int(structured_verdict in CONCLUSIVE_VERDICTS),
        int(bool(item.get("official_source", False))),
        -int(item.get("trust_tier", 99)),
        float(item.get("relevance_score", 0.0)),
    )


def deduplicate_and_rank_evidence(
    items: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()

    for item in items:
        if not isinstance(item, dict):
            continue
        identity = evidence_identity(item)
        if identity in seen:
            continue
        seen.add(identity)
        selected.append(item)

    selected.sort(key=evidence_priority, reverse=True)
    return selected[:MAXIMUM_EVIDENCE_ITEMS]


def explicit_verdicts_from_evidence(
    items: list[dict[str, Any]],
) -> list[str]:
    verdicts: list[str] = []

    for item in items:
        verdict = normalize_verdict(
            item.get(
                "structured_relation_verdict",
                item.get("stable_relation_verdict", ""),
            )
        )
        if verdict in CONCLUSIVE_VERDICTS:
            verdicts.append(verdict)

    return verdicts


def combine_explicit_verdicts(verdicts: list[str]) -> str:
    unique = set(verdicts)
    if "SUPPORTS" in unique and "REFUTES" in unique:
        return "CONFLICTING_EVIDENCE"
    if "SUPPORTS" in unique:
        return "SUPPORTS"
    if "REFUTES" in unique:
        return "REFUTES"
    return "NOT_ENOUGH_INFO"


def unique_warnings(values: list[Any]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()

    for value in values:
        warning = normalize_text(value)
        key = warning.casefold()
        if warning and key not in seen:
            seen.add(key)
            output.append(warning)

    return output


def _empty_legacy_result(claim: str) -> dict[str, Any]:
    return {
        "available": True,
        "eligible": False,
        "claim": normalize_text(claim),
        "topic": "general_knowledge",
        "evidence": [],
        "warnings": [],
        "retrieval_mode": "not_used",
        "cache_allowed": False,
        "persistent_cache_used": False,
    }


def retrieve_stable_knowledge_v3(claim: str) -> dict[str, Any]:
    cleaned_claim = normalize_text(claim)
    parsed_claim = parse_structured_claim(cleaned_claim)

    base_result: dict[str, Any] = {
        "available": True,
        "version": "2026.08-v3",
        "claim": cleaned_claim,
        "eligible": False,
        "topic": parsed_claim.get("topic", "general_knowledge"),
        "parsed_claim": parsed_claim,
        "evidence_status": "NOT_ENOUGH_INFO",
        "confidence": 0.0,
        "confidence_cap": CONFIDENCE_CAP,
        "evidence_conflict_detected": False,
        "evidence": [],
        "evidence_count": 0,
        "source_names": [],
        "warnings": list(parsed_claim.get("warnings", [])),
        "structured_retrieval_used": False,
        "legacy_live_retrieval_used": False,
        "fallback_reason": "",
        "retrieval_mode": "live_only",
        "cache_allowed": False,
        "persistent_cache_used": False,
        "automatic_enforcement_allowed": False,
        "requires_final_policy_decision": True,
    }

    if not cleaned_claim:
        base_result["warnings"] = unique_warnings(
            [*base_result["warnings"], "The claim is empty."]
        )
        return base_result

    if not parsed_claim.get("suitable_for_stable_knowledge", False):
        base_result["warnings"] = unique_warnings(
            [
                *base_result["warnings"],
                "V3 did not route this claim as stable general knowledge. "
                "Current, high-impact, unsupported, and question forms must "
                "use a different decision path.",
            ]
        )
        return base_result

    structured_result = retrieve_structured_evidence(cleaned_claim)
    structured_verdict = normalize_verdict(
        structured_result.get("verdict", "NOT_DETERMINED")
    )
    structured_items = [
        item
        for item in structured_result.get("evidence", [])
        if isinstance(item, dict)
        and structured_verdict in CONCLUSIVE_VERDICTS
    ]
    structured_warnings = list(structured_result.get("warnings", []))
    structured_used = bool(structured_result.get("eligible", False))

    if structured_verdict in CONCLUSIVE_VERDICTS:
        legacy_result = _empty_legacy_result(cleaned_claim)
        legacy_items: list[dict[str, Any]] = []
        legacy_warnings: list[str] = []
        fallback_reason = ""
    else:
        legacy_result = retrieve_stable_knowledge_evidence(cleaned_claim)
        legacy_items = [
            item
            for item in legacy_result.get("evidence", [])
            if isinstance(item, dict)
        ]
        legacy_warnings = list(legacy_result.get("warnings", []))
        fallback_reason = (
            "Structured evidence was not conclusive, so the existing "
            "live-only stable-knowledge retriever was used."
        )

    all_items = deduplicate_and_rank_evidence(
        [*structured_items, *legacy_items]
    )
    explicit_verdicts = explicit_verdicts_from_evidence(all_items)

    if structured_verdict in CONCLUSIVE_VERDICTS:
        explicit_verdicts.insert(0, structured_verdict)

    evidence_status = combine_explicit_verdicts(explicit_verdicts)
    evidence_conflict = evidence_status == "CONFLICTING_EVIDENCE"

    if evidence_status == "SUPPORTS":
        raw_confidence = max(
            float(structured_result.get("confidence", 0.0)),
            0.80,
        )
    elif evidence_status == "REFUTES":
        raw_confidence = max(
            float(structured_result.get("confidence", 0.0)),
            0.80,
        )
    elif evidence_status == "CONFLICTING_EVIDENCE":
        raw_confidence = 0.50
    else:
        raw_confidence = 0.0

    confidence = round(min(raw_confidence, CONFIDENCE_CAP), 4)
    source_names = sorted(
        {
            normalize_text(item.get("source_name", ""))
            for item in all_items
            if normalize_text(item.get("source_name", ""))
        }
    )
    warnings = unique_warnings(
        [
            *parsed_claim.get("warnings", []),
            *structured_warnings,
            *legacy_warnings,
        ]
    )

    if evidence_conflict:
        warnings.append(
            "Live sources returned opposing explicit relationship verdicts. "
            "The claim must remain uncertain and require human review."
        )

    base_result.update(
        {
            "eligible": bool(
                structured_result.get("eligible", False)
                or legacy_result.get("eligible", False)
            ),
            "topic": parsed_claim.get(
                "topic",
                legacy_result.get("topic", "general_knowledge"),
            ),
            "evidence_status": evidence_status,
            "confidence": confidence,
            "evidence_conflict_detected": evidence_conflict,
            "evidence": all_items,
            "evidence_count": len(all_items),
            "source_names": source_names,
            "warnings": unique_warnings(warnings),
            "structured_retrieval_used": structured_used,
            "structured_verdict": structured_verdict,
            "structured_confidence": float(
                structured_result.get("confidence", 0.0)
            ),
            "legacy_live_retrieval_used": bool(
                legacy_result.get("retrieval_mode") != "not_used"
            ),
            "fallback_reason": fallback_reason,
        }
    )
    return base_result


def get_stable_knowledge_v3_status() -> dict[str, Any]:
    return {
        "available": True,
        "version": "2026.08-v3",
        "language": "en",
        "retrieval_mode": "live_only",
        "structured_retrieval_first": True,
        "legacy_live_fallback": True,
        "confidence_cap": CONFIDENCE_CAP,
        "cache_allowed": False,
        "persistent_cache_used": False,
        "uses_holdout_records": False,
        "automatic_enforcement_allowed": False,
    }


__all__ = [
    "get_stable_knowledge_v3_status",
    "retrieve_stable_knowledge_v3",
]
