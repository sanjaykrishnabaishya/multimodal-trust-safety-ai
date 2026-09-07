from __future__ import annotations

import json
import os
import platform
import statistics
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any


# A public documentation benchmark must never contact an external AI provider.
os.environ["TRUSTSCOPE_OPENROUTER_ENABLED"] = "false"

from fastapi.testclient import TestClient

from app.main import app
from app.services import review_database_service


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = PROJECT_ROOT / "docs" / "PERFORMANCE_SNAPSHOT.json"

CASES = (
    "The library opens at nine and the community class starts at ten.",
    "This report explains how defenders detected and removed ransomware.",
    "A credential stealer is hosted for download by unrelated users.",
    "The message asks for a password and one-time code through a fake login page.",
    "A licensed pharmacy explains how patients can collect approved medicine.",
    "The privacy guide explains how to disable unwanted location tracking.",
)

USER_LEVELS = (1, 5, 10)
REQUESTS_BY_LEVEL = {1: 20, 5: 25, 10: 50}


def percentile(values: list[float], percent: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0

    position = (len(ordered) - 1) * percent
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] + (ordered[upper] - ordered[lower]) * fraction


def run_request(client: TestClient, index: int) -> dict[str, Any]:
    started = perf_counter()

    try:
        response = client.post(
            "/moderation/text",
            json={
                "text": f"{CASES[index % len(CASES)]} Benchmark case {index}.",
                "source_context": "readme_benchmark",
            },
        )
        payload = response.json()
        succeeded = (
            response.status_code == 200
            and isinstance(payload.get("category"), str)
            and isinstance(payload.get("action"), str)
        )
        error = None if succeeded else f"HTTP {response.status_code}"
    except Exception as exc:  # pragma: no cover - diagnostic boundary
        succeeded = False
        error = type(exc).__name__

    return {
        "success": succeeded,
        "latency_ms": (perf_counter() - started) * 1000,
        "error": error,
    }


def benchmark_level(
    client: TestClient,
    *,
    users: int,
    requests: int,
) -> dict[str, Any]:
    started = perf_counter()

    with ThreadPoolExecutor(max_workers=users) as executor:
        results = list(executor.map(lambda index: run_request(client, index), range(requests)))

    elapsed = perf_counter() - started
    latencies = [result["latency_ms"] for result in results]
    successful = sum(1 for result in results if result["success"])
    errors: dict[str, int] = {}

    for result in results:
        if result["error"]:
            errors[result["error"]] = errors.get(result["error"], 0) + 1

    return {
        "simulated_users": users,
        "requests": requests,
        "successful_requests": successful,
        "success_rate_percent": round(successful / requests * 100, 2),
        "median_response_ms": round(statistics.median(latencies), 2),
        "p95_response_ms": round(percentile(latencies, 0.95), 2),
        "average_response_ms": round(statistics.fmean(latencies), 2),
        "throughput_requests_per_second": round(requests / elapsed, 2),
        "errors": errors,
    }


def main() -> None:
    original_data_directory = review_database_service.DATA_DIRECTORY
    original_database_path = review_database_service.DATABASE_PATH
    warm_up_seconds = 0.0

    try:
        # Windows can briefly retain a SQLite file handle after concurrent
        # requests finish. The benchmark data is temporary, so a delayed OS
        # cleanup must not discard otherwise valid timing results.
        with tempfile.TemporaryDirectory(
            prefix="trustscope-readme-benchmark-",
            ignore_cleanup_errors=True,
        ) as temporary:
            temporary_directory = Path(temporary)
            review_database_service.DATA_DIRECTORY = temporary_directory
            review_database_service.DATABASE_PATH = temporary_directory / "reviews.db"

            with TestClient(app) as client:
                warm_up_started = perf_counter()
                warm_up_results = [
                    run_request(client, index)
                    for index in range(len(CASES))
                ]
                warm_up_seconds = perf_counter() - warm_up_started

                for warm_up in warm_up_results:
                    if not warm_up["success"]:
                        raise RuntimeError(f"Warm-up request failed: {warm_up['error']}")

                results = [
                    benchmark_level(
                        client,
                        users=users,
                        requests=REQUESTS_BY_LEVEL[users],
                    )
                    for users in USER_LEVELS
                ]
    finally:
        review_database_service.DATA_DIRECTORY = original_data_directory
        review_database_service.DATABASE_PATH = original_database_path

    total_requests = sum(result["requests"] for result in results)
    total_successful = sum(result["successful_requests"] for result in results)

    report = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": (
            "In-process text moderation API benchmark after warming each of the "
            "six representative text paths."
        ),
        "warning": (
            "This is a small local development measurement, not a production "
            "capacity promise. File, OCR, image, video, network, and external-AI "
            "time are not included."
        ),
        "external_ai_enabled": False,
        "machine": {
            "operating_system": platform.system(),
            "python_version": platform.python_version(),
            "logical_cpu_count": os.cpu_count(),
        },
        "maximum_simulated_users": max(USER_LEVELS),
        "six_path_cold_start_and_warm_up_seconds": round(warm_up_seconds, 2),
        "total_requests": total_requests,
        "successful_requests": total_successful,
        "overall_success_rate_percent": round(total_successful / total_requests * 100, 2),
        "results": results,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
