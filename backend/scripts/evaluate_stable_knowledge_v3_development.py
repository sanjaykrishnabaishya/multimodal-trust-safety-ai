from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.fact_check_decision_service import analyze_fact_check


SCRIPT_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SCRIPT_DIRECTORY.parent
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent
DATASET_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "development"
    / "stable_knowledge_v3"
    / "development.csv"
)
MANIFEST_PATH = DATASET_PATH.parent / "manifest.json"
REPORT_ROOT = (
    PROJECT_DIRECTORY
    / "reports"
    / "evaluation"
    / "stable_knowledge_v3_development"
)

EXPECTED_VERSION = "2026.08-v3-development"
CONCLUSIVE_STATUSES = {"SUPPORTS", "REFUTES"}
VALID_EXPECTED_STATUSES = {"SUPPORTS", "REFUTES", "NOT_ROUTED"}
CHECKPOINT_RETRY_ATTEMPTS = 12
CHECKPOINT_RETRY_DELAY_SECONDS = 0.5
MAXIMUM_RECORD_ATTEMPTS = 3
RECORD_RETRY_DELAYS_SECONDS = (4.0, 12.0)
TRANSIENT_RETRIEVAL_MARKERS = (
    "nameresolutionerror",
    "getaddrinfo failed",
    "temporary failure in name resolution",
    "connectionerror",
    "connecttimeout",
    "readtimeout",
    "remote disconnected",
    "max retries exceeded",
    "too many requests",
    "429 client error",
    "service unavailable",
    "502 server error",
    "503 server error",
    "504 server error",
)


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Stable Knowledge V3 on the development-only dataset. "
            "This must never be reported as independent accuracy."
        )
    )
    parser.add_argument(
        "--sample-per-status",
        type=int,
        default=0,
        help=(
            "Select up to this many records for every relation/status pair. "
            "Use 1 for a balanced smoke run; 0 evaluates the full dataset."
        ),
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Optional maximum after balanced selection; 0 means no limit.",
    )
    parser.add_argument(
        "--run-name",
        default="full",
        help="Separate name for checkpoints and reports.",
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Discard only this run's checkpoint before evaluation.",
    )
    return parser.parse_args()


def safe_run_name(value: str) -> str:
    cleaned = "".join(
        character
        if character.isalnum() or character in {"-", "_"}
        else "_"
        for character in str(value or "full")
    ).strip("_")
    return cleaned or "full"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise FileNotFoundError(
            f"Development manifest was not found: {MANIFEST_PATH}"
        )

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8-sig"))
    if manifest.get("version") != EXPECTED_VERSION:
        raise ValueError(
            "Unexpected development dataset version: "
            f"{manifest.get('version')!r}"
        )
    if manifest.get("eligible_for_holdout") is not False:
        raise ValueError("The manifest must explicitly forbid holdout use.")
    if manifest.get("uses_v2_holdout_records") is not False:
        raise ValueError("The development manifest violates holdout separation.")
    if manifest.get("uses_v2_mismatch_report") is not False:
        raise ValueError("The development manifest violates mismatch separation.")

    actual_hash = sha256_file(DATASET_PATH)
    expected_hash = str(manifest.get("dataset_sha256", ""))
    if actual_hash != expected_hash:
        raise ValueError(
            "Development dataset SHA-256 does not match its manifest. "
            "Regenerate the dataset before evaluating it."
        )
    return manifest


