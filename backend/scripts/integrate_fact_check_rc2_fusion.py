from __future__ import annotations

from pathlib import Path
import shutil


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SCRIPT_DIRECTORY.parent
TARGET_PATH = BACKEND_DIRECTORY / "app" / "services" / "fusion_service.py"
BACKUP_PATH = TARGET_PATH.with_suffix(".py.before_fact_check_rc2")


IMPORT_MARKER = """from app.services.identity_impersonation_service import (
    analyze_identity_impersonation,
)
"""

IMPORT_REPLACEMENT = IMPORT_MARKER + """from app.services.fact_check_fusion_service import (
    analyze_fact_check_for_fusion,
)
"""


FACT_CHECK_BLOCK = '''    fact_check_result: dict[str, Any]
    fact_check_error = ""

    try:
        fact_check_result = analyze_fact_check_for_fusion(
            text=text,
            current_category=safely_normalize_category(category),
        )
    except Exception as error:
        fact_check_error = f"{type(error).__name__}: {error}"
        fact_check_result = {
            "fact_check_router_used": True,
            "fact_check_analysis_used": False,
            "decision_override_allowed": False,
            "route_reason": "Fact-check processing failed safely.",
            "category": "",
            "evidence_status": "ERROR",
            "confidence": 0.0,
            "action": "",
            "human_review_required": False,
            "automatic_enforcement_allowed": False,
            "analysis": {},
        }

    fact_check_analysis_used = bool(
        fact_check_result.get("fact_check_analysis_used", False)
    )

    fact_check_override_allowed = bool(
        fact_check_result.get("decision_override_allowed", False)
    )

    if fact_check_analysis_used and fact_check_override_allowed:
        fact_check_category = str(
            fact_check_result.get("category", "Uncertain")
        )
        fact_check_status = str(
            fact_check_result.get(
                "evidence_status",
                "NOT_ENOUGH_INFO",
            )
        )
        fact_check_confidence = min(
            0.80,
            float(fact_check_result.get("confidence", 0.50)),
        )
        fact_check_analysis = dict(
            fact_check_result.get("analysis", {})
        )

        category = fact_check_category
        confidence = fact_check_confidence
        action = str(
            fact_check_result.get(
                "action",
                "Refer to human review",
            )
        )
        human_review_required = bool(
            fact_check_result.get(
                "human_review_required",
                True,
            )
        )

        if fact_check_status == "SUPPORTS":
            severity = "None"
        elif fact_check_status == "REFUTES":
            severity = (
                "High"
                if fact_check_analysis.get("high_impact_claim", False)
                else "Medium"
            )
        else:
            severity = "Unknown"

        reason = str(
            fact_check_analysis.get(
                "reason",
                (
                    "The fact-check component could not reach a "
                    "sufficiently supported conclusion."
                ),
            )
        )

        matched_signals.append(
            "fact_check_rc2:" + fact_check_status.casefold()
        )

'''


SOURCE_BLOCK = '''            + (
                ["fact_check_rc2"]
                if fact_check_analysis_used
                else []
            )
'''


WARNING_BLOCK = '''    if fact_check_error:
        warnings.append(
            f"Fact-check warning: {fact_check_error}"
        )

    if fact_check_analysis_used:
        warnings.extend(
            str(item)
            for item in fact_check_result.get(
                "analysis",
                {},
            ).get("warnings", [])
            if str(item).strip()
        )

    warnings = list(dict.fromkeys(warnings))

'''


RETURN_BLOCK = '''        "fact_check_used": fact_check_analysis_used,
        "fact_check": fact_check_result,
'''


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(
            f"Expected one {label} marker, found {count}. "
            "No changes were written."
        )
    return source.replace(old, new, 1)


def insert_before_last(
    source: str,
    marker: str,
    insertion: str,
    label: str,
) -> str:
    position = source.rfind(marker)
    if position < 0:
        raise RuntimeError(
            f"Could not find the {label} marker. No changes were written."
        )
    return source[:position] + insertion + source[position:]


def main() -> None:
    if not TARGET_PATH.exists():
        raise FileNotFoundError(f"File not found: {TARGET_PATH}")

    source = TARGET_PATH.read_text(encoding="utf-8")

    if "fact_check_result = analyze_fact_check_for_fusion" in source:
        print("RC2 fact-check fusion is already integrated.")
        print(f"No changes made: {TARGET_PATH}")
        return

    updated = source

    updated = replace_once(
        updated,
        IMPORT_MARKER,
        IMPORT_REPLACEMENT,
        "identity import",
    )

    updated = insert_before_last(
        updated,
        "    visual_only = (\n",
        FACT_CHECK_BLOCK,
        "visual-only",
    )

    identity_source_marker = '''            + (
                ["identity_impersonation_detector"]
                if identity_impersonation_detected
                else []
            )
'''

    updated = replace_once(
        updated,
        identity_source_marker,
        identity_source_marker + SOURCE_BLOCK,
        "decision-source",
    )

    updated = replace_once(
        updated,
        "    if rag_error:\n",
        WARNING_BLOCK + "    if rag_error:\n",
        "warning",
    )

    updated = replace_once(
        updated,
        '''        "sms_spam_specialist_used": (
''',
        RETURN_BLOCK + '''        "sms_spam_specialist_used": (
''',
        "return-payload",
    )

    if not BACKUP_PATH.exists():
        shutil.copy2(TARGET_PATH, BACKUP_PATH)

    compile(updated, str(TARGET_PATH), "exec")
    TARGET_PATH.write_text(updated, encoding="utf-8")

    print("RC2 fact-check fusion integration completed successfully.")
    print(f"Updated: {TARGET_PATH}")
    print(f"Backup: {BACKUP_PATH}")
    print("The RC2 candidate source files were not modified.")


if __name__ == "__main__":
    main()
