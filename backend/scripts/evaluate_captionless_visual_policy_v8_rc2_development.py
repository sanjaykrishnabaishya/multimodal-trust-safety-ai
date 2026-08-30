from __future__ import annotations

import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from app.services.captionless_visual_policy_v8_rc2_service import (
    AGE_RESTRICT_BLOCK_ACTION,
    ALLOW_ACTION,
    NORMAL_CATEGORY,
    REVIEW_ACTION,
    SEXUAL_CATEGORY,
    UNCERTAIN_CATEGORY,
    WARNING_REVIEW_ACTION,
    analyze_captionless_visual_policy_v8_rc2,
)


BACKEND_ROOT = Path(__file__).resolve().parents[1]
PROJECT_ROOT = BACKEND_ROOT.parent
REPORT_DIR = (
    PROJECT_ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_policy_v8_rc2_development"
)
REPORT_PATH = REPORT_DIR / "report.json"

RECORDS_PER_GROUP = 10
ZERO_HASH = "0" * 64


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _visual(
    record_id: str,
    *,
    boundary: str,
    confidence: float = 0.97,
    content_type: str = "image",
    **overrides: Any,
) -> dict[str, Any]:
    value: dict[str, Any] = {
        "evidence_source": "signed_visual_pipeline",
        "pipeline_ready": True,
        "candidate_frozen": True,
        "independent_verdict_passed": True,
        "model_id": "captionless-visual-evidence-future-independent-candidate",
        "model_revision": "locked-policy-contract-fixture",
        "artifact_sha256": _digest(f"artifact:{record_id}"),
        "verdict_sha256": _digest(f"verdict:{record_id}"),
        "candidate_boundary": boundary,
        "candidate_confidence": confidence,
        "sample_coverage": 1.0 if content_type == "image" else 0.95,
        "decode_status": "complete",
        "visible_nudity": False,
        "visible_private_parts": False,
        "explicit_sexual_activity": False,
        "non_explicit_intimacy": False,
        "fully_obscured": False,
        "no_explicit_detail_visible": False,
        "adult_status_verified": False,
        "age_ambiguous": False,
        "child_risk_detected": False,
        "self_report_only": False,
        "llm_only": False,
    }
    value.update(overrides)
    return value


def _provenance(
    record_id: str,
    *,
    context_type: str,
    source: str | None = None,
    **overrides: Any,
) -> dict[str, Any]:
    default_source = (
        "museum_catalog"
        if context_type in {
            "verified_artwork",
            "verified_monument",
            "verified_cultural_object",
        }
        else "trusted_educational_repository"
        if context_type == "verified_educational_material"
        else "verified_publisher_metadata"
    )
    value: dict[str, Any] = {
        "evidence_source": source or default_source,
        "context_type": context_type,
        "work_identity_verified": True,
        "independently_verified": True,
        "record_id": f"CATALOG-{record_id}",
        "record_sha256": _digest(f"record:{record_id}"),
        "media_sha256": _digest(f"media:{record_id}"),
        "signed_evidence": True,
        "self_report_only": False,
        "llm_only": False,
    }
    value.update(overrides)
    return value


def _case(
    *,
    group: str,
    expected_category: str | None,
    expected_action: str | None,
    expected_status: str,
    content_type: str = "image",
    existing_category: str | None = None,
    visual: dict[str, Any],
    provenance: dict[str, Any] | None = None,
    llm: dict[str, Any] | None = None,
    expect_art_allow_eligible: bool = False,
) -> dict[str, Any]:
    return {
        "group": group,
        "content_type": content_type,
        "existing_category": existing_category,
        "visual": visual,
        "provenance": provenance,
        "llm": llm,
        "expected_category": expected_category,
        "expected_action": expected_action,
        "expected_status": expected_status,
        "expect_art_allow_eligible": expect_art_allow_eligible,
    }


