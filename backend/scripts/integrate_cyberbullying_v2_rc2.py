from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
FUSION_PATH = REPO_ROOT / "backend" / "app" / "services" / "fusion_service.py"


IMPORT_ANCHOR = """from app.services.targeted_threat_service import (
    analyze_targeted_threat,
)
"""
IMPORT_REPLACEMENT = IMPORT_ANCHOR + """from app.services.cyberbullying_rc2_service import (
    analyze_cyberbullying_rc2,
    apply_cyberbullying_rc2_fusion,
)
"""

ANALYSIS_ANCHOR = """    targeted_threat_analysis = analyze_targeted_threat(text)

    identity_impersonation_analysis = (
"""
ANALYSIS_REPLACEMENT = """    targeted_threat_analysis = analyze_targeted_threat(text)
    cyberbullying_rc2_analysis = analyze_cyberbullying_rc2(
        text,
        input_sources,
    )

    identity_impersonation_analysis = (
"""

FUSION_ANCHOR = """    fact_check_result: dict[str, Any]
    fact_check_error = ""
"""
FUSION_REPLACEMENT = """    cyberbullying_rc2_fusion = apply_cyberbullying_rc2_fusion(
        category=category,
        severity=severity,
        action=action,
        confidence=confidence,
        human_review_required=human_review_required,
        reason=reason,
        matched_signals=matched_signals,
        analysis=cyberbullying_rc2_analysis,
        safe_context_confirmed=(
            (
                safe_context_detected
                and not direct_action_detected
            )
            or bool(
                identity_impersonation_analysis.get(
                    "safe_context_signals",
                    [],
                )
            )
        ),
    )
    category = str(cyberbullying_rc2_fusion["category"])
    severity = str(cyberbullying_rc2_fusion["severity"])
    action = str(cyberbullying_rc2_fusion["action"])
    confidence = float(cyberbullying_rc2_fusion["confidence"])
    human_review_required = bool(
        cyberbullying_rc2_fusion["human_review_required"]
    )
    reason = str(cyberbullying_rc2_fusion["reason"])
    matched_signals = list(cyberbullying_rc2_fusion["matched_signals"])
    cyberbullying_rc2_applied = bool(
        cyberbullying_rc2_fusion["decision_applied"]
    )

    fact_check_result: dict[str, Any]
    fact_check_error = ""
"""

SOURCE_ANCHOR = """            + (
                ["spam_dictionary"]
                if spam_analysis.get(
"""
SOURCE_REPLACEMENT = """            + (
                ["cyberbullying_abusive_rc2"]
                if cyberbullying_rc2_applied
                else []
            )
            + (
                ["spam_dictionary"]
                if spam_analysis.get(
"""

RETURN_ANCHOR = """        "targeted_threat": targeted_threat_analysis,
        "violent_content_specialist_used": (
"""
RETURN_REPLACEMENT = """        "targeted_threat": targeted_threat_analysis,
        "cyberbullying_rc2_used": cyberbullying_rc2_applied,
        "cyberbullying_rc2": cyberbullying_rc2_analysis,
        "cyberbullying_rc2_fusion_status": (
            cyberbullying_rc2_fusion["fusion_status"]
        ),
        "violent_content_specialist_used": (
"""


def replace_once(source: str, anchor: str, replacement: str, label: str) -> str:
    count = source.count(anchor)
    if count != 1:
        raise RuntimeError(
            f"Expected exactly one {label} anchor, but found {count}. "
            "No files were changed."
        )
    return source.replace(anchor, replacement, 1)


def main() -> None:
    if not FUSION_PATH.is_file():
        raise FileNotFoundError(f"Fusion service was not found: {FUSION_PATH}")

    source = FUSION_PATH.read_text(encoding="utf-8")
    marker = "cyberbullying_rc2_fusion_status"
    if marker in source:
        print("Cyberbullying/Abusive Words RC2 fusion is already installed.")
        print(f"Unchanged: {FUSION_PATH}")
        return

    updated = replace_once(source, IMPORT_ANCHOR, IMPORT_REPLACEMENT, "import")
    updated = replace_once(
        updated,
        ANALYSIS_ANCHOR,
        ANALYSIS_REPLACEMENT,
        "analysis",
    )
    updated = replace_once(updated, FUSION_ANCHOR, FUSION_REPLACEMENT, "fusion")
    updated = replace_once(
        updated,
        SOURCE_ANCHOR,
        SOURCE_REPLACEMENT,
        "decision-source",
    )
    updated = replace_once(updated, RETURN_ANCHOR, RETURN_REPLACEMENT, "return")

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    backup = FUSION_PATH.with_name(
        f"fusion_service.py.before_cyberbullying_rc2_{timestamp}"
    )
    backup.write_text(source, encoding="utf-8")
    FUSION_PATH.write_text(updated, encoding="utf-8")

    print("Cyberbullying/Abusive Words RC2 guarded fusion installed.")
    print(f"Updated: {FUSION_PATH}")
    print(f"Backup: {backup}")
    print("Automatic enforcement allowed: False")
    print("Uncertain decisions: Refer to human review")
    print("Safe prediction behavior: No boundary override")
    print("Unrelated category override allowed: False")


if __name__ == "__main__":
    main()
