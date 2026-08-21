from __future__ import annotations

import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.captionless_visual_safe_context_v5_service import (
    ALLOW_ACTION,
    NORMAL_CATEGORY,
    UNCERTAIN_CATEGORY,
    analyze_captionless_visual_safe_context_v5,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "captionless_visual_safe_context_v5_development"
    / "report.json"
)
MISMATCH_PATH = REPORT_PATH.with_name("mismatches.json")
ARTIFACT_HASH = "a" * 64
VERDICT_HASH = "b" * 64


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


def verified_evidence(context_type: str, *, content_type: str) -> dict[str, Any]:
    return {
        "safe_context_claimed": True,
        "context_type": context_type,
        "evidence_source": "signed_visual_pipeline",
        "visual_context_component_ready": True,
        "independently_validated": True,
        "model_id": "development-visual-context-candidate",
        "model_revision": "pinned-development-revision",
        "artifact_sha256": ARTIFACT_HASH,
        "readiness_verdict_sha256": VERDICT_HASH,
        "context_confidence": 0.98,
        "sample_coverage": 1.0 if content_type == "image" else 0.95,
        "cultural_context_verified": context_type
        in {"recognized_artwork", "recognized_monument"},
        "educational_context_verified": context_type
        == "verified_educational_material",
        "sexual_safety_component_ready": True,
        "child_safety_component_ready": True,
        "no_visible_explicit_sexual_detail": True,
        "sexual_content_risk_detected": False,
        "child_exploitation_risk_detected": False,
        "sexual_harassment_risk_detected": False,
        "self_report_only": False,
        "llm_only": False,
    }


def cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    safe_groups = (
        ("captionless_verified_artwork", "recognized_artwork", "image"),
        ("captionless_verified_monument", "recognized_monument", "image"),
        (
            "captionless_verified_educational_material",
            "verified_educational_material",
            "video",
        ),
    )
    for group, context_type, content_type in safe_groups:
        for index in range(20):
            rows.append(
                {
                    "record_id": f"{group.upper()}-{index + 1:03d}",
                    "group": group,
                    "expected": "allow",
                    "text": "",
                    "content_type": content_type,
                    "existing_category": "Normal/Ignore",
                    "visual": verified_evidence(context_type, content_type=content_type),
                }
            )

    for index in range(20):
        visual = verified_evidence("recognized_artwork", content_type="image")
        visual.update(
            {
                "independently_validated": False,
                "self_report_only": index % 2 == 0,
                "llm_only": index % 2 == 1,
            }
        )
        rows.append(
            {
                "record_id": f"UNVERIFIED-SAFE-CLAIM-{index + 1:03d}",
                "group": "self_report_or_llm_only_cannot_allow",
                "expected": "review",
                "text": "",
                "content_type": "image",
                "existing_category": "Normal/Ignore",
                "visual": visual,
            }
        )

    for index in range(20):
        content_type = "video" if index % 2 else "image"
        visual = verified_evidence(
            "verified_educational_material", content_type=content_type
        )
        if index % 2:
            visual["sample_coverage"] = 0.50
        else:
            visual["context_confidence"] = 0.70
        rows.append(
            {
                "record_id": f"LOW-CONFIDENCE-COVERAGE-{index + 1:03d}",
                "group": "low_confidence_or_coverage_cannot_allow",
                "expected": "review",
                "text": "",
                "content_type": content_type,
                "existing_category": "Normal/Ignore",
                "visual": visual,
            }
        )

    for index in range(20):
        visual = verified_evidence("recognized_monument", content_type="image")
        if index % 2:
            visual["child_exploitation_risk_detected"] = True
        else:
            visual["sexual_content_risk_detected"] = True
            visual["no_visible_explicit_sexual_detail"] = False
        rows.append(
            {
                "record_id": f"SAFETY-CONFLICT-{index + 1:03d}",
                "group": "sexual_or_child_safety_conflict_cannot_allow",
                "expected": "review",
                "text": "",
                "content_type": "image",
                "existing_category": "Normal/Ignore",
                "visual": visual,
            }
        )

    owners = (
        "Child Exploitation",
        "Sexual Harassment",
        "Cyberbullying & Harassment",
        "Hate Speech & Discrimination",
        "Dangerous Content",
    )
    for index in range(20):
        rows.append(
            {
                "record_id": f"OWNER-ISOLATION-{index + 1:03d}",
                "group": "established_category_owner_isolation",
                "expected": "owner_preserved",
                "text": "",
                "content_type": "image",
                "existing_category": owners[index % len(owners)],
                "visual": verified_evidence("recognized_artwork", content_type="image"),
            }
        )

    for index in range(20):
        rows.append(
            {
                "record_id": f"NO-SPECIAL-CONTEXT-{index + 1:03d}",
                "group": "ordinary_captionless_media_no_special_allow",
                "expected": "no_override",
                "text": "",
                "content_type": "video" if index % 2 else "image",
                "existing_category": "Normal/Ignore",
                "visual": {},
            }
        )
    if len(rows) != 160:
        raise RuntimeError(f"Expected 160 cases; found {len(rows)}")
    return rows


