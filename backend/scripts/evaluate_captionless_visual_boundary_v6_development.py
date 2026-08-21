from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.captionless_visual_boundary_v6_service import (
    AGE_RESTRICT_BLOCK_ACTION,
    ALLOW_ACTION,
    ALLOW_WARNING_REVIEW_ACTION,
    NORMAL_CATEGORY,
    SEXUAL_CATEGORY,
    UNCERTAIN_CATEGORY,
    analyze_captionless_visual_boundary_v6,
)


ROOT = Path(__file__).resolve().parents[2]
SEED_MANIFEST = (
    ROOT
    / "datasets"
    / "development"
    / "captionless_visual_boundary_v6"
    / "seed_manifest.json"
)
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_boundary_v6_development"
    / "report.json"
)
MISMATCH_PATH = REPORT_PATH.with_name("mismatches.json")
ARTIFACT_HASH = "c" * 64
VERDICT_HASH = "d" * 64


def canonical_hash(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def evidence(**overrides: Any) -> dict[str, Any]:
    value = {
        "evidence_source": "signed_visual_pipeline",
        "visual_pipeline_ready": True,
        "independently_validated": True,
        "model_id": "captionless-visual-development-candidate",
        "model_revision": "pinned-development-revision",
        "artifact_sha256": ARTIFACT_HASH,
        "verdict_sha256": VERDICT_HASH,
        "classification_confidence": 0.98,
        "adult_confidence": 0.98,
        "sample_coverage": 1.0,
        "context_type": "ordinary_live_action",
        "art_culture_or_education_verified": False,
        "non_explicit_intimacy": False,
        "visible_nudity": False,
        "visible_private_parts": False,
        "explicit_sexual_activity": False,
        "fully_obscured": False,
        "no_explicit_detail_visible": False,
        "age_ambiguous": False,
        "child_risk_detected": False,
        "self_report_only": False,
        "llm_only": False,
    }
    value.update(overrides)
    return value


def generated_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    definitions = (
        (
            "verified_art_culture_education_allow",
            "allow",
            lambda index: evidence(
                context_type=(
                    "recognized_artwork"
                    if index % 3 == 0
                    else "recognized_monument"
                    if index % 3 == 1
                    else "verified_educational_material"
                ),
                art_culture_or_education_verified=True,
                visible_nudity=index % 2 == 0,
                visible_private_parts=index % 4 == 0,
            ),
        ),
        (
            "non_explicit_intimacy_warning_review",
            "allow_warning_review",
            lambda index: evidence(
                non_explicit_intimacy=True,
                age_ambiguous=index % 2 == 0,
            ),
        ),
        (
            "explicit_adult_nudity_block",
            "block",
            lambda index: evidence(
                visible_nudity=True,
                visible_private_parts=True,
            ),
        ),
        (
            "explicit_adult_activity_block",
            "block",
            lambda index: evidence(
                explicit_sexual_activity=True,
                visible_nudity=index % 2 == 0,
            ),
        ),
        (
            "validated_full_obscuration_allow",
            "allow",
            lambda index: evidence(
                fully_obscured=True,
                no_explicit_detail_visible=True,
                visible_nudity=True,
            ),
        ),
        (
            "uncertain_or_unvalidated_review",
            "review",
            lambda index: evidence(
                independently_validated=index % 2 == 0,
                classification_confidence=0.60 if index % 2 == 0 else 0.98,
                self_report_only=index % 2 == 1,
            ),
        ),
        (
            "child_safety_boundary_review",
            "review",
            lambda index: evidence(child_risk_detected=True),
        ),
        (
            "established_category_owner_isolation",
            "owner_preserved",
            lambda index: evidence(visible_nudity=True),
        ),
    )
    owners = (
        "Child Exploitation",
        "Sexual Harassment",
        "Cyberbullying & Harassment",
        "Hate Speech & Discrimination",
    )
    for group, expected, factory in definitions:
        for index in range(20):
            rows.append(
                {
                    "record_id": f"{group.upper()}-{index + 1:03d}",
                    "group": group,
                    "expected": expected,
                    "content_type": "image",
                    "existing_category": (
                        owners[index % len(owners)]
                        if group == "established_category_owner_isolation"
                        else "Normal/Ignore"
                    ),
                    "visual_evidence": factory(index),
                }
            )
    return rows


def seed_evidence(record: dict[str, Any]) -> dict[str, Any]:
    boundary = str(record["boundary"])
    if boundary == "verified_art_culture_or_education":
        return evidence(
            context_type=record["context_type"],
            art_culture_or_education_verified=True,
            visible_nudity=True,
            visible_private_parts=True,
        )
    if boundary == "non_explicit_intimacy":
        return evidence(non_explicit_intimacy=True, age_ambiguous=True)
    if boundary == "explicit_adult_sexual_content":
        return evidence(
            visible_nudity=True,
            visible_private_parts=True,
            explicit_sexual_activity=record["media_type"] == "video",
        )
    raise RuntimeError(f"Unknown seed boundary: {boundary}")


def expected_contract(record: dict[str, Any]) -> str:
    action = str(record["expected_action"])
    if action == ALLOW_ACTION:
        return "allow"
    if action == ALLOW_WARNING_REVIEW_ACTION:
        return "allow_warning_review"
    if action == AGE_RESTRICT_BLOCK_ACTION:
        return "block"
    raise RuntimeError(f"Unsupported seed action: {action}")


def predicted_contract(result: dict[str, Any]) -> str:
    if result.get("v6_status") == "blocked_by_established_category_owner":
        return "owner_preserved"
    if result.get("category") == NORMAL_CATEGORY and result.get("action") == ALLOW_ACTION:
        return "allow"
    if (
        result.get("category") == UNCERTAIN_CATEGORY
        and result.get("action") == ALLOW_WARNING_REVIEW_ACTION
    ):
        return "allow_warning_review"
    if (
        result.get("category") == SEXUAL_CATEGORY
        and result.get("action") == AGE_RESTRICT_BLOCK_ACTION
    ):
        return "block"
    if result.get("category") == UNCERTAIN_CATEGORY:
        return "review"
    return "other"


def main() -> None:
    if not SEED_MANIFEST.is_file():
        raise FileNotFoundError(
            "Seed manifest is missing. Run import_captionless_visual_boundary_v6_seeds first."
        )
    manifest = json.loads(SEED_MANIFEST.read_text(encoding="utf-8"))
    seeds = manifest.get("records", [])
    if not isinstance(seeds, list) or len(seeds) != 8:
        raise RuntimeError("Expected exactly eight user-confirmed seed records.")

    rows = generated_cases()
    for record in seeds:
        rows.append(
            {
                "record_id": record["record_id"],
                "group": "user_confirmed_seed_boundaries",
                "expected": expected_contract(record),
                "content_type": record["media_type"],
                "existing_category": "Normal/Ignore",
                "visual_evidence": seed_evidence(record),
            }
        )

    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    action_contract_failures = 0
    human_review_contract_failures = 0
    category_mix_failures = 0
    processing_errors = 0
    results: list[dict[str, Any]] = []
    for row in rows:
        try:
            result = analyze_captionless_visual_boundary_v6(
                "",
                content_type=row["content_type"],
                existing_category=row["existing_category"],
                visual_evidence=row["visual_evidence"],
            )
        except Exception as exc:
            processing_errors += 1
            results.append(
                {
                    "record_id": row["record_id"],
                    "group": row["group"],
                    "expected": row["expected"],
                    "predicted": "processing_error",
                    "correct": False,
                    "error_type": type(exc).__name__,
                }
            )
            continue
        predicted = predicted_contract(result)
        correct = predicted == row["expected"]
        group_totals[row["group"]] += 1
        group_correct[row["group"]] += int(correct)
        expected_review = row["expected"] in {"allow_warning_review", "review"}
        review_failure = result.get("human_review_required") is not expected_review
        action_failure = bool(
            (row["expected"] == "block" and result.get("human_review_required") is True)
            or (
                row["expected"] == "allow_warning_review"
                and result.get("action") != ALLOW_WARNING_REVIEW_ACTION
            )
        )
        mix_failure = bool(
            row["expected"] == "owner_preserved"
            and result.get("visual_boundary_used") is True
        )
        human_review_contract_failures += int(review_failure)
        action_contract_failures += int(action_failure)
        category_mix_failures += int(mix_failure)
        results.append(
            {
                "record_id": row["record_id"],
                "group": row["group"],
                "expected": row["expected"],
                "predicted": predicted,
                "correct": correct,
                "status": result.get("v6_status"),
            }
        )

    correct_count = sum(item["correct"] for item in results)
    accuracy = correct_count / len(rows)
    minimum_group_accuracy = min(
        group_correct[group] / total for group, total in group_totals.items()
    )
    passed = bool(
        accuracy >= 0.95
        and minimum_group_accuracy >= 0.90
        and action_contract_failures == 0
        and human_review_contract_failures == 0
        and category_mix_failures == 0
        and processing_errors == 0
    )
    mismatches = [item for item in results if not item["correct"]]
    report = {
        "evaluation": "captionless_visual_boundary_v6_development",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "records": len(rows),
        "user_confirmed_seed_records": len(seeds),
        "synthetic_policy_records": len(rows) - len(seeds),
        "case_definition_sha256": canonical_hash(rows),
        "accuracy_percent": round(accuracy * 100, 2),
        "minimum_group_accuracy_percent": round(minimum_group_accuracy * 100, 2),
        "action_contract_failures": action_contract_failures,
        "human_review_contract_failures": human_review_contract_failures,
        "category_mix_failures": category_mix_failures,
        "processing_errors": processing_errors,
        "group_results": {
            group: {
                "correct": group_correct[group],
                "total": total,
                "accuracy_percent": round(group_correct[group] / total * 100, 2),
            }
            for group, total in sorted(group_totals.items())
        },
        "passed_development_gate": passed,
        "raw_seed_media_copied": False,
        "visual_recognition_executed": False,
        "structured_visual_evidence_used": True,
        "local_llm_used": False,
        "training_on_seed_media_allowed": False,
        "frozen_rc1_modified": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
    }
    write_json(REPORT_PATH, report)
    write_json(MISMATCH_PATH, mismatches)

    print("CAPTIONLESS VISUAL SEXUAL-CONTENT BOUNDARY V6 DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"User-confirmed seed records: {len(seeds)}")
    print(f"Synthetic policy records: {len(rows) - len(seeds)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Action-contract failures: {action_contract_failures}")
    print(f"Human-review contract failures: {human_review_contract_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Processing errors: {processing_errors}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, total in sorted(group_totals.items()):
        correct = group_correct[group]
        print(f"{group}: {correct}/{total} ({correct / total * 100:.2f}%)")
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Raw seed media copied: False")
    print("Visual recognition executed: False")
    print("Local LLM used: False")
    print("Frozen RC1 modified: False")
    print("Connected to live moderation: False")
    print("This is policy-routing evidence, not visual-model accuracy.")


if __name__ == "__main__":
    main()
