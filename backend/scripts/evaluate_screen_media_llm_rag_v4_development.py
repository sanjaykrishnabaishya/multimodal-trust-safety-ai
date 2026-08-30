from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.graphic_sexual_content_v2_service import (
    HARASSMENT_ACTION,
    SEXUAL_ACTION,
    SEXUAL_CATEGORY,
    SEXUAL_HARASSMENT_CATEGORY,
)
from app.services.screen_media_llm_rag_v4_service import (
    LLM_SCHEMA_VERSION,
    MEDIA_REVIEW_ACTION,
    UNCERTAIN_CATEGORY,
    analyze_screen_media_llm_rag_v4,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "screen_media_llm_rag_v4_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.csv"


CATALOG = [
    {
        "qid": "Q1001",
        "title": "Titanic",
        "aliases": ["Titanic film"],
        "work_type": "film",
        "release_year": 1997,
        "source": "wikidata",
        "license": "CC0-1.0",
    },
    {
        "qid": "Q1002",
        "title": "Outlander",
        "aliases": ["Outlander series"],
        "work_type": "television_series",
        "release_year": 2014,
        "source": "wikidata",
        "license": "CC0-1.0",
    },
    {
        "qid": "Q1003",
        "title": "Journey Alpha",
        "aliases": ["The Journey"],
        "work_type": "film",
        "release_year": 2001,
        "source": "wikidata",
        "license": "CC0-1.0",
    },
    {
        "qid": "Q1004",
        "title": "Journey Beta",
        "aliases": ["The Journey"],
        "work_type": "film",
        "release_year": 2010,
        "source": "wikidata",
        "license": "CC0-1.0",
    },
]


def publisher(qid: str, work_type: str, *, trusted: bool = True) -> dict[str, Any]:
    return {
        "source_type": (
            "signed_publisher_metadata" if trusted else "uploader_metadata"
        ),
        "qid": qid,
        "work_type": work_type,
        "signature_verified": trusted,
    }


def llm(
    *,
    sexual_signal: str,
    obscuration: str = "uncertain",
    candidate_qid: str = "",
    confidence: float = 0.9,
    evidence_ids: list[str] | None = None,
    abstained: bool = False,
) -> dict[str, Any]:
    return {
        "schema_version": LLM_SCHEMA_VERSION,
        "abstained": abstained,
        "sexual_signal": sexual_signal,
        "obscuration": obscuration,
        "candidate_qid": candidate_qid,
        "confidence": confidence,
        "evidence_ids": evidence_ids or ["caption-1"],
    }


def visual(
    explicitness: str,
    *,
    independently_validated: bool = False,
    no_explicit_detail_visible: bool = False,
) -> dict[str, Any]:
    return {
        "explicitness": explicitness,
        "independently_validated_blur_detector": independently_validated,
        "no_explicit_detail_visible": no_explicit_detail_visible,
        "sample_coverage": 0.95 if independently_validated else 0.50,
        "sensitive_region_coverage": 0.98 if independently_validated else 0.0,
        "visible_explicit_regions": 0 if no_explicit_detail_visible else 1,
    }


def add_cases(
    rows: list[dict[str, Any]],
    group: str,
    expected: str,
    factory: Any,
) -> None:
    for index in range(16):
        row = factory(index)
        rows.append(
            {
                "case_id": f"{group.upper().replace('_', '-')}-{index + 1:03d}",
                "group": group,
                "expected": expected,
                "content_type": "video" if index % 2 == 0 else "image",
                "existing_category": "Normal/Ignore",
                "text": "",
                "evidence": {},
                "publisher": None,
                "visual": {},
                "llm": {},
                **row,
            }
        )


def build_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    add_cases(
        rows,
        "verified_film_explicit_review",
        "media_review",
        lambda _: {
            "text": "The visual evidence indicates explicit adult content.",
            "evidence": {"caption": "A verified scene from Titanic."},
            "publisher": publisher("Q1001", "film"),
            "visual": visual("explicit"),
            "llm": llm(sexual_signal="explicit", candidate_qid="Q1001"),
        },
    )
    add_cases(
        rows,
        "verified_series_uncertain_review",
        "media_review",
        lambda _: {
            "text": "The scene requires contextual assessment.",
            "evidence": {"caption": "A scene from Outlander series."},
            "publisher": publisher("Q1002", "television_series"),
            "visual": visual("uncertain"),
            "llm": llm(
                sexual_signal="possibly_explicit", candidate_qid="Q1002"
            ),
        },
    )
    add_cases(
        rows,
        "validated_full_blur_no_override",
        "no_override",
        lambda _: {
            "text": "The source scene concerns explicit adult content.",
            "evidence": {"ocr": "Titanic film"},
            "publisher": publisher("Q1001", "film"),
            "visual": visual(
                "obscured",
                independently_validated=True,
                no_explicit_detail_visible=True,
            ),
            "llm": llm(
                sexual_signal="possibly_explicit",
                obscuration="fully_obscured",
                candidate_qid="Q1001",
                evidence_ids=["ocr-1"],
            ),
        },
    )
    add_cases(
        rows,
        "self_reported_blur_still_reviews",
        "media_review",
        lambda _: {
            "text": "The uploader says explicit adult content was blurred.",
            "evidence": {"caption": "A blurred Outlander scene."},
            "publisher": publisher("Q1002", "television_series"),
            "visual": visual("explicit", independently_validated=False),
            "llm": llm(
                sexual_signal="possibly_explicit",
                obscuration="fully_obscured",
                candidate_qid="Q1002",
            ),
        },
    )
    add_cases(
        rows,
        "famous_title_spoof_falls_back",
        "standard_graphic",
        lambda _: {
            "text": "The upload presents explicit adult content.",
            "evidence": {"caption": "The uploader calls this a Titanic scene."},
            "publisher": publisher("Q1001", "film", trusted=False),
            "visual": visual("explicit"),
            "llm": llm(sexual_signal="explicit", candidate_qid="Q1001"),
        },
    )
    add_cases(
        rows,
        "hallucinated_title_is_rejected",
        "standard_graphic",
        lambda index: {
            "text": "The upload presents explicit adult content.",
            "evidence": {"caption": f"Claimed production number {index + 1}."},
            "publisher": None,
            "visual": visual("explicit"),
            "llm": llm(sexual_signal="explicit", candidate_qid="Q999999"),
        },
    )
    add_cases(
        rows,
        "ambiguous_title_is_not_verified",
        "standard_graphic",
        lambda _: {
            "text": "The upload presents explicit adult content.",
            "evidence": {"caption": "A clip labelled The Journey."},
            "publisher": None,
            "visual": visual("explicit"),
            "llm": llm(sexual_signal="explicit", candidate_qid="Q1003"),
        },
    )
    add_cases(
        rows,
        "llm_only_concern_can_only_escalate",
        "uncertain_review",
        lambda _: {
            "text": "The extracted text does not establish a category.",
            "evidence": {"caption": "An unclear visual scene."},
            "publisher": None,
            "visual": visual("none"),
            "llm": llm(sexual_signal="possibly_explicit", confidence=0.91),
        },
    )
    add_cases(
        rows,
        "llm_cannot_create_allow",
        "media_review",
        lambda _: {
            "text": "The visual evidence indicates explicit adult content.",
            "evidence": {"caption": "A scene from Titanic."},
            "publisher": publisher("Q1001", "film"),
            "visual": visual("explicit"),
            "llm": llm(
                sexual_signal="none",
                obscuration="fully_obscured",
                candidate_qid="Q1001",
            ),
        },
    )
    add_cases(
        rows,
        "sexual_harassment_owner_precedence",
        "sexual_harassment",
        lambda _: {
            "text": "A coworker repeatedly sends unwanted explicit messages to a named recipient.",
            "evidence": {"caption": "A scene from Outlander."},
            "publisher": publisher("Q1002", "television_series"),
            "visual": visual("explicit"),
            "llm": llm(sexual_signal="explicit", candidate_qid="Q1002"),
        },
    )
    owners = [
        "Child Exploitation",
        "Cyberbullying & Harassment",
        "Violent Content",
        "Publishing Private Information",
    ]
    add_cases(
        rows,
        "established_category_owner_isolation",
        "owner_preserved",
        lambda index: {
            "existing_category": owners[index % len(owners)],
            "text": "Another established category already owns this decision.",
            "evidence": {"caption": "A scene from Titanic."},
            "publisher": publisher("Q1001", "film"),
            "visual": visual("explicit"),
            "llm": llm(sexual_signal="explicit", candidate_qid="Q1001"),
        },
    )
    return rows


def predicted_contract(result: dict[str, Any]) -> str:
    if result.get("v4_status") == "blocked_by_higher_priority_owner":
        return "owner_preserved"
    if result.get("category") == SEXUAL_HARASSMENT_CATEGORY:
        return "sexual_harassment"
    if result.get("status") == "verified_screen_work_review_candidate":
        return "media_review"
    if result.get("category") == UNCERTAIN_CATEGORY:
        return "uncertain_review"
    if result.get("category") == SEXUAL_CATEGORY and result.get("action") == SEXUAL_ACTION:
        return "standard_graphic"
    return "no_override"


def main() -> None:
    rows = build_cases()
    if len(rows) != 176:
        raise RuntimeError(f"Expected 176 development records; found {len(rows)}")

    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    action_failures = 0
    category_mix_failures = 0
    provenance_failures = 0
    hallucination_failures = 0
    llm_authority_failures = 0
    blur_contract_failures = 0
    results: list[dict[str, Any]] = []

    for row in rows:
        result = analyze_screen_media_llm_rag_v4(
            row["text"],
            content_type=row["content_type"],
            existing_category=row["existing_category"],
            extracted_evidence=row["evidence"],
            catalog_records=CATALOG,
            publisher_metadata=row["publisher"],
            visual_evidence=row["visual"],
            llm_analysis=row["llm"],
            run_local_llm=False,
        )
        predicted = predicted_contract(result)
        correct = predicted == row["expected"]
        group_totals[row["group"]] += 1
        group_correct[row["group"]] += int(correct)

        action_failure = bool(
            (predicted in {"media_review", "uncertain_review"} and (
                result.get("action") != MEDIA_REVIEW_ACTION
                or result.get("human_review_required") is not True
                or result.get("automatic_enforcement_allowed") is not False
            ))
            or (predicted == "sexual_harassment" and (
                result.get("action") != HARASSMENT_ACTION
                or result.get("human_review_required") is not True
            ))
        )
        mix_failure = bool(
            row["group"] == "established_category_owner_isolation"
            and predicted != "owner_preserved"
        )
        provenance_failure = bool(
            row["group"] in {
                "famous_title_spoof_falls_back",
                "hallucinated_title_is_rejected",
                "ambiguous_title_is_not_verified",
            }
            and result.get("screen_work_verified") is True
        )
        hallucination_failure = bool(
            row["group"] == "hallucinated_title_is_rejected"
            and result.get("llm_analysis", {}).get("valid") is True
        )
        llm_failure = bool(
            (row["group"] == "llm_only_concern_can_only_escalate" and predicted != "uncertain_review")
            or (row["group"] == "llm_cannot_create_allow" and predicted != "media_review")
        )
        blur_failure = bool(
            (row["group"] == "validated_full_blur_no_override" and predicted != "no_override")
            or (row["group"] == "self_reported_blur_still_reviews" and predicted != "media_review")
        )
        action_failures += int(action_failure)
        category_mix_failures += int(mix_failure)
        provenance_failures += int(provenance_failure)
        hallucination_failures += int(hallucination_failure)
        llm_authority_failures += int(llm_failure)
        blur_contract_failures += int(blur_failure)
        results.append(
            {
                "case_id": row["case_id"],
                "group": row["group"],
                "expected": row["expected"],
                "predicted": predicted,
                "status": result.get("status"),
                "v4_status": result.get("v4_status"),
                "screen_work_verified": result.get("screen_work_verified"),
                "llm_used": result.get("llm_used"),
                "rag_used": result.get("rag_used"),
                "correct": correct,
                "action_failure": action_failure,
                "category_mix_failure": mix_failure,
                "provenance_failure": provenance_failure,
                "hallucination_failure": hallucination_failure,
                "llm_authority_failure": llm_failure,
                "blur_contract_failure": blur_failure,
            }
        )

    records = len(rows)
    accuracy = sum(int(item["correct"]) for item in results) / records
    group_results = {
        group: {
            "correct": group_correct[group],
            "records": total,
            "accuracy": group_correct[group] / total,
        }
        for group, total in sorted(group_totals.items())
    }
    minimum_group_accuracy = min(item["accuracy"] for item in group_results.values())
    passed = bool(
        accuracy >= 0.95
        and minimum_group_accuracy >= 0.90
        and action_failures == 0
        and category_mix_failures == 0
        and provenance_failures == 0
        and hallucination_failures == 0
        and llm_authority_failures == 0
        and blur_contract_failures == 0
    )
    report = {
        "component": "Screen-media LLM/RAG V4 evidence contract",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "accuracy": accuracy,
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": group_results,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "provenance_contract_failures": provenance_failures,
        "hallucination_contract_failures": hallucination_failures,
        "llm_authority_contract_failures": llm_authority_failures,
        "blur_contract_failures": blur_contract_failures,
        "passed_development_gate": passed,
        "local_llm_executed": False,
        "local_llm_model_downloaded": False,
        "rag_catalog": "synthetic CC0-shaped contract fixtures only",
        "rc1_holdout_cases_or_predictions_used": False,
        "frozen_rc1_modified": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
    }
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    fields = [
        "case_id",
        "group",
        "expected",
        "predicted",
        "status",
        "v4_status",
        "screen_work_verified",
        "llm_used",
        "rag_used",
        "action_failure",
        "category_mix_failure",
        "provenance_failure",
        "hallucination_failure",
        "llm_authority_failure",
        "blur_contract_failure",
    ]
    with MISMATCH_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in results:
            if not item["correct"] or any(
                item[key]
                for key in fields
                if key.endswith("failure")
            ):
                writer.writerow({field: item.get(field) for field in fields})

    print("SCREEN-MEDIA LLM/RAG V4 DEVELOPMENT CONTRACT")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Provenance-contract failures: {provenance_failures}")
    print(f"Hallucination-contract failures: {hallucination_failures}")
    print(f"LLM-authority failures: {llm_authority_failures}")
    print(f"Blur-contract failures: {blur_contract_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, item in group_results.items():
        print(f"{group}: {item['correct']}/{item['records']} ({item['accuracy'] * 100:.2f}%)")
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Local LLM executed or downloaded: False")
    print("RAG catalog: synthetic CC0-shaped fixtures only")
    print("Frozen RC1 modified: False")
    print("RC1 holdout cases or predictions used: False")
    print("Automatic enforcement allowed: False")
    print("The LLM/RAG evidence layer is not connected to live moderation.")


if __name__ == "__main__":
    main()
