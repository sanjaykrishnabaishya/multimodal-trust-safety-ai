from __future__ import annotations

import py_compile
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
FUSION_PATH = ROOT / "backend" / "app" / "services" / "fusion_service.py"
SERVICE_PATH = ROOT / "backend" / "app" / "services" / "hate_speech_v7_service.py"
TEST_PATH = ROOT / "backend" / "tests" / "test_hate_speech_v7_fusion.py"


def replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise RuntimeError(f"Expected exactly one {label} marker, found {count}.")
    return source.replace(old, new, 1)


def main() -> None:
    if not FUSION_PATH.is_file():
        raise FileNotFoundError(f"Fusion service was not found: {FUSION_PATH}")
    if not SERVICE_PATH.is_file():
        raise FileNotFoundError(f"Hate Speech V7 service was not found: {SERVICE_PATH}")

    source = FUSION_PATH.read_text(encoding="utf-8")
    if "analyze_hate_speech_v7" in source:
        print("Hate Speech V7 guarded fusion is already installed.")
    else:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = FUSION_PATH.with_name(
            f"fusion_service.py.before_hate_speech_v7_{timestamp}"
        )
        backup.write_text(source, encoding="utf-8")

        import_marker = '''from app.services.cyberbullying_rc2_service import (
    analyze_cyberbullying_rc2,
    apply_cyberbullying_rc2_fusion,
)
'''
        source = replace_once(
            source,
            import_marker,
            import_marker
            + '''from app.services.hate_speech_v7_service import (
    analyze_hate_speech_v7,
    apply_hate_speech_v7_fusion,
)
''',
            "import",
        )

        analysis_marker = '''    cyberbullying_rc2_analysis = analyze_cyberbullying_rc2(
        text,
        input_sources,
    )
'''
        source = replace_once(
            source,
            analysis_marker,
            analysis_marker
            + '''    hate_speech_v7_analysis = analyze_hate_speech_v7(
        text,
        input_sources,
    )
''',
            "analysis",
        )

        fusion_marker = '''    cyberbullying_rc2_applied = bool(
        cyberbullying_rc2_fusion["decision_applied"]
    )

    fact_check_result: dict[str, Any]
'''
        fusion_replacement = '''    cyberbullying_rc2_applied = bool(
        cyberbullying_rc2_fusion["decision_applied"]
    )

    hate_speech_v7_fusion = apply_hate_speech_v7_fusion(
        category=category,
        severity=severity,
        action=action,
        confidence=confidence,
        human_review_required=human_review_required,
        reason=reason,
        matched_signals=matched_signals,
        analysis=hate_speech_v7_analysis,
        safe_context_confirmed=(
            safe_context_detected
            and not direct_action_detected
        ),
    )
    category = str(hate_speech_v7_fusion["category"])
    severity = str(hate_speech_v7_fusion["severity"])
    action = str(hate_speech_v7_fusion["action"])
    confidence = float(hate_speech_v7_fusion["confidence"])
    human_review_required = bool(
        hate_speech_v7_fusion["human_review_required"]
    )
    reason = str(hate_speech_v7_fusion["reason"])
    matched_signals = list(hate_speech_v7_fusion["matched_signals"])
    hate_speech_v7_applied = bool(
        hate_speech_v7_fusion["decision_applied"]
    )

    fact_check_result: dict[str, Any]
'''
        source = replace_once(source, fusion_marker, fusion_replacement, "fusion")

        source_marker = '''            + (
                ["cyberbullying_abusive_rc2"]
                if cyberbullying_rc2_applied
                else []
            )
'''
        source = replace_once(
            source,
            source_marker,
            source_marker
            + '''            + (
                ["hate_speech_v7_rc1"]
                if hate_speech_v7_applied
                else []
            )
''',
            "decision source",
        )

        return_marker = '''        "cyberbullying_rc2_used": cyberbullying_rc2_applied,
        "cyberbullying_rc2": cyberbullying_rc2_analysis,
'''
        source = replace_once(
            source,
            return_marker,
            '''        "hate_speech_v7_used": hate_speech_v7_applied,
        "hate_speech_v7": hate_speech_v7_analysis,
        "hate_speech_v7_fusion_status": (
            hate_speech_v7_fusion["fusion_status"]
        ),
''' + return_marker,
            "response metadata",
        )

        FUSION_PATH.write_text(source, encoding="utf-8")
        print("Hate Speech V7 guarded fusion installed.")
        print(f"Updated: {FUSION_PATH}")
        print(f"Backup: {backup}")

    test_source = '''from app.services.hate_speech_v7_service import apply_hate_speech_v7_fusion


def baseline(category="Normal/Ignore"):
    return {
        "category": category,
        "severity": "None",
        "action": "Allow",
        "confidence": 0.70,
        "human_review_required": False,
        "reason": "Baseline decision.",
        "matched_signals": [],
    }


def accepted(*, protected=True):
    return {
        "available": True,
        "decision": "accepted_review_only",
        "primary_category": "Hate Speech & Discrimination",
        "model_score": 0.91,
        "protected_reference_detected": protected,
        "reporting_or_counterspeech_detected": False,
        "reason": "Validated Hate Speech evidence requires review.",
        "automatic_enforcement_allowed": False,
    }


def apply(category="Normal/Ignore", analysis=None, safe=False):
    return apply_hate_speech_v7_fusion(
        **baseline(category),
        analysis=analysis or accepted(),
        safe_context_confirmed=safe,
    )


def test_normal_can_become_review_only_hate_speech():
    result = apply()
    assert result["category"] == "Hate Speech & Discrimination"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["decision_applied"] is True


def test_abusive_words_need_explicit_protected_reference():
    result = apply("Abusive Words", accepted(protected=False))
    assert result["category"] == "Abusive Words"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "abusive_words_retained_without_protected_target"


def test_protected_group_hate_can_refine_abusive_words():
    result = apply("Abusive Words", accepted(protected=True))
    assert result["category"] == "Hate Speech & Discrimination"
    assert result["human_review_required"] is True


def test_cyberbullying_cannot_be_overridden():
    result = apply("Cyberbullying & Harassment")
    assert result["category"] == "Cyberbullying & Harassment"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_category_isolation"


def test_unrelated_categories_cannot_be_overridden():
    for category in (
        "Violent Content",
        "Spam, Scam & Phishing",
        "Publishing Private Information",
        "Misinformation & Fake News",
        "Religiously Offensive Content",
    ):
        result = apply(category)
        assert result["category"] == category
        assert result["decision_applied"] is False


def test_safe_context_blocks_hate_override():
    result = apply(safe=True)
    assert result["category"] == "Normal/Ignore"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_safe_context"


def test_below_threshold_never_creates_allow_or_hate_override():
    analysis = accepted()
    analysis["decision"] = "below_selective_threshold_no_override"
    result = apply(analysis=analysis)
    assert result["category"] == "Normal/Ignore"
    assert result["decision_applied"] is False
'''
    TEST_PATH.write_text(test_source, encoding="utf-8")

    py_compile.compile(str(SERVICE_PATH), doraise=True)
    py_compile.compile(str(FUSION_PATH), doraise=True)
    py_compile.compile(str(TEST_PATH), doraise=True)
    print(f"Tests written: {TEST_PATH}")
    print("Automatic enforcement allowed: False")
    print("Only Hate Speech may be added; other category ownership is preserved.")


if __name__ == "__main__":
    main()
