from __future__ import annotations

import shutil
from datetime import datetime
from pathlib import Path


ROOT_DIRECTORY = Path(__file__).resolve().parents[2]
FUSION_PATH = (
    ROOT_DIRECTORY / "backend" / "app" / "services" / "fusion_service.py"
)


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} anchor, found {count}. "
            "No review-boundary changes were written."
        )
    return text.replace(old, new, 1)


def main() -> None:
    original = FUSION_PATH.read_text(encoding="utf-8")
    if "apply_graphic_depiction_review_boundary" in original:
        raise RuntimeError("The graphic-depiction review boundary is already installed.")
    updated = original

    import_anchor = '''from app.services.cyberbullying_depiction_boundary_service import (
    analyze_cyberbullying_depiction_boundary,
)
'''
    updated = replace_once(
        updated,
        import_anchor,
        '''from app.services.cyberbullying_depiction_boundary_service import (
    analyze_cyberbullying_depiction_boundary,
    apply_graphic_depiction_review_boundary,
)
''',
        "import",
    )

    application_anchor = '''    cyberbullying_rc2_applied = bool(
        cyberbullying_rc2_fusion["decision_applied"]
    )

'''
    application_block = '''    graphic_depiction_review_boundary = (
        apply_graphic_depiction_review_boundary(
            category=category,
            severity=severity,
            action=action,
            confidence=confidence,
            human_review_required=human_review_required,
            reason=reason,
            matched_signals=matched_signals,
            analysis=cyberbullying_depiction_boundary_analysis,
        )
    )
    category = str(graphic_depiction_review_boundary["category"])
    severity = str(graphic_depiction_review_boundary["severity"])
    action = str(graphic_depiction_review_boundary["action"])
    confidence = float(graphic_depiction_review_boundary["confidence"])
    human_review_required = bool(
        graphic_depiction_review_boundary["human_review_required"]
    )
    reason = str(graphic_depiction_review_boundary["reason"])
    matched_signals = list(
        graphic_depiction_review_boundary["matched_signals"]
    )
    graphic_depiction_review_applied = bool(
        graphic_depiction_review_boundary["decision_applied"]
    )

'''
    updated = replace_once(
        updated,
        application_anchor,
        application_anchor + application_block,
        "application",
    )

    model_anchor = '''            + (
                ["cyberbullying_abusive_rc2"]
                if cyberbullying_rc2_applied
                else []
            )
'''
    updated = replace_once(
        updated,
        model_anchor,
        model_anchor
        + '''            + (
                ["graphic_depiction_review_boundary"]
                if graphic_depiction_review_applied
                else []
            )
''',
        "model list",
    )

    result_anchor = '''        "cyberbullying_depiction_boundary": (
            cyberbullying_depiction_boundary_analysis
        ),
'''
    updated = replace_once(
        updated,
        result_anchor,
        result_anchor
        + '''        "graphic_depiction_review_boundary_used": (
            graphic_depiction_review_applied
        ),
        "graphic_depiction_review_boundary_status": (
            graphic_depiction_review_boundary["boundary_status"]
        ),
''',
        "result",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = FUSION_PATH.with_name(
        FUSION_PATH.name + f".before_graphic_depiction_review_{timestamp}"
    )
    shutil.copy2(FUSION_PATH, backup)
    FUSION_PATH.write_text(updated, encoding="utf-8")

    print("Graphic-depiction fail-closed review boundary installed.")
    print(f"Updated: {FUSION_PATH}")
    print(f"Backup: {backup}")
    print("Frozen candidates modified: False")
    print("Unvalidated Violent Content verdict claimed: False")
    print("Automatic enforcement allowed: False")
    print("Required fallback: Uncertain and human review")


if __name__ == "__main__":
    main()