def predicted_contract(result: dict[str, Any], existing_category: str | None) -> str:
    if result.get("v5_status") == "blocked_by_established_category_owner":
        return "owner_preserved"
    if result.get("category") == NORMAL_CATEGORY and result.get("action") == ALLOW_ACTION:
        return "allow"
    if (
        result.get("category") == UNCERTAIN_CATEGORY
        and result.get("action") == "Refer to human review"
    ):
        return "review"
    if result.get("decision_applied") is not True:
        return "no_override"
    return "other"


def main() -> None:
    rows = cases()
    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    action_contract_failures = 0
    caption_dependency_failures = 0
    safety_override_failures = 0
    category_mix_failures = 0
    proof_contract_failures = 0
    results: list[dict[str, Any]] = []

    for row in rows:
        result = analyze_captionless_visual_safe_context_v5(
            row["text"],
            content_type=row["content_type"],
            existing_category=row["existing_category"],
            extracted_evidence={},
            visual_context_evidence=row["visual"],
        )
        predicted = predicted_contract(result, row["existing_category"])
        correct = predicted == row["expected"]
        group_totals[row["group"]] += 1
        group_correct[row["group"]] += int(correct)
        action_failure = bool(
            predicted == "allow"
            and (
                result.get("category") != NORMAL_CATEGORY
                or result.get("action") != ALLOW_ACTION
                or result.get("automatic_enforcement_allowed") is not False
                or result.get("automatic_allow_allowed") is not False
            )
        )
        caption_failure = bool(
            row["expected"] == "allow"
            and not row["text"]
            and predicted != "allow"
        )
        safety_failure = bool(
            row["group"] == "sexual_or_child_safety_conflict_cannot_allow"
            and predicted == "allow"
        )
        mix_failure = bool(
            row["expected"] == "owner_preserved"
            and result.get("visual_safe_context_used") is True
        )
        proof_failure = bool(
            predicted == "allow"
            and not all(
                result.get("visual_safe_context_evidence", {})
                .get("contract_checks", {})
                .values()
            )
        )
        action_contract_failures += int(action_failure)
        caption_dependency_failures += int(caption_failure)
        safety_override_failures += int(safety_failure)
        category_mix_failures += int(mix_failure)
        proof_contract_failures += int(proof_failure)
        results.append(
            {
                "record_id": row["record_id"],
                "group": row["group"],
                "expected": row["expected"],
                "predicted": predicted,
                "correct": correct,
                "status": result.get("v5_status"),
                "caption_present": bool(row["text"]),
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
        and caption_dependency_failures == 0
        and safety_override_failures == 0
        and category_mix_failures == 0
        and proof_contract_failures == 0
    )
    mismatches = [item for item in results if not item["correct"]]
    report = {
        "evaluation": "captionless_visual_safe_context_v5_development",
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "case_definition_sha256": canonical_hash(rows),
        "records": len(rows),
        "accuracy_percent": round(accuracy * 100, 2),
        "minimum_group_accuracy_percent": round(minimum_group_accuracy * 100, 2),
        "action_contract_failures": action_contract_failures,
        "caption_dependency_failures": caption_dependency_failures,
        "safety_override_failures": safety_override_failures,
        "category_mix_failures": category_mix_failures,
        "proof_contract_failures": proof_contract_failures,
        "group_results": {
            group: {
                "correct": group_correct[group],
                "total": total,
                "accuracy_percent": round(group_correct[group] / total * 100, 2),
            }
            for group, total in sorted(group_totals.items())
        },
        "passed_development_gate": passed,
        "captionless_visual_recognition_executed": False,
        "synthetic_signed_visual_evidence_used": True,
        "local_llm_executed": False,
        "local_llm_connected": False,
        "frozen_rc1_modified": False,
        "automatic_enforcement_allowed": False,
        "automatic_allow_allowed": False,
        "connected_to_live_moderation": False,
    }
    write_json(REPORT_PATH, report)
    write_json(MISMATCH_PATH, mismatches)

    print("CAPTIONLESS ART/CULTURE/EDUCATION SAFE-CONTEXT V5 DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {len(rows)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Action-contract failures: {action_contract_failures}")
    print(f"Caption-dependency failures: {caption_dependency_failures}")
    print(f"Safety-override failures: {safety_override_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Proof-contract failures: {proof_contract_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, total in sorted(group_totals.items()):
        correct = group_correct[group]
        print(f"{group}: {correct}/{total} ({correct / total * 100:.2f}%)")
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Captionless visual recognition executed: False")
    print("Synthetic signed visual evidence used: True")
    print("Local Qwen connected: False")
    print("Frozen RC1 modified: False")
    print("Automatic Allow enabled: False")
    print("Connected to live moderation: False")
    print("This is a policy contract, not visual-model accuracy evidence.")


if __name__ == "__main__":
    main()
