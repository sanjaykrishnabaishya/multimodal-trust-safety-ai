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
    / "hindi-abusive-context-rc3"
)
MANIFEST_PATH = CANDIDATE_DIRECTORY / "manifest.json"
VERDICT_PATH = CANDIDATE_DIRECTORY / "external_evaluation_verdict.json"
REPORT_PATH = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "cyberbullyx63k_hindi_rc3"
    / "aggregate_report.json"
)
SERVICE_PATH = (
    REPO_ROOT
    / "backend"
    / "app"
    / "services"
    / "hindi_abusive_context_service.py"
)
LEXICON_PATH = (
    REPO_ROOT
    / "datasets"
    / "development"
    / "hindi_abusive_rc3"
    / "lexicon.csv"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def percentage(numerator: int, denominator: int) -> float:
    return round((numerator / denominator * 100), 2) if denominator else 0.0


def main() -> None:
    for path in (MANIFEST_PATH, REPORT_PATH, SERVICE_PATH, LEXICON_PATH):
        if not path.is_file():
            raise FileNotFoundError(f"Required file was not found: {path}")

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    report = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    if manifest.get("candidate") != "hindi-abusive-context-rc3":
        raise RuntimeError("Unexpected candidate manifest.")
    if report.get("candidate") != "hindi-abusive-context-rc3":
        raise RuntimeError("The external report does not belong to RC3.")

    frozen_hashes = manifest.get("frozen_input_hashes", {})
    if sha256_file(SERVICE_PATH) != frozen_hashes.get("service"):
        raise RuntimeError("RC3 service changed after freeze; verdict is invalid.")
    if sha256_file(LEXICON_PATH) != frozen_hashes.get("lexicon"):
        raise RuntimeError("RC3 lexicon changed after freeze; verdict is invalid.")

    strict = report["strict_cyberbullying_category_metrics"]
    broad = report["broad_harmful_language_signal_metrics"]
    bc_mc_records = int(report.get("bc_mc_safe_records", 0))
    bc_mc_false_positives = int(
        report.get("bc_mc_safe_false_positives", 0)
    )
    bc_mc_false_positive_rate = percentage(
        bc_mc_false_positives,
        bc_mc_records,
    )

    strict_gate_passed = bool(report.get("readiness_gate", {}).get("passed"))
    broad_gate_passed = bool(
        float(broad.get("accuracy_percent", 0.0)) >= 85.0
        and float(broad.get("f1_percent", 0.0)) >= 85.0
        and float(broad.get("specificity_percent", 0.0)) >= 85.0
    )
    ambiguity_gate_passed = bool(
        bc_mc_records >= 20 and bc_mc_false_positive_rate <= 5.0
    )
    contract_gate_passed = bool(
        int(report.get("automatic_enforcement_contract_failures", 0)) == 0
        and report.get("raw_text_stored") is False
        and report.get("record_level_predictions_stored") is False
        and report.get("used_for_training") is False
    )

    ready = bool(
        strict_gate_passed
        and broad_gate_passed
        and ambiguity_gate_passed
        and contract_gate_passed
    )
    if ready:
        raise RuntimeError(
            "The report unexpectedly passes all gates. Review the verdict script "
            "instead of recording a failure."
        )

    verdict = {
        "candidate": "hindi-abusive-context-rc3",
        "recorded_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "failed_external_readiness_gate",
        "ready_for_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "source_files_modified": False,
        "external_report_sha256": sha256_file(REPORT_PATH),
        "results": {
            "records_evaluated": report.get("records_evaluated"),
            "strict_cyberbullying": strict,
            "broad_harmful_language": broad,
            "bc_mc_safe_records": bc_mc_records,
            "bc_mc_safe_false_positives": bc_mc_false_positives,
            "bc_mc_safe_false_positive_rate_percent": bc_mc_false_positive_rate,
        },
        "gates": {
            "strict_category_gate_passed": strict_gate_passed,
            "broad_harmful_language_gate_passed": broad_gate_passed,
            "bc_mc_ambiguity_gate_passed": ambiguity_gate_passed,
            "privacy_and_policy_contract_gate_passed": contract_gate_passed,
        },
        "interpretation": [
            "The external benchmark uses one binary cyberbullying label, while TrustScopeAI separates Abusive Words from Cyberbullying & Harassment.",
            "The strict result must not be improved by incorrectly merging those product categories.",
            "Broad harmful-language recall and F1 remain below the required readiness target.",
            "BC/MC false positives remain too high for a context-aware ambiguity gate.",
        ],
        "required_next_candidate": "hindi-abusive-context-rc4",
        "rc4_requirements": [
            "Do not train on or inspect the 4,000 RC3 evaluation records.",
            "Use a commercially permitted Hindi/Hinglish sentence source or obtain explicit permission.",
            "Keep Abusive Words and Cyberbullying & Harassment as separate primary categories.",
            "Add a trained Hinglish semantic signal only as supporting evidence until independently validated.",
            "Create a new untouched external test for RC4.",
        ],
    }
    CANDIDATE_DIRECTORY.mkdir(parents=True, exist_ok=True)
    VERDICT_PATH.write_text(
        json.dumps(verdict, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("HINDI/HINGLISH ABUSIVE CONTEXT RC3 EXTERNAL VERDICT")
    print("=" * 60)
    print("Candidate: hindi-abusive-context-rc3")
    print("Status: Failed external readiness gate")
    print(f"Strict category gate passed: {strict_gate_passed}")
    print(f"Broad harmful-language gate passed: {broad_gate_passed}")
    print(f"BC/MC ambiguity gate passed: {ambiguity_gate_passed}")
    print(f"Privacy and policy contract passed: {contract_gate_passed}")
    print(f"BC/MC safe false-positive rate: {bc_mc_false_positive_rate:.2f}%")
    print("Ready for live moderation: False")
    print("Automatic enforcement allowed: False")
    print("RC3 source files modified: False")
    print(f"Verdict: {VERDICT_PATH}")
    print("Next candidate: hindi-abusive-context-rc4")


if __name__ == "__main__":
    main()
