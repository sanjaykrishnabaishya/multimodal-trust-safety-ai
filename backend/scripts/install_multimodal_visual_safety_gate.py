from __future__ import annotations

import shutil
from pathlib import Path


IMPORT_BLOCK = """from app.services.multimodal_capability_gate_service import (
    apply_multimodal_capability_gate,
    get_multimodal_capability_status,
)
"""

IMPORT_ANCHOR = """from app.services.moderation_service import (
    combine_extracted_signals,
)
"""

CALL_BLOCK = """    decision, capability_warnings = (
        apply_multimodal_capability_gate(
            decision=decision,
            content_type=content_type,
        )
    )

"""

FILE_DECISION_ANCHOR = """    decision = (
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

WARNING_OLD = """    warnings = list(
        extraction_warnings
    ) + list(
        fusion_warnings
    )
"""

WARNING_NEW = """    warnings = (
        list(extraction_warnings)
        + list(fusion_warnings)
        + list(capability_warnings)
    )
"""

HEALTH_OLD = """        \"visual_model_connected\": True,
        \"ocr_connected\": True,
"""

HEALTH_NEW = """        \"visual_model_connected\": True,
        \"visual_description_connected\": True,
        \"visual_violence_independently_validated\": False,
        \"automatic_visual_safety_confirmation_allowed\": False,
        \"multimodal_capability_gate\": (
            get_multimodal_capability_status()
        ),
        \"ocr_connected\": True,
"""

SCHEMA_CONTENT_ANCHOR = """ContentType = Literal[
    \"text\",
    \"document\",
    \"image\",
    \"video\",
]
"""

SCHEMA_CONTENT_REPLACEMENT = """ContentType = Literal[
    \"text\",
    \"document\",
    \"image\",
    \"video\",
]

# Uncertain is a decision state, not an additional policy category.
DecisionCategory = ModerationCategory | Literal[\"Uncertain\"]
"""

SCHEMA_CATEGORY_OLD = """    category: ModerationCategory
"""

SCHEMA_CATEGORY_NEW = """    category: DecisionCategory
"""

SCHEMA_VALIDATOR_ANCHOR = """        try:
            return (
                normalize_category_name(
                    value
                )
            )
"""

SCHEMA_VALIDATOR_REPLACEMENT = """        if value.strip() == \"Uncertain\":
            return \"Uncertain\"

        try:
            return (
                normalize_category_name(
                    value
                )
            )
"""


TEST_CODE = '''from app.services.multimodal_capability_gate_service import (
    apply_multimodal_capability_gate,
)


def base_decision(category: str = "Normal/Ignore") -> dict:
    return {
        "category": category,
        "severity": "None",
        "action": "Allow",
        "confidence": 0.7,
        "human_review_required": False,
        "reason": "No signal detected.",
        "matched_signals": [],
        "decision_sources": ["rule_engine"],
    }


def test_safe_image_is_not_automatically_confirmed() -> None:
    result, warnings = apply_multimodal_capability_gate(
        decision=base_decision(),
        content_type="image",
    )
    assert result["category"] == "Uncertain"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["confidence"] <= 0.5
    assert result["visual_safety_gate_applied"] is True
    assert warnings


def test_safe_video_is_not_automatically_confirmed() -> None:
    result, _ = apply_multimodal_capability_gate(
        decision=base_decision(),
        content_type="video",
    )
    assert result["category"] == "Uncertain"
    assert result["human_review_required"] is True


def test_text_result_is_unchanged() -> None:
    original = base_decision()
    result, warnings = apply_multimodal_capability_gate(
        decision=original,
        content_type="text",
    )
    assert result == original
    assert warnings == []


def test_detected_violation_is_not_overwritten() -> None:
    original = base_decision("Spam, Scam & Phishing")
    original["action"] = "Block and warn"
    original["human_review_required"] = True
    result, warnings = apply_multimodal_capability_gate(
        decision=original,
        content_type="image",
    )
    assert result == original
    assert warnings == []
'''


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} anchor, found {count}."
        )
    return text.replace(old, new, 1)


def main() -> None:
    backend = Path(__file__).resolve().parents[1]
    route_path = backend / "app" / "api" / "moderation_routes.py"
    schema_path = backend / "app" / "moderation_schemas.py"
    service_source = (
        Path(__file__).resolve().parents[1]
        / "app"
        / "services"
        / "multimodal_capability_gate_service.py"
    )
    test_path = backend / "tests" / "test_multimodal_capability_gate.py"

    if (
        not route_path.exists()
        or not schema_path.exists()
        or not service_source.exists()
    ):
        raise RuntimeError("Required backend files were not found.")

    schema = schema_path.read_text(encoding="utf-8")
    if "DecisionCategory =" not in schema:
        schema_backup = schema_path.with_suffix(
            ".py.before_visual_safety_gate"
        )
        shutil.copy2(schema_path, schema_backup)
        schema = replace_once(
            schema,
            SCHEMA_CONTENT_ANCHOR,
            SCHEMA_CONTENT_REPLACEMENT,
            "schema-content-type",
        )
        schema = replace_once(
            schema,
            SCHEMA_CATEGORY_OLD,
            SCHEMA_CATEGORY_NEW,
            "schema-category-field",
        )
        schema = replace_once(
            schema,
            SCHEMA_VALIDATOR_ANCHOR,
            SCHEMA_VALIDATOR_REPLACEMENT,
            "schema-category-validator",
        )
        schema_path.write_text(schema, encoding="utf-8")
        print(f"Updated: {schema_path}")
        print(f"Backup: {schema_backup}")
    else:
        print("Uncertain decision-state support is already installed.")

    source = route_path.read_text(encoding="utf-8")
    if "apply_multimodal_capability_gate" in source:
        print("Multimodal visual safety gate is already installed.")
    else:
        backup_path = route_path.with_suffix(".py.before_visual_safety_gate")
        shutil.copy2(route_path, backup_path)
        source = replace_once(
            source,
            IMPORT_ANCHOR,
            IMPORT_ANCHOR + IMPORT_BLOCK,
            "import",
        )
        source = replace_once(
            source,
            FILE_DECISION_ANCHOR,
            FILE_DECISION_ANCHOR + CALL_BLOCK,
            "file-decision-call",
        )
        source = replace_once(
            source,
            WARNING_OLD,
            WARNING_NEW,
            "warning-combination",
        )
        source = replace_once(
            source,
            HEALTH_OLD,
            HEALTH_NEW,
            "health-status",
        )
        route_path.write_text(source, encoding="utf-8")
        print(f"Updated: {route_path}")
        print(f"Backup: {backup_path}")

    test_path.write_text(TEST_CODE, encoding="utf-8")
    print(f"Tests written: {test_path}")
    print("Frozen RC1 service files were not modified.")


if __name__ == "__main__":
    main()