def build_cases() -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for index in range(1, RECORDS_PER_GROUP + 1):
        suffix = f"{index:02d}"

        for group, context_type in (
            ("verified_artwork_auto_allow", "verified_artwork"),
            ("verified_monument_auto_allow", "verified_monument"),
            ("verified_education_auto_allow", "verified_educational_material"),
        ):
            record_id = f"{group}:{suffix}"
            cases.append(
                _case(
                    group=group,
                    expected_category=NORMAL_CATEGORY,
                    expected_action=ALLOW_ACTION,
                    expected_status=(
                        "verified_art_culture_or_education_allow_candidate"
                    ),
                    visual=_visual(
                        record_id,
                        boundary="verified_art_culture_or_education",
                        visible_nudity=index % 2 == 0,
                    ),
                    provenance=_provenance(
                        record_id, context_type=context_type
                    ),
                    expect_art_allow_eligible=True,
                )
            )

        record_id = f"film_explicit_adult:{suffix}"
        cases.append(
            _case(
                group="film_explicit_adult_restricted",
                content_type="video",
                expected_category=SEXUAL_CATEGORY,
                expected_action=AGE_RESTRICT_BLOCK_ACTION,
                expected_status="verified_screen_media_explicit_adult_restricted",
                visual=_visual(
                    record_id,
                    content_type="video",
                    boundary="explicit_adult_sexual_content",
                    visible_nudity=True,
                    visible_private_parts=True,
                    adult_status_verified=True,
                ),
                provenance=_provenance(record_id, context_type="film"),
            )
        )

        record_id = f"series_intimacy:{suffix}"
        cases.append(
            _case(
                group="series_non_explicit_intimacy_review",
                content_type="video",
                expected_category=UNCERTAIN_CATEGORY,
                expected_action=WARNING_REVIEW_ACTION,
                expected_status=(
                    "verified_screen_media_non_explicit_intimacy_review"
                ),
                visual=_visual(
                    record_id,
                    content_type="video",
                    boundary="non_explicit_intimacy",
                    non_explicit_intimacy=True,
                ),
                provenance=_provenance(
                    record_id, context_type="television_series"
                ),
            )
        )

        record_id = f"film_safe:{suffix}"
        cases.append(
            _case(
                group="screen_safe_scene_never_earns_allow",
                expected_category=None,
                expected_action=None,
                expected_status="verified_screen_media_safe_scene_no_policy_override",
                visual=_visual(record_id, boundary="safe_or_other"),
                provenance=_provenance(record_id, context_type="movie"),
            )
        )

        record_id = f"screen_obscured:{suffix}"
        cases.append(
            _case(
                group="screen_full_obscuration_never_earns_allow",
                expected_category=None,
                expected_action=None,
                expected_status="verified_screen_media_obscured_no_policy_override",
                visual=_visual(
                    record_id,
                    boundary="safe_or_other",
                    fully_obscured=True,
                    no_explicit_detail_visible=True,
                ),
                provenance=_provenance(record_id, context_type="tv_series"),
            )
        )

        record_id = f"unverified_title:{suffix}"
        cases.append(
            _case(
                group="unverified_famous_title_cannot_allow",
                expected_category=UNCERTAIN_CATEGORY,
                expected_action=REVIEW_ACTION,
                expected_status="unverified_or_ambiguous_visual_context_review",
                visual=_visual(record_id, boundary="safe_or_other"),
                provenance=_provenance(
                    record_id,
                    context_type="film",
                    source="self_report",
                    independently_verified=False,
                    signed_evidence=False,
                    self_report_only=True,
                ),
            )
        )

        record_id = f"llm_art:{suffix}"
        cases.append(
            _case(
                group="llm_only_art_claim_cannot_allow",
                expected_category=UNCERTAIN_CATEGORY,
                expected_action=REVIEW_ACTION,
                expected_status="llm_concern_can_only_escalate_to_review",
                visual=_visual(record_id, boundary="safe_or_other"),
                provenance=_provenance(
                    record_id,
                    context_type="verified_artwork",
                    source="local_llm",
                    independently_verified=False,
                    signed_evidence=False,
                    llm_only=True,
                ),
                llm={"review_concern": True, "claimed_context": "artwork"},
            )
        )

        record_id = f"art_activity:{suffix}"
        cases.append(
            _case(
                group="art_provenance_cannot_override_sexual_activity",
                expected_category=SEXUAL_CATEGORY,
                expected_action=AGE_RESTRICT_BLOCK_ACTION,
                expected_status="explicit_adult_visual_content_restricted",
                visual=_visual(
                    record_id,
                    boundary="explicit_adult_sexual_content",
                    explicit_sexual_activity=True,
                    adult_status_verified=True,
                ),
                provenance=_provenance(
                    record_id, context_type="verified_artwork"
                ),
            )
        )

        for group, visual_overrides in (
            ("age_ambiguous_fails_closed", {"age_ambiguous": True}),
            ("child_risk_fails_closed", {"child_risk_detected": True}),
        ):
            record_id = f"{group}:{suffix}"
            cases.append(
                _case(
                    group=group,
                    expected_category=UNCERTAIN_CATEGORY,
                    expected_action=REVIEW_ACTION,
                    expected_status="child_or_age_safety_boundary_requires_review",
                    visual=_visual(
                        record_id,
                        boundary="verified_art_culture_or_education",
                        **visual_overrides,
                    ),
                    provenance=_provenance(
                        record_id, context_type="verified_artwork"
                    ),
                )
            )

        record_id = f"decode_failure:{suffix}"
        cases.append(
            _case(
                group="avif_or_video_decode_failure_review",
                content_type="video" if index % 2 else "image",
                expected_category=UNCERTAIN_CATEGORY,
                expected_action=REVIEW_ACTION,
                expected_status="visual_evidence_incomplete_or_unvalidated",
                visual=_visual(
                    record_id,
                    content_type="video" if index % 2 else "image",
                    boundary="safe_or_other",
                    decode_status="unsupported" if index % 2 else "failed",
                    sample_coverage=0.0,
                ),
                provenance=None,
            )
        )

        record_id = f"low_confidence:{suffix}"
        cases.append(
            _case(
                group="low_confidence_art_cannot_allow",
                expected_category=UNCERTAIN_CATEGORY,
                expected_action=REVIEW_ACTION,
                expected_status="visual_evidence_incomplete_or_unvalidated",
                visual=_visual(
                    record_id,
                    boundary="verified_art_culture_or_education",
                    confidence=0.84,
                ),
                provenance=_provenance(
                    record_id, context_type="verified_artwork"
                ),
            )
        )

        record_id = f"owner:{suffix}"
        preserved_owner = (
            "Child Exploitation" if index % 2 else "Sexual Harassment"
        )
        cases.append(
            _case(
                group="established_category_owner_isolation",
                existing_category=preserved_owner,
                expected_category=preserved_owner,
                expected_action=None,
                expected_status="blocked_by_established_category_owner",
                visual=_visual(
                    record_id,
                    boundary="verified_art_culture_or_education",
                ),
                provenance=_provenance(
                    record_id, context_type="verified_artwork"
                ),
            )
        )

        record_id = f"ordinary_intimacy:{suffix}"
        cases.append(
            _case(
                group="ordinary_non_explicit_intimacy_review",
                expected_category=UNCERTAIN_CATEGORY,
                expected_action=WARNING_REVIEW_ACTION,
                expected_status="non_explicit_intimacy_warning_review",
                visual=_visual(
                    record_id,
                    boundary="non_explicit_intimacy",
                    non_explicit_intimacy=True,
                ),
            )
        )

        record_id = f"ordinary_explicit:{suffix}"
        cases.append(
            _case(
                group="ordinary_explicit_adult_restricted",
                expected_category=SEXUAL_CATEGORY,
                expected_action=AGE_RESTRICT_BLOCK_ACTION,
                expected_status="explicit_adult_visual_content_restricted",
                visual=_visual(
                    record_id,
                    boundary="explicit_adult_sexual_content",
                    visible_private_parts=True,
                    adult_status_verified=True,
                ),
            )
        )

    return cases


