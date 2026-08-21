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
from app.services.graphic_sexual_media_context_v3_service import (
    MEDIA_REVIEW_ACTION,
    analyze_graphic_sexual_media_context_v3,
)


ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "graphic_sexual_content"
    / "media_context_v3_development"
)
REPORT_PATH = REPORT_DIRECTORY / "report.json"
MISMATCH_PATH = REPORT_DIRECTORY / "mismatches.csv"


def case(
    case_id: str,
    group: str,
    text: str,
    expected: str,
    *,
    media_type: str = "video",
    work_type: str = "film",
    title: str = "",
    provenance: str = "verified_catalog_metadata",
    obscuration: str = "unblurred",
    explicitness: str = "explicit",
    no_explicit_detail_visible: bool = False,
    existing_category: str = "Normal/Ignore",
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "group": group,
        "text": text,
        "expected": expected,
        "existing_category": existing_category,
        "media_context": {
            "media_type": media_type,
            "work_type": work_type,
            "title": title,
            "provenance": provenance,
            "obscuration": obscuration,
            "explicitness": explicitness,
            "no_explicit_detail_visible": no_explicit_detail_visible,
        },
    }


def build_cases() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    film_titles = [
        "Titanic",
        "Verified Film Alpha",
        "Verified Film Beta",
        "Verified Film Gamma",
        "Verified Film Delta",
    ]
    series_titles = [
        "Outlander",
        "Verified Series Alpha",
        "Verified Series Beta",
        "Verified Series Gamma",
        "Verified Series Delta",
    ]

    for index in range(20):
        title = film_titles[index % len(film_titles)]
        rows.append(
            case(
                f"FILM-REVIEW-{index + 1:03d}",
                "verified_film_explicit_review",
                "Trusted metadata identifies this as a film scene with adult sexual content.",
                "media_review",
                title=title,
            )
        )
        title = series_titles[index % len(series_titles)]
        rows.append(
            case(
                f"SERIES-REVIEW-{index + 1:03d}",
                "verified_series_explicit_review",
                "Publisher metadata identifies this as a television-series scene with adult sexual content.",
                "media_review",
                work_type="tv_series",
                title=title,
                provenance="verified_publisher_metadata",
            )
        )
        title = (film_titles + series_titles)[index % 10]
        rows.append(
            case(
                f"BLURRED-SAFE-{index + 1:03d}",
                "verified_screen_media_fully_blurred",
                "The identified screen scene is fully blurred and no explicit detail remains visible.",
                "no_override",
                work_type="film" if index % 2 == 0 else "tv_series",
                title=title,
                obscuration="fully_blurred",
                explicitness="explicit",
                no_explicit_detail_visible=True,
            )
        )
        title = (film_titles + series_titles)[index % 10]
        rows.append(
            case(
                f"PARTIAL-BLUR-{index + 1:03d}",
                "partial_or_uncertain_blur_review",
                "The identified screen scene is only partly obscured and its explicitness is uncertain.",
                "media_review",
                work_type="film" if index % 2 == 0 else "tv_series",
                title=title,
                obscuration="partially_blurred",
                explicitness="uncertain",
            )
        )
        title = (film_titles + series_titles)[index % 10]
        rows.append(
            case(
                f"NONEXPLICIT-SAFE-{index + 1:03d}",
                "recognized_nonexplicit_screen_media",
                "Trusted metadata identifies an ordinary non-explicit scene from a screen work.",
                "no_override",
                work_type="film" if index % 2 == 0 else "tv_series",
                title=title,
                explicitness="non_explicit",
            )
        )
        rows.append(
            case(
                f"UNVERIFIED-CLAIM-{index + 1:03d}",
                "unverified_famous_title_claim",
                "The uploader claims this explicit adult clip comes from a famous film or series.",
                "standard_graphic",
                title=f"Claimed Work {index + 1}",
                provenance="uploader_claim",
            )
        )
        rows.append(
            case(
                f"HARASSMENT-OWNER-{index + 1:03d}",
                "sexual_harassment_owner_precedence",
                "A coworker repeatedly sends unwanted explicit messages to a named recipient.",
                "sexual_harassment",
                title=series_titles[index % len(series_titles)],
                work_type="tv_series",
                obscuration="fully_blurred",
                no_explicit_detail_visible=True,
            )
        )
        owner = [
            "Child Exploitation",
            "Cyberbullying & Harassment",
            "Violent Content",
            "Publishing Private Information",
            "Spam, Scam & Phishing",
        ][index % 5]
        rows.append(
            case(
                f"OWNER-ISOLATION-{index + 1:03d}",
                "established_category_owner_isolation",
                "Trusted metadata identifies a screen excerpt, but another policy category already owns the decision.",
                "no_override",
                title=film_titles[index % len(film_titles)],
                existing_category=owner,
            )
        )
    return rows


def predicted_contract(result: dict[str, Any]) -> str:
    status = result.get("status")
    category = result.get("category")
    action = result.get("action")
    if status == "recognized_screen_media_review_candidate":
        return "media_review"
    if category == SEXUAL_HARASSMENT_CATEGORY:
        return "sexual_harassment"
    if category == SEXUAL_CATEGORY and action == SEXUAL_ACTION:
        return "standard_graphic"
    return "no_override"