def load_records() -> list[dict[str, str]]:
    if not DATASET_PATH.exists():
        raise FileNotFoundError(
            f"Development dataset was not found: {DATASET_PATH}"
        )

    with DATASET_PATH.open("r", encoding="utf-8-sig", newline="") as handle:
        records = list(csv.DictReader(handle))

    if not records:
        raise ValueError("The development dataset is empty.")

    case_ids: set[str] = set()
    for record in records:
        case_id = str(record.get("case_id", "")).strip()
        expected = str(record.get("expected_status", "")).strip().upper()
        split = str(record.get("split", "")).strip().casefold()
        holdout_value = str(record.get("eligible_for_holdout", "")).strip().casefold()

        if not case_id or case_id in case_ids:
            raise ValueError(f"Missing or duplicate case ID: {case_id!r}")
        if expected not in VALID_EXPECTED_STATUSES:
            raise ValueError(
                f"Unsupported expected status in {case_id}: {expected!r}"
            )
        if split != "development":
            raise ValueError(f"Non-development record found: {case_id}")
        if holdout_value not in {"false", "0", "no"}:
            raise ValueError(f"Record is not explicitly excluded from holdout: {case_id}")

        case_ids.add(case_id)
        record["expected_status"] = expected

    return records


def balanced_selection(
    records: list[dict[str, str]],
    sample_per_status: int,
    limit: int,
) -> list[dict[str, str]]:
    if sample_per_status <= 0:
        selected = list(records)
    else:
        group_counts: Counter[tuple[str, str]] = Counter()
        selected = []

        for record in records:
            key = (
                str(record.get("relation", "unknown")),
                str(record.get("expected_status", "")),
            )
            if group_counts[key] >= sample_per_status:
                continue
            group_counts[key] += 1
            selected.append(record)

    if limit > 0:
        selected = selected[:limit]
    return selected


def read_checkpoint(path: Path) -> dict[str, dict[str, Any]]:
    completed: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return completed

    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            cleaned = line.strip()
            if not cleaned:
                continue
            try:
                row = json.loads(cleaned)
            except json.JSONDecodeError:
                if line_number > 1:
                    continue
                raise
            case_id = str(row.get("case_id", ""))
            if case_id:
                completed[case_id] = row
    return completed


