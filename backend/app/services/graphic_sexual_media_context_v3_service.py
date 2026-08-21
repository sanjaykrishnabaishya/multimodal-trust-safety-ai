from __future__ import annotations

from typing import Any, Mapping

from app.services.graphic_sexual_content_v2_service import (
    SEXUAL_CATEGORY,
    SEXUAL_HARASSMENT_CATEGORY,
    analyze_graphic_sexual_content_v2,
)


MEDIA_REVIEW_ACTION = "Refer to human review"
RECOGNIZED_SCREEN_MEDIA_TYPES = {"film", "movie", "television_series", "tv_series"}
TRUSTED_PROVENANCE_VALUES = {
    "verified_catalog_metadata",
    "verified_publisher_metadata",
    "trusted_media_database",
}
FULLY_OBSCURED_VALUES = {"fully_blurred", "fully_obscured"}
REVIEW_OBSCURATION_VALUES = {"partial", "partially_blurred", "uncertain", "unblurred"}
EXPLICITNESS_REVIEW_VALUES = {"explicit", "adult_sexual", "uncertain"}
EXPLICITNESS_SAFE_VALUES = {"none", "non_explicit"}


def _base(status: str) -> dict[str, Any]:
    return {
        "available": True,
        "category": None,
        "severity": "None",
        "action": None,
        "confidence": 0.0,
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "decision_applied": False,
        "status": status,
        "development_candidate_only": True,
        "connected_to_live_moderation": False,
        "recognized_screen_media_policy_used": False,
    }


def _clean_media_context(media_context: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(media_context or {})
    media_type = str(source.get("media_type", "")).strip().lower()
    work_type = str(source.get("work_type", "")).strip().lower()
    title = " ".join(str(source.get("title", "")).split())
    provenance = str(source.get("provenance", "")).strip().lower()
    obscuration = str(source.get("obscuration", "uncertain")).strip().lower()
    explicitness = str(source.get("explicitness", "uncertain")).strip().lower()
    no_explicit_detail_visible = source.get("no_explicit_detail_visible") is True
    return {
        "media_type": media_type,
        "work_type": work_type,
        "title": title,
        "provenance": provenance,
        "obscuration": obscuration,
        "explicitness": explicitness,
        "no_explicit_detail_visible": no_explicit_detail_visible,
    }


def analyze_graphic_sexual_media_context_v3(
    text: str,
    *,
    existing_category: str | None = None,
    media_context: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply a provenance-gated film/television context policy.

    A title is never recognized from model confidence or title text alone. Trusted
    catalog or publisher metadata must identify both the work and its type.
    Likewise, a blur exception requires an affirmative signal that no explicit
    detail remains visible. These rules cannot displace Child Exploitation,
    Sexual Harassment, or any established category owner.
    """

    v2_result = analyze_graphic_sexual_content_v2(
        text,
        existing_category=existing_category,
    )
    v2_status = str(v2_result.get("status", ""))
    v2_category = v2_result.get("category")

    if v2_status in {
        "child_exploitation_boundary_no_override",
        "blocked_by_established_category_owner",
    }:
        return {
            **v2_result,
            "recognized_screen_media_policy_used": False,
            "media_policy_status": "blocked_by_higher_priority_owner",
        }
    if v2_category == SEXUAL_HARASSMENT_CATEGORY:
        return {
            **v2_result,
            "recognized_screen_media_policy_used": False,
            "media_policy_status": "sexual_harassment_owner_preserved",
        }

    context = _clean_media_context(media_context)
    is_visual_media = context["media_type"] in {"image", "video"}
    trusted_source = context["provenance"] in TRUSTED_PROVENANCE_VALUES
    recognized_work = bool(
        is_visual_media
        and trusted_source
        and context["title"]
        and context["work_type"] in RECOGNIZED_SCREEN_MEDIA_TYPES
    )
    fully_obscured = bool(
        context["obscuration"] in FULLY_OBSCURED_VALUES
        and context["no_explicit_detail_visible"]
    )
    explicit_or_uncertain = context["explicitness"] in EXPLICITNESS_REVIEW_VALUES
    clearly_non_explicit = context["explicitness"] in EXPLICITNESS_SAFE_VALUES
    evidence = {
        "visual_media": is_visual_media,
        "trusted_provenance": trusted_source,
        "recognized_screen_work": recognized_work,
        "work_type": context["work_type"],
        "obscuration": context["obscuration"],
        "no_explicit_detail_visible": context["no_explicit_detail_visible"],
        "explicitness": context["explicitness"],
        "v2_status": v2_status,
        "v2_category": v2_category,
    }

    if recognized_work and fully_obscured:
        result = _base("recognized_screen_media_fully_obscured_no_override")
        result.update(
            {
                "recognized_screen_media_policy_used": True,
                "media_policy_status": "fully_obscured_no_explicit_detail",
                "evidence": evidence,
            }
        )
        return result

    if recognized_work and clearly_non_explicit:
        result = _base("recognized_screen_media_non_explicit_no_override")
        result.update(
            {
                "recognized_screen_media_policy_used": True,
                "media_policy_status": "recognized_but_non_explicit",
                "evidence": evidence,
            }
        )
        return result

    if recognized_work and (
        explicit_or_uncertain
        or context["obscuration"] in REVIEW_OBSCURATION_VALUES
        or v2_category == SEXUAL_CATEGORY
    ):
        return {
            **_base("recognized_screen_media_review_candidate"),
            "category": SEXUAL_CATEGORY,
            "severity": "Medium",
            "action": MEDIA_REVIEW_ACTION,
            "confidence": 0.78,
            "human_review_required": True,
            "decision_applied": True,
            "recognized_screen_media_policy_used": True,
            "media_policy_status": "recognized_explicit_or_uncertain_scene",
            "evidence": evidence,
        }

    return {
        **v2_result,
        "recognized_screen_media_policy_used": False,
        "media_policy_status": (
            "unverified_media_claim_falls_back_to_v2"
            if is_visual_media and context["title"]
            else "no_recognized_screen_media_context"
        ),
        "evidence": {
            **dict(v2_result.get("evidence", {})),
            **evidence,
        },
    }