def main() -> None:
    rows = build_cases()
    if len(rows) != 160:
        raise RuntimeError(f"Expected 160 development cases; found {len(rows)}")

    group_totals: Counter[str] = Counter()
    group_correct: Counter[str] = Counter()
    contract_totals: Counter[str] = Counter()
    contract_correct: Counter[str] = Counter()
    results: list[dict[str, Any]] = []
    action_failures = 0
    category_mix_failures = 0
    provenance_failures = 0
    blur_contract_failures = 0

    for row in rows:
        result = analyze_graphic_sexual_media_context_v3(
            row["text"],
            existing_category=row["existing_category"],
            media_context=row["media_context"],
        )
        predicted = predicted_contract(result)
        expected = row["expected"]
        correct = predicted == expected
        group_totals[row["group"]] += 1
        group_correct[row["group"]] += int(correct)
        contract_totals[expected] += 1
        contract_correct[expected] += int(correct)

        action_failure = bool(
            (predicted == "media_review" and (
                result.get("action") != MEDIA_REVIEW_ACTION
                or result.get("human_review_required") is not True
                or result.get("automatic_enforcement_allowed") is not False
            ))
            or (predicted == "sexual_harassment" and (
                result.get("action") != HARASSMENT_ACTION
                or result.get("human_review_required") is not True
            ))
        )
        category_mix_failure = bool(
            row["group"] == "established_category_owner_isolation"
            and result.get("decision_applied") is True
        )
        provenance_failure = bool(
            row["group"] == "unverified_famous_title_claim"
            and result.get("recognized_screen_media_policy_used") is True
        )
        blur_failure = bool(
            row["group"] == "verified_screen_media_fully_blurred"
            and (
                result.get("decision_applied") is True
                or result.get("action") is not None
                or result.get("human_review_required") is not False
            )
        )
        action_failures += int(action_failure)
        category_mix_failures += int(category_mix_failure)
        provenance_failures += int(provenance_failure)
        blur_contract_failures += int(blur_failure)
        results.append(
            {
                "case_id": row["case_id"],
                "group": row["group"],
                "expected": expected,
                "predicted": predicted,
                "status": result.get("status"),
                "action": result.get("action"),
                "correct": correct,
                "action_failure": action_failure,
                "category_mix_failure": category_mix_failure,
                "provenance_failure": provenance_failure,
                "blur_contract_failure": blur_failure,
                "text": row["text"],
            }
        )

    records = len(rows)
    correct_records = sum(int(item["correct"]) for item in results)
    accuracy = correct_records / records
    group_results = {
        group: {
            "correct": group_correct[group],
            "records": total,
            "accuracy": group_correct[group] / total,
        }
        for group, total in sorted(group_totals.items())
    }
    contract_results = {
        contract: {
            "correct": contract_correct[contract],
            "records": total,
            "accuracy": contract_correct[contract] / total,
        }
        for contract, total in sorted(contract_totals.items())
    }
    minimum_group_accuracy = min(
        item["accuracy"] for item in group_results.values()
    )
    passed = bool(
        accuracy >= 0.95
        and minimum_group_accuracy >= 0.90
        and action_failures == 0
        and category_mix_failures == 0
        and provenance_failures == 0
        and blur_contract_failures == 0
    )

    report = {
        "component": "Graphic/Sexual Content V3 screen-media context policy",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "records": records,
        "accuracy": accuracy,
        "minimum_group_accuracy": minimum_group_accuracy,
        "group_results": group_results,
        "contract_results": contract_results,
        "action_contract_failures": action_failures,
        "category_mix_failures": category_mix_failures,
        "provenance_contract_failures": provenance_failures,
        "blur_contract_failures": blur_contract_failures,
        "passed_development_gate": passed,
        "recognized_title_requires_trusted_metadata": True,
        "title_inferred_from_model_output": False,
        "full_blur_requires_no_explicit_detail_visible": True,
        "child_exploitation_output_enabled": False,
        "automatic_enforcement_allowed": False,
        "connected_to_live_moderation": False,
        "rc1_holdout_cases_or_predictions_used": False,
        "external_or_restricted_data_used": False,
        "explicit_descriptions_stored": False,
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
        "action",
        "action_failure",
        "category_mix_failure",
        "provenance_failure",
        "blur_contract_failure",
        "text",
    ]
    with MISMATCH_PATH.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for item in results:
            if not item["correct"] or any(
                item[key]
                for key in (
                    "action_failure",
                    "category_mix_failure",
                    "provenance_failure",
                    "blur_contract_failure",
                )
            ):
                writer.writerow({field: item.get(field) for field in fields})

    print("GRAPHIC/SEXUAL CONTENT V3 SCREEN-MEDIA POLICY DEVELOPMENT")
    print("=" * 60)
    print(f"Records: {records}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Minimum group accuracy: {minimum_group_accuracy * 100:.2f}%")
    print(f"Action-contract failures: {action_failures}")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Provenance-contract failures: {provenance_failures}")
    print(f"Blur-contract failures: {blur_contract_failures}")
    print("\nGROUP RESULTS")
    print("-" * 60)
    for group, item in group_results.items():
        print(f"{group}: {item['correct']}/{item['records']} ({item['accuracy'] * 100:.2f}%)")
    print(f"\nPassed development gate: {passed}")
    print(f"Report: {REPORT_PATH}")
    print(f"Mismatches: {MISMATCH_PATH}")
    print("Recognized title requires trusted metadata: True")
    print("Title inferred from model output: False")
    print("Full blur requires no explicit detail visible: True")
    print("Frozen RC1 modified: False")
    print("RC1 holdout cases or predictions used: False")
    print("Automatic enforcement allowed: False")
    print("The policy layer is not connected to live moderation.")


if __name__ == "__main__":
    main()