def append_checkpoint(path: Path, row: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(row, ensure_ascii=False) + "\n"
    last_error: PermissionError | None = None

    for attempt in range(CHECKPOINT_RETRY_ATTEMPTS):
        try:
            with path.open("a", encoding="utf-8") as handle:
                handle.write(serialized)
                handle.flush()
                os.fsync(handle.fileno())
            return
        except PermissionError as error:
            last_error = error
            time.sleep(CHECKPOINT_RETRY_DELAY_SECONDS * (attempt + 1))

    if last_error is not None:
        raise PermissionError(
            f"Checkpoint remained locked after retries: {path}"
        ) from last_error


def remove_run_checkpoint(path: Path) -> None:
    if not path.exists():
        return
    resolved_path = path.resolve()
    resolved_root = REPORT_ROOT.resolve()
    if resolved_root not in resolved_path.parents:
        raise ValueError("Refusing to remove a checkpoint outside the report directory.")
    path.unlink()


def predicted_development_status(
    expected_status: str,
    result: dict[str, Any],
) -> str:
    stable_eligible = bool(result.get("stable_knowledge_eligible", False))
    parser_relation = str(
        result.get("stable_knowledge_v3_parser_relation", "unknown")
    )

    if expected_status == "NOT_ROUTED":
        if not stable_eligible:
            return "NOT_ROUTED"
        return str(result.get("evidence_status", "NOT_ENOUGH_INFO"))

    if parser_relation == "unknown" or not stable_eligible:
        return "NOT_ENOUGH_INFO"

    return str(result.get("evidence_status", "NOT_ENOUGH_INFO")).upper()


def transient_retrieval_warnings(result: dict[str, Any]) -> list[str]:
    warnings = [str(value) for value in result.get("warnings", [])]
    return [
        warning
        for warning in warnings
        if any(
            marker in warning.casefold()
            for marker in TRANSIENT_RETRIEVAL_MARKERS
        )
    ]


def evaluate_record(record: dict[str, str]) -> dict[str, Any]:
    case_id = record["case_id"]
    expected_status = record["expected_status"]
    claim = str(record.get("claim", ""))
    started = time.perf_counter()
    result: dict[str, Any] = {}
    processing_errors: list[str] = []
    attempt_count = 0

    for attempt in range(1, MAXIMUM_RECORD_ATTEMPTS + 1):
        attempt_count = attempt
        attempt_failed = False

        try:
            result = analyze_fact_check(claim)
        except Exception as error:  # Preserve the diagnostic and retry safely.
            attempt_failed = True
            processing_errors.append(
                f"Attempt {attempt}: {type(error).__name__}: {error}"
            )
            result = {}

        transient_warnings = transient_retrieval_warnings(result)
        evidence_status = str(
            result.get("evidence_status", "NOT_ENOUGH_INFO")
        ).upper()
        should_retry = bool(
            expected_status in CONCLUSIVE_STATUSES
            and attempt < MAXIMUM_RECORD_ATTEMPTS
            and (
                attempt_failed
                or (
                    transient_warnings
                    and evidence_status not in CONCLUSIVE_STATUSES
                )
            )
        )

        if not should_retry:
            break

        delay = RECORD_RETRY_DELAYS_SECONDS[
            min(attempt - 1, len(RECORD_RETRY_DELAYS_SECONDS) - 1)
        ]
        print(
            f"    Transient retrieval failure for {case_id}; "
            f"retrying in {delay:.0f} seconds "
            f"(attempt {attempt + 1}/{MAXIMUM_RECORD_ATTEMPTS})."
        )
        time.sleep(delay)

    processing_error = "" if result else "; ".join(processing_errors)

    elapsed_seconds = round(time.perf_counter() - started, 3)
    predicted_status = (
        "ERROR"
        if processing_error and not result
        else predicted_development_status(expected_status, result)
    )
    correct = predicted_status == expected_status
    stable_eligible = bool(result.get("stable_knowledge_eligible", False))
    expected_routing = str(record.get("expected_routing", ""))
    routing_correct = bool(
        (expected_routing == "stable_knowledge" and stable_eligible)
        or (expected_routing == "other_policy_path" and not stable_eligible)
    )
    transient_warnings = transient_retrieval_warnings(result)
    retrieval_degraded = bool(transient_warnings)
    infrastructure_failure = bool(
        expected_status in CONCLUSIVE_STATUSES
        and predicted_status not in CONCLUSIVE_STATUSES
        and transient_warnings
    )

    policy_failures: list[str] = []
    if result.get("automatic_enforcement_allowed") is not False:
        policy_failures.append("automatic_enforcement_was_allowed")
    if result.get("stable_knowledge_cache_allowed") is not False:
        policy_failures.append("stable_knowledge_cache_was_allowed")
    if result.get("stable_knowledge_persistent_cache_used") is not False:
        policy_failures.append("non_pib_persistent_cache_was_used")
    if stable_eligible and float(result.get("confidence", 0.0) or 0.0) > 0.80:
        policy_failures.append("stable_knowledge_confidence_cap_exceeded")
    if expected_status == "REFUTES":
        if predicted_status == "REFUTES" and result.get("human_review_required") is not True:
            policy_failures.append("refutation_did_not_require_human_review")
        if predicted_status == "REFUTES" and result.get("action") != "Refer to human review":
            policy_failures.append("refutation_action_was_not_human_review")

    return {
        "case_id": case_id,
        "topic": record.get("topic", ""),
        "relation": record.get("relation", ""),
        "template_type": record.get("template_type", ""),
        "expected_status": expected_status,
        "predicted_status": predicted_status,
        "correct": correct,
        "expected_routing": expected_routing,
        "routing_correct": routing_correct,
        "claim": claim,
        "category": result.get("category"),
        "confidence": result.get("confidence"),
        "action": result.get("action"),
        "human_review_required": result.get("human_review_required"),
        "automatic_enforcement_allowed": result.get(
            "automatic_enforcement_allowed"
        ),
        "stable_knowledge_eligible": stable_eligible,
        "parser_relation": result.get("stable_knowledge_v3_parser_relation"),
        "parser_subject": result.get("stable_knowledge_v3_parser_subject"),
        "parser_object": result.get("stable_knowledge_v3_parser_object"),
        "structured_retrieval_used": result.get(
            "stable_knowledge_v3_structured_retrieval_used"
        ),
        "legacy_fallback_used": result.get(
            "stable_knowledge_v3_legacy_fallback_used"
        ),
        "structured_verdict": result.get(
            "stable_knowledge_v3_structured_verdict"
        ),
        "evidence_conflict_detected": result.get(
            "evidence_conflict_detected",
            False,
        ),
        "support_source_count": result.get("support_source_count", 0),
        "refute_source_count": result.get("refute_source_count", 0),
        "source_names": result.get("stable_knowledge_sources", []),
        "policy_failures": policy_failures,
        "warnings": result.get("warnings", []),
        "transient_retrieval_warnings": transient_warnings,
        "retrieval_degraded": retrieval_degraded,
        "infrastructure_failure": infrastructure_failure,
        "attempt_count": attempt_count,
        "attempt_processing_errors": processing_errors,
        "processing_error": processing_error,
        "elapsed_seconds": elapsed_seconds,
        "engine_version": result.get("engine_version"),
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
    }


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def percentage(value: float) -> float:
    return round(value * 100.0, 2)


def status_metrics(
    rows: list[dict[str, Any]],
    status: str,
) -> dict[str, Any]:
    true_positive = sum(
        row["expected_status"] == status and row["predicted_status"] == status
        for row in rows
    )
    false_positive = sum(
        row["expected_status"] != status and row["predicted_status"] == status
        for row in rows
    )
    false_negative = sum(
        row["expected_status"] == status and row["predicted_status"] != status
        for row in rows
    )
    support = sum(row["expected_status"] == status for row in rows)
    precision = safe_divide(true_positive, true_positive + false_positive)
    recall = safe_divide(true_positive, true_positive + false_negative)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    return {
        "support": support,
        "precision_percent": percentage(precision),
        "recall_percent": percentage(recall),
        "f1_percent": percentage(f1),
    }


def build_report(
    rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    run_name: str,
) -> dict[str, Any]:
    total = len(rows)
    correct = sum(bool(row["correct"]) for row in rows)
    routing_correct = sum(bool(row["routing_correct"]) for row in rows)
    expected_conclusive = [
        row for row in rows if row["expected_status"] in CONCLUSIVE_STATUSES
    ]
    predicted_conclusive = [
        row for row in expected_conclusive
        if row["predicted_status"] in CONCLUSIVE_STATUSES
    ]
    selective_correct = sum(bool(row["correct"]) for row in predicted_conclusive)
    policy_failure_count = sum(len(row["policy_failures"]) for row in rows)
    processing_error_count = sum(bool(row["processing_error"]) for row in rows)
    infrastructure_failure_count = sum(
        bool(row.get("infrastructure_failure", False)) for row in rows
    )
    retrieval_degraded_count = sum(
        bool(row.get("retrieval_degraded", False)) for row in rows
    )
    logic_rows = [
        row
        for row in rows
        if not row.get("infrastructure_failure", False)
        and not row.get("processing_error")
    ]
    logic_correct = sum(bool(row["correct"]) for row in logic_rows)
    conflict_count = sum(
        bool(row["evidence_conflict_detected"]) for row in rows
    )

    status_names = ["SUPPORTS", "REFUTES", "NOT_ROUTED"]
    status_results = {
        status: status_metrics(rows, status)
        for status in status_names
    }
    macro_f1 = safe_divide(
        sum(result["f1_percent"] for result in status_results.values()),
        len(status_results),
    )

    relation_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        relation_groups[str(row.get("relation", "unknown"))].append(row)

    relation_results = {
        relation: {
            "records": len(group),
            "correct": sum(bool(row["correct"]) for row in group),
            "accuracy_percent": percentage(
                safe_divide(
                    sum(bool(row["correct"]) for row in group),
                    len(group),
                )
            ),
        }
        for relation, group in sorted(relation_groups.items())
    }

    exact_accuracy = percentage(safe_divide(correct, total))
    routing_accuracy = percentage(safe_divide(routing_correct, total))
    selective_accuracy = percentage(
        safe_divide(selective_correct, len(predicted_conclusive))
    )
    conclusive_coverage = percentage(
        safe_divide(len(predicted_conclusive), len(expected_conclusive))
    )
    logic_accuracy = percentage(
        safe_divide(logic_correct, len(logic_rows))
    )
    development_gate = bool(
        exact_accuracy >= 85.0
        and routing_accuracy >= 95.0
        and selective_accuracy >= 90.0
        and conclusive_coverage >= 85.0
        and policy_failure_count == 0
        and processing_error_count == 0
        and infrastructure_failure_count == 0
    )

    return {
        "evaluation_type": "development_only_not_independent_accuracy",
        "run_name": run_name,
        "dataset_version": manifest.get("version"),
        "dataset_sha256": manifest.get("dataset_sha256"),
        "records": total,
        "correct": correct,
        "incorrect": total - correct,
        "exact_accuracy_percent": exact_accuracy,
        "macro_f1_percent": round(macro_f1, 2),
        "routing_accuracy_percent": routing_accuracy,
        "selective_accuracy_percent": selective_accuracy,
        "expected_conclusive_coverage_percent": conclusive_coverage,
        "logic_records_excluding_infrastructure_failures": len(logic_rows),
        "logic_correct_excluding_infrastructure_failures": logic_correct,
        "logic_accuracy_excluding_infrastructure_failures_percent": (
            logic_accuracy
        ),
        "predicted_conclusive_records": len(predicted_conclusive),
        "expected_conclusive_records": len(expected_conclusive),
        "evidence_conflicts": conflict_count,
        "policy_contract_failures": policy_failure_count,
        "processing_errors": processing_error_count,
        "retrieval_degraded_records": retrieval_degraded_count,
        "retrieval_infrastructure_failures": infrastructure_failure_count,
        "passed_development_gate": development_gate,
        "status_results": status_results,
        "relation_results": relation_results,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "holdout_separation": {
            "uses_v2_holdout_records": False,
            "uses_v2_mismatch_report": False,
            "eligible_for_independent_accuracy_claim": False,
        },
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "case_id",
        "topic",
        "relation",
        "template_type",
        "expected_status",
        "predicted_status",
        "correct",
        "expected_routing",
        "routing_correct",
        "claim",
        "category",
        "confidence",
        "action",
        "human_review_required",
        "automatic_enforcement_allowed",
        "stable_knowledge_eligible",
        "parser_relation",
        "parser_subject",
        "parser_object",
        "structured_retrieval_used",
        "legacy_fallback_used",
        "structured_verdict",
        "evidence_conflict_detected",
        "support_source_count",
        "refute_source_count",
        "source_names",
        "policy_failures",
        "warnings",
        "transient_retrieval_warnings",
        "retrieval_degraded",
        "infrastructure_failure",
        "attempt_count",
        "attempt_processing_errors",
        "processing_error",
        "elapsed_seconds",
        "engine_version",
        "evaluated_at",
    ]

    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            serialized = dict(row)
            for name in (
                "source_names",
                "policy_failures",
                "warnings",
                "transient_retrieval_warnings",
                "attempt_processing_errors",
            ):
                serialized[name] = json.dumps(
                    serialized.get(name, []),
                    ensure_ascii=False,
                )
            writer.writerow({name: serialized.get(name) for name in fieldnames})


def print_report(report: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("STABLE KNOWLEDGE V3 DEVELOPMENT RESULTS")
    print("=" * 60)
    print(f"Run: {report['run_name']}")
    print(f"Records: {report['records']}")
    print(f"Exact development accuracy: {report['exact_accuracy_percent']:.2f}%")
    print(f"Macro F1: {report['macro_f1_percent']:.2f}%")
    print(f"Routing accuracy: {report['routing_accuracy_percent']:.2f}%")
    print(f"Selective accuracy: {report['selective_accuracy_percent']:.2f}%")
    print(
        "Expected-conclusive coverage: "
        f"{report['expected_conclusive_coverage_percent']:.2f}%"
    )
    print(
        "Logic accuracy excluding infrastructure failures: "
        f"{report['logic_accuracy_excluding_infrastructure_failures_percent']:.2f}% "
        f"({report['logic_records_excluding_infrastructure_failures']} records)"
    )
    print(f"Evidence conflicts: {report['evidence_conflicts']}")
    print(f"Policy contract failures: {report['policy_contract_failures']}")
    print(f"Processing errors: {report['processing_errors']}")
    print(
        "Retrieval infrastructure failures: "
        f"{report['retrieval_infrastructure_failures']}"
    )
    print(
        "Retrieval-degraded records: "
        f"{report['retrieval_degraded_records']}"
    )
    print(f"Passed development gate: {report['passed_development_gate']}")

    print("\nRELATION RESULTS")
    print("-" * 60)
    for relation, result in report["relation_results"].items():
        print(
            f"{relation}: {result['correct']}/{result['records']} "
            f"({result['accuracy_percent']:.2f}%)"
        )

    print("\nThis is a development score, not independent accuracy.")
    print("The V2 holdout and its mismatch report were not used.")


def main() -> None:
    arguments = parse_arguments()
    run_name = safe_run_name(arguments.run_name)
    manifest = load_manifest()
    records = balanced_selection(
        load_records(),
        sample_per_status=max(arguments.sample_per_status, 0),
        limit=max(arguments.limit, 0),
    )
    if not records:
        raise ValueError("No development records were selected.")

    run_directory = REPORT_ROOT / run_name
    checkpoint_path = run_directory / "checkpoint.jsonl"
    if arguments.fresh:
        remove_run_checkpoint(checkpoint_path)

    completed = read_checkpoint(checkpoint_path)
    selected_case_ids = {record["case_id"] for record in records}
    completed = {
        case_id: row
        for case_id, row in completed.items()
        if case_id in selected_case_ids
    }

    print("Starting Stable Knowledge V3 development evaluation...")
    print(f"Selected records: {len(records)}")
    print(f"Already completed: {len(completed)}")
    print("Progress is checkpointed after every record.")
    print("This does not read the V2 holdout or mismatch report.\n")

    for index, record in enumerate(records, start=1):
        case_id = record["case_id"]
        if case_id in completed:
            row = completed[case_id]
            source = "checkpoint"
        else:
            row = evaluate_record(record)
            append_checkpoint(checkpoint_path, row)
            completed[case_id] = row
            source = "new"

        marker = "correct" if row["correct"] else "mismatch"
        print(
            f"[{index}/{len(records)}] {case_id} "
            f"{row['expected_status']} -> {row['predicted_status']} "
            f"({marker}, {source})"
        )

    ordered_rows = [completed[record["case_id"]] for record in records]
    report = build_report(ordered_rows, manifest, run_name)
    report_path = run_directory / "report.json"
    results_path = run_directory / "results.csv"
    mismatches_path = run_directory / "mismatches.csv"

    run_directory.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    write_csv(results_path, ordered_rows)
    write_csv(
        mismatches_path,
        [row for row in ordered_rows if not row["correct"]],
    )

    print_report(report)
    print(f"\nReport saved: {report_path}")
    print(f"Results saved: {results_path}")
    print(f"Development mismatches saved: {mismatches_path}")


if __name__ == "__main__":
    main()