def main() -> None:
    print("CAPTIONLESS VISUAL POLICY V8 RC2 DEVELOPMENT")
    print("=" * 60)
    print("Synthetic signed evidence is used; no raw media or holdout is opened.\n")

    cases = build_cases()
    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    failures: list[dict[str, Any]] = []
    action_contract_failures = 0
    art_allow_contract_failures = 0
    screen_auto_allow_failures = 0
    llm_authority_failures = 0
    age_inference_failures = 0
    category_mix_failures = 0

    for case in cases:
        result = analyze_captionless_visual_policy_v8_rc2(
            content_type=case["content_type"],
            existing_category=case["existing_category"],
            visual_evidence=case["visual"],
            provenance_evidence=case["provenance"],
            llm_analysis=case["llm"],
        )
        group = case["group"]
        group_totals[group] += 1
        correct = bool(
            result.get("category") == case["expected_category"]
            and result.get("action") == case["expected_action"]
            and result.get("status") == case["expected_status"]
            and bool(result.get("art_auto_allow_policy_eligible"))
            == case["expect_art_allow_eligible"]
        )
        if correct:
            group_correct[group] += 1
        else:
            failures.append(
                {
                    "group": group,
                    "expected_category": case["expected_category"],
                    "actual_category": result.get("category"),
                    "expected_action": case["expected_action"],
                    "actual_action": result.get("action"),
                    "expected_status": case["expected_status"],
                    "actual_status": result.get("status"),
                }
            )

        if result.get("automatic_enforcement_allowed") is not False:
            action_contract_failures += 1
        if (
            result.get("art_auto_allow_policy_eligible")
            and case["group"]
            not in {
                "verified_artwork_auto_allow",
                "verified_monument_auto_allow",
                "verified_education_auto_allow",
            }
        ):
            art_allow_contract_failures += 1
        context_type = str((case["provenance"] or {}).get("context_type", ""))
        if context_type in {"film", "movie", "television_series", "tv_series"}:
            if result.get("action") == ALLOW_ACTION:
                screen_auto_allow_failures += 1
        if case["group"] == "llm_only_art_claim_cannot_allow":
            if result.get("action") == ALLOW_ACTION:
                llm_authority_failures += 1
        if result.get("age_inferred_from_pixels") is not False:
            age_inference_failures += 1
        if case["group"] == "established_category_owner_isolation":
            if result.get("category") != case["existing_category"]:
                category_mix_failures += 1

    correct_count = len(cases) - len(failures)
    accuracy = correct_count / len(cases) if cases else 0.0
    group_scores = {
        group: group_correct[group] / total
        for group, total in sorted(group_totals.items())
    }
    minimum_group_accuracy = min(group_scores.values(), default=0.0)
    gate_checks = {
        "accuracy": accuracy >= 0.95,
        "minimum_group_accuracy": minimum_group_accuracy >= 0.90,
        "action_contract": action_contract_failures == 0,
        "art_auto_allow_contract": art_allow_contract_failures == 0,
        "screen_media_never_auto_allows": screen_auto_allow_failures == 0,
        "llm_has_no_allow_authority": llm_authority_failures == 0,
        "age_not_inferred_from_pixels": age_inference_failures == 0,
        "category_owner_isolation": category_mix_failures == 0,
    }
    passed = all(gate_checks.values())

    report = {
        "candidate": "captionless-visual-policy-v8-rc2",
        "records": len(cases),
        "accuracy": accuracy,
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": {
            group: {
                "correct": group_correct[group],
                "records": group_totals[group],
                "accuracy": score,
            }
            for group, score in group_scores.items()
        },
        "failures": failures,
        "contract_failures": {
            "action": action_contract_failures,
            "art_auto_allow": art_allow_contract_failures,
            "screen_auto_allow": screen_auto_allow_failures,
            "llm_authority": llm_authority_failures,
            "age_inference": age_inference_failures,
            "category_mix": category_mix_failures,
        },
        "gate_checks": gate_checks,
        "passed_development_gate": passed,
        "raw_media_used": False,
        "independent_holdout_opened": False,
        "copyrighted_user_examples_used": False,
        "synthetic_signed_evidence_only": True,
        "frozen_rc1_modified": False,
        "automatic_allow_enabled": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("CAPTIONLESS VISUAL POLICY V8 RC2 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Records: {len(cases)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Action-contract failures: {action_contract_failures}")
    print(f"Art auto-Allow contract failures: {art_allow_contract_failures}")
    print(f"Film/TV auto-Allow failures: {screen_auto_allow_failures}")
    print(f"LLM-authority failures: {llm_authority_failures}")
    print(f"Age-inference failures: {age_inference_failures}")
    print(f"Category-mix failures: {category_mix_failures}\n")
    print("GROUP RESULTS")
    print("-" * 60)
    for group, score in group_scores.items():
        print(
            f"{group}: {group_correct[group]}/{group_totals[group]} "
            f"({score * 100:.2f}%)"
        )
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print("Verified art/culture/education is the only automatic-Allow policy route.")
    print("Film and television identity never creates Allow.")
    print("Unsupported or incomplete AVIF/video decoding fails closed to review.")
    print("Frozen RC1 modified: False")
    print("Independent holdout opened: False")
    print("Automatic Allow enabled: False")
    print("Connected to live moderation: False")
    print("This is an evidence-routing policy contract, not visual-model accuracy.")

    if not passed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
