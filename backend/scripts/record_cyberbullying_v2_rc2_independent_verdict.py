from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CANDIDATE_DIRECTORY = (
    REPO_ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "cyberbullying-v2-rc2"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "independent_evaluation_verdict.json"
REPORT_PATH = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "v2_rc2_independent_test"
    / "aggregate_report.json"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_frozen_candidate(manifest: dict) -> None:
    frozen_hashes = manifest.get("frozen_file_hashes", {})
    if not frozen_hashes:
        raise RuntimeError("The manifest does not contain frozen file hashes.")

    for relative_path, expected_hash in frozen_hashes.items():
        candidate_path = CANDIDATE_DIRECTORY / relative_path
        if not candidate_path.is_file():
            raise FileNotFoundError(
                f"Frozen candidate file was not found: {candidate_path}"
            )
        actual_hash = sha256_file(candidate_path)
        if actual_hash != expected_hash:
            raise RuntimeError(
                "Frozen RC2 changed after freeze: "
                f"{relative_path}\nExpected: {expected_hash}\nActual: {actual_hash}"
            )


def main() -> None:
    for path in (MANIFEST_PATH, REPORT_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required file was not found: {path}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    expected_candidate = "cyberbullying-v2-rc2"
    if manifest.get("candidate") != expected_candidate:
        raise RuntimeError("Unexpected candidate manifest.")
    if report.get("candidate") != expected_candidate:
        raise RuntimeError("The independent report does not belong to RC2.")

    verify_frozen_candidate(manifest)

    report_test_hash = report.get("test_split_sha256")
    manifest_test_hash = manifest.get("dataset_hashes", {}).get("test.csv")
    if report_test_hash != manifest_test_hash:
        raise RuntimeError(
            "The independently evaluated test split does not match the frozen manifest."
        )

    passed = bool(report.get("passed_independent_readiness_gate"))
    if not passed:
        raise RuntimeError(
            "The independent readiness gate did not pass. Refusing to record a "
            "passing verdict."
        )

    if report.get("frozen_candidate_modified") is not False:
        raise RuntimeError("The evaluation did not preserve the frozen candidate.")
    if report.get("raw_text_stored_in_report") is not False:
        raise RuntimeError("The independent report stored raw test text.")
    if report.get("record_level_predictions_stored") is not False:
        raise RuntimeError("The independent report stored record-level predictions.")

    selective_results = report.get("per_label_selective_results", {})
    required_labels = {"targeted_threat", "abusive_words", "safe_or_other"}
    if set(selective_results) != required_labels:
        raise RuntimeError("The independent report has unexpected label results.")

    minimum_precision = float(report.get("minimum_selective_precision", 0.85))
    for label, metrics in selective_results.items():
        if float(metrics.get("accepted_precision", 0.0)) < minimum_precision:
            raise RuntimeError(
                f"{label} does not satisfy the accepted-precision gate."
            )

    verdict = {
        "candidate": expected_candidate,
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "passed_independent_readiness_gate",
        "independently_validated_for_controlled_integration": True,
        "ready_for_controlled_live_integration": True,
        "automatic_enforcement_allowed": False,
        "currently_connected_to_live_moderation": False,
        "frozen_classifier_and_source_modified": False,
        "independent_report_sha256": sha256_file(REPORT_PATH),
        "test_split_sha256": report_test_hash,
        "metrics": {
            "records": report.get("records"),
            "raw_accuracy": report.get("raw_accuracy"),
            "raw_macro_f1": report.get("raw_macro_f1"),
            "selective_accuracy": report.get("selective_accuracy"),
            "coverage": report.get("coverage"),
            "accepted_records": report.get("accepted_records"),
            "uncertain_records": report.get("uncertain_records"),
            "per_label_selective_results": selective_results,
        },
        "policy_contract": {
            "one_primary_category_only": True,
            "targeted_threat_category": "Cyberbullying & Harassment",
            "single_abusive_language_category": "Abusive Words",
            "safe_or_other_behavior": "No boundary override",
            "uncertain_behavior": "Refer to human review",
            "may_automatically_enforce": False,
            "may_override_unrelated_specialists": False,
        },
        "limitations": report.get("limitations", []),
        "next_step": (
            "Integrate RC2 behind category-isolation and human-review gates, "
            "then run live-fusion contract tests before enabling it."
        ),
    }

    VERDICT_PATH.write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("CYBERBULLYING/ABUSIVE WORDS V2 RC2 INDEPENDENT VERDICT")
    print("=" * 60)
    print("Candidate: cyberbullying-v2-rc2")
    print("Status: Passed independent readiness gate")
    print(
        "Selective accuracy: "
        f"{float(report['selective_accuracy']) * 100:.2f}%"
    )
    print(f"Coverage: {float(report['coverage']) * 100:.2f}%")
    print("Eligible for controlled live integration: True")
    print("Automatic enforcement allowed: False")
    print("Currently connected to live moderation: False")
    print("Frozen classifier and source modified: False")
    print(f"Verdict: {VERDICT_PATH}")
    print("Next: guarded fusion integration and category-isolation tests")


if __name__ == "__main__":
    main()
