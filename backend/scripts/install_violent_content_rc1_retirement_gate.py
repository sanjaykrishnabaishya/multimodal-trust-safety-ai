from __future__ import annotations

import shutil
from pathlib import Path


IMPORT_OLD = """from app.services.multimodal_capability_gate_service import (
    apply_multimodal_capability_gate,
    get_multimodal_capability_status,
)
"""

IMPORT_NEW = """from app.services.multimodal_capability_gate_service import (
    apply_multimodal_capability_gate,
    apply_violent_content_readiness_gate,
    get_multimodal_capability_status,
)
"""

TEXT_DECISION = """    decision = (
        fuse_moderation_decision(
            text=cleaned_text,
            source_context=(
                request.source_context
            ),
            input_sources=[\"text\"],
        )
    )

"""

TEXT_GATE = """    decision, readiness_warnings = (
        apply_violent_content_readiness_gate(
            decision=decision,
        )
    )

"""

TEXT_WARNINGS_OLD = """    warnings = list(
        fusion_warnings
    )
"""

TEXT_WARNINGS_NEW = """    warnings = (
        list(fusion_warnings)
        + list(readiness_warnings)
    )
"""

FILE_DECISION = """    decision = (
        fuse_moderation_decision(
            text=combined_text,
            source_context=(
                source_context
            ),
            input_sources=(
                input_sources
            ),
        )
    )

"""

FILE_GATE = """    decision, readiness_warnings = (
        apply_violent_content_readiness_gate(
            decision=decision,
        )
    )

"""

FILE_WARNINGS_OLD = """    warnings = (
        list(extraction_warnings)
        + list(fusion_warnings)
        + list(capability_warnings)
    )
"""

FILE_WARNINGS_NEW = """    warnings = (
        list(extraction_warnings)
        + list(fusion_warnings)
        + list(readiness_warnings)
        + list(capability_warnings)
    )
"""


TEST_CODE = '''from app.services.multimodal_capability_gate_service import (
    apply_violent_content_readiness_gate,
)


def violent_decision() -> dict:
    return {
        "category": "Violent Content",
        "severity": "Low",
        "action": "Allow with sensitive-content warning",
        "confidence": 0.82,
        "human_review_required": False,
        "reason": "Violence appears in contextual material.",
        "matched_signals": ["violent_content_specialist"],
        "decision_sources": ["violent_content_specialist"],
    }


def test_failed_candidate_cannot_automatically_allow() -> None:
    result, warnings = apply_violent_content_readiness_gate(
        decision=violent_decision()
    )
    assert result["category"] == "Violent Content"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["confidence"] <= 0.75
    assert result["automatic_enforcement_allowed"] is False
    assert warnings


def test_failed_candidate_cannot_automatically_enforce() -> None:
    decision = violent_decision()
    decision["action"] = "Block immediately"
    decision["severity"] = "High"
    decision["human_review_required"] = True
    result, _ = apply_violent_content_readiness_gate(decision=decision)
    assert result["action"] == "Refer to human review"
    assert result["recommended_action_before_readiness_gate"] == "Block immediately"


def test_other_categories_are_unchanged() -> None:
    decision = violent_decision()
    decision["category"] = "Cyberbullying & Harassment"
    original = dict(decision)
    result, warnings = apply_violent_content_readiness_gate(decision=decision)
    assert result == original
    assert warnings == []
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"Expected one {label} anchor, found {count}.")
    return text.replace(old, new, 1)


def main() -> None:
    backend = Path(__file__).resolve().parents[1]
    route_path = backend / "app" / "api" / "moderation_routes.py"
    test_path = backend / "tests" / "test_violent_content_readiness_gate.py"
    source = route_path.read_text(encoding="utf-8")

    if "apply_violent_content_readiness_gate" in source:
        print("Violent Content RC1 retirement gate is already installed.")
    else:
        backup = route_path.with_suffix(".py.before_violent_rc1_retirement_gate")
        shutil.copy2(route_path, backup)
        source = replace_once(source, IMPORT_OLD, IMPORT_NEW, "import")
        source = replace_once(
            source,
            TEXT_DECISION,
            TEXT_DECISION + TEXT_GATE,
            "text decision",
        )
        source = replace_once(
            source,
            TEXT_WARNINGS_OLD,
            TEXT_WARNINGS_NEW,
            "text warnings",
        )
        source = replace_once(
            source,
            FILE_DECISION,
            FILE_DECISION + FILE_GATE,
            "file decision",
        )
        source = replace_once(
            source,
            FILE_WARNINGS_OLD,
            FILE_WARNINGS_NEW,
            "file warnings",
        )
        route_path.write_text(source, encoding="utf-8")
        print(f"Updated: {route_path}")
        print(f"Backup: {backup}")

    test_path.write_text(TEST_CODE, encoding="utf-8")
    print(f"Tests written: {test_path}")
    print("Frozen V2 RC1 service files were not modified.")


if __name__ == "__main__":
    main()
