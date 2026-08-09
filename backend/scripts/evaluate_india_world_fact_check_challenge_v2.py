from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any

from scripts import evaluate_india_world_fact_check_challenge as base


CHALLENGE_VERSION = "2026.08-v2"


def make_case(
    case_id: str,
    region: str,
    expected_status: str,
    high_impact: bool,
    claim: str,
    truth_source: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "region": region,
        "expected_status": expected_status,
        "high_impact": high_impact,
        "claim": claim,
        "truth_source": truth_source,
    }


CASES: tuple[dict[str, Any], ...] = (
    make_case(
        "V2-IN-S-001",
        "India",
        "SUPPORTS",
        False,
        "ISRO launched the Chandrayaan-3 spacecraft on 14 July 2023.",
        "https://www.isro.gov.in/ISRO_EN/Chandrayaan3.html",
    ),
    make_case(
        "V2-IN-S-002",
        "India",
        "SUPPORTS",
        True,
        "The GST Council is constituted under Article 279A of the Constitution of India.",
        "https://gstcouncil.gov.in/gst-council-0",
    ),
    make_case(
        "V2-IN-S-003",
        "India",
        "SUPPORTS",
        True,
        "Rajya Sabha is a permanent House and is not subject to dissolution.",
        "https://cms.rajyasabha.nic.in/UploadedFiles/ElectronicPublications/FAQ.pdf",
    ),
    make_case(
        "V2-IN-S-004",
        "India",
        "SUPPORTS",
        True,
        "India's Parliament consists of the President, Rajya Sabha, and Lok Sabha.",
        "https://cms.rajyasabha.nic.in/UploadedFiles/ElectronicPublications/FAQ.pdf",
    ),
    make_case(
        "V2-IN-S-005",
        "India",
        "SUPPORTS",
        True,
        "The Reserve Bank of India is the nation's sole banknote-issuing authority.",
        "https://www.rbi.org.in/scripts/FS_FAQs.aspx?Id=136&fn=2753",
    ),
    make_case(
        "V2-IN-S-006",
        "India",
        "SUPPORTS",
        False,
        "One-rupee currency notes are issued by the Government of India.",
        "https://www.rbi.org.in/commonperson/english/scripts/PressReleases.aspx?Id=2346",
    ),
    make_case(
        "V2-IN-R-001",
        "India",
        "REFUTES",
        False,
        "Chandrayaan-3 was an Indian mission that landed on Mars.",
        "https://www.isro.gov.in/ISRO_EN/Chandrayaan3.html",
    ),
    make_case(
        "V2-IN-R-002",
        "India",
        "REFUTES",
        True,
        "Rajya Sabha is automatically dissolved every five years.",
        "https://cms.rajyasabha.nic.in/UploadedFiles/ElectronicPublications/FAQ.pdf",
    ),
    make_case(
        "V2-IN-R-003",
        "India",
        "REFUTES",
        True,
        "The World Health Organization created and operates India's GST Council.",
        "https://gstcouncil.gov.in/gst-council-0",
    ),
    make_case(
        "V2-IN-R-004",
        "India",
        "REFUTES",
        True,
        "The President of India is not a component of Parliament.",
        "https://cms.rajyasabha.nic.in/UploadedFiles/ElectronicPublications/FAQ.pdf",
    ),
    make_case(
        "V2-IN-R-005",
        "India",
        "REFUTES",
        True,
        "The Reserve Bank of India administers elections to the Lok Sabha.",
        "https://www.rbi.org.in/CommonPerson/english/History/Scripts/BriefHistory.aspx",
    ),
    make_case(
        "V2-IN-R-006",
        "India",
        "REFUTES",
        False,
        "Every one-rupee currency note is issued by the Reserve Bank of India.",
        "https://www.rbi.org.in/commonperson/english/scripts/PressReleases.aspx?Id=2346",
    ),
    make_case(
        "V2-IN-N-001",
        "India",
        "NOT_ENOUGH_INFO",
        True,
        "An anonymous audio message says an unnamed state election will be postponed tomorrow.",
        "No state, election, order, authority, or calendar date is identified.",
    ),
    make_case(
        "V2-IN-N-002",
        "India",
        "NOT_ENOUGH_INFO",
        True,
        "A screenshot claims an unnamed Indian regulator will prohibit an unspecified banking service tonight.",
        "No regulator, service, notification, source, or calendar date is identified.",
    ),
    make_case(
        "V2-IN-N-003",
        "India",
        "NOT_ENOUGH_INFO",
        True,
        "A forwarded post says a new benefit will be paid to everyone next week without naming the scheme.",
        "No scheme, ministry, eligibility rule, notification, or date is identified.",
    ),
    make_case(
        "V2-IN-N-004",
        "India",
        "NOT_ENOUGH_INFO",
        True,
        "An anonymous account says an unspecified Indian space launch has failed today.",
        "No mission, launch vehicle, source, location, or time is identified.",
    ),
    make_case(
        "V2-IN-N-005",
        "India",
        "NOT_ENOUGH_INFO",
        True,
        "A message says an unnamed city will impose an immediate curfew but cites no order.",
        "No city, authority, order number, source, or calendar date is identified.",
    ),
    make_case(
        "V2-IN-N-006",
        "India",
        "NOT_ENOUGH_INFO",
        True,
        "A viral image says a national law changed this morning without naming the law or amendment.",
        "No law, amendment, gazette notification, source, or date is identified.",
    ),
    make_case(
        "V2-WO-S-001",
        "World",
        "SUPPORTS",
        True,
        "The Constitution of the World Health Organization entered into force on 7 April 1948.",
        "https://www.who.int/about/governance/constitution",
    ),
    make_case(
        "V2-WO-S-002",
        "World",
        "SUPPORTS",
        False,
        "The Moon is Earth's natural satellite.",
        "https://science.nasa.gov/moon/facts/",
    ),
    make_case(
        "V2-WO-S-003",
        "World",
        "SUPPORTS",
        False,
        "The World Bank has its headquarters in Washington, DC.",
        "https://www.worldbank.org/ps/about",
    ),
    make_case(
        "V2-WO-S-004",
        "World",
        "SUPPORTS",
        False,
        "The United Nations Sustainable Development framework contains 17 goals.",
        "https://sdgs.un.org/goals",
    ),
    make_case(
        "V2-WO-S-005",
        "World",
        "SUPPORTS",
        False,
        "The Constitution of UNESCO was signed on 16 November 1945.",
        "https://unesdoc.unesco.org/archives/about-unesco-history-and-mission",
    ),
    make_case(
        "V2-WO-S-006",
        "World",
        "SUPPORTS",
        False,
        "The Moon travels around Earth.",
        "https://science.nasa.gov/moon/facts/",
    ),
    make_case(
        "V2-WO-R-001",
        "World",
        "REFUTES",
        True,
        "The World Health Organization's Constitution entered into force in 1988.",
        "https://www.who.int/about/governance/constitution",
    ),
    make_case(
        "V2-WO-R-002",
        "World",
        "REFUTES",
        False,
        "The Moon is a planet that orbits Mars.",
        "https://science.nasa.gov/moon/top-moon-questions/",
    ),
    make_case(
        "V2-WO-R-003",
        "World",
        "REFUTES",
        False,
        "The headquarters of the World Bank is in Geneva, Switzerland.",
        "https://www.worldbank.org/ps/about",
    ),
    make_case(
        "V2-WO-R-004",
        "World",
        "REFUTES",
        False,
        "The United Nations Sustainable Development framework contains 25 goals.",
        "https://sdgs.un.org/goals",
    ),
    make_case(
        "V2-WO-R-005",
        "World",
        "REFUTES",
        False,
        "UNESCO is a private commercial bank.",
        "https://www.unesco.org/en/about-us/history",
    ),
    make_case(
        "V2-WO-R-006",
        "World",
        "REFUTES",
        False,
        "The Moon produces its own visible light in the same way as the Sun.",
        "https://science.nasa.gov/moon/top-moon-questions/",
    ),
    make_case(
        "V2-WO-N-001",
        "World",
        "NOT_ENOUGH_INFO",
        True,
        "An anonymous post says an unnamed health body approved a secret treatment this morning.",
        "No health body, treatment, decision, publication, or date is identified.",
    ),
    make_case(
        "V2-WO-N-002",
        "World",
        "NOT_ENOUGH_INFO",
        True,
        "A message claims an unspecified spacecraft will collide with Earth next week.",
        "No spacecraft, agency, observation, source, or calendar date is identified.",
    ),
    make_case(
        "V2-WO-N-003",
        "World",
        "NOT_ENOUGH_INFO",
        True,
        "A private channel says an unnamed development bank will cancel all loans tomorrow.",
        "No bank, loan programme, announcement, source, or calendar date is identified.",
    ),
    make_case(
        "V2-WO-N-004",
        "World",
        "NOT_ENOUGH_INFO",
        True,
        "A viral image says an unidentified country joined an unnamed global organization today.",
        "No country, organization, announcement, source, or date is identified.",
    ),
    make_case(
        "V2-WO-N-005",
        "World",
        "NOT_ENOUGH_INFO",
        True,
        "An anonymous account reports that a newly discovered moon vanished last night.",
        "No object designation, observatory, scientist, publication, or date is identified.",
    ),
    make_case(
        "V2-WO-N-006",
        "World",
        "NOT_ENOUGH_INFO",
        True,
        "A forwarded message says every international school will use a new curriculum next month.",
        "No jurisdiction, organization, curriculum, decision, or effective date is identified.",
    ),
)


def validate_v2() -> None:
    identifiers = [case["case_id"] for case in CASES]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("V2 contains duplicate case IDs.")

    counts = Counter(
        (case["region"], case["expected_status"])
        for case in CASES
    )
    expected = {
        (region, status): 6
        for region in ("India", "World")
        for status in ("SUPPORTS", "REFUTES", "NOT_ENOUGH_INFO")
    }
    if counts != expected:
        raise ValueError(f"V2 is not balanced: {dict(counts)}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument(
        "--region",
        choices=("all", "India", "World"),
        default="all",
    )
    parser.add_argument("--fresh", action="store_true")
    args = parser.parse_args()

    validate_v2()
    base.CHALLENGE_VERSION = CHALLENGE_VERSION
    challenge_hash = base.canonical_challenge_hash(list(CASES))

    selected = [
        case
        for case in CASES
        if args.region == "all" or case["region"] == args.region
    ]
    if args.limit > 0:
        selected = selected[: args.limit]

    project_directory = Path(__file__).resolve().parents[2]
    output_directory = (
        project_directory
        / "reports"
        / "evaluation"
        / "misinformation"
        / "india_world_challenge_v2"
    )
    output_directory.mkdir(parents=True, exist_ok=True)

    checkpoint_path = output_directory / "checkpoint.jsonl"
    report_path = output_directory / "report.json"
    results_path = output_directory / "results.csv"
    mismatches_path = output_directory / "mismatches.csv"

    if args.fresh:
        base.clear_checkpoints(checkpoint_path)

    completed = base.read_checkpoint(checkpoint_path)
    rows: list[dict[str, Any]] = []

    print("Starting frozen unseen India + world fact-check challenge V2...")
    print(f"Selected records: {len(selected)}")
    print(f"Challenge SHA-256: {challenge_hash}")
    print("Do not change the model or evidence library during this run.\n")

    for index, case in enumerate(selected, start=1):
        existing = completed.get(case["case_id"])
        if existing:
            row = existing
            state = "saved"
        else:
            row = base.evaluate_case(case)
            base.append_checkpoint(checkpoint_path, row)
            state = "new"
        rows.append(row)
        print(
            f"[{index}/{len(selected)}] {case['case_id']} "
            f"{case['expected_status']} -> {row['predicted_status']} ({state})"
        )

    report = base.build_report(rows, challenge_hash)
    report["benchmark_integrity"] = {
        "unseen_before_first_run": True,
        "created_after_v1_regression": True,
        "rule": (
            "This V2 score is the independent baseline. If V2 results are used "
            "to modify the system, V2 becomes a regression set and a new unseen "
            "challenge is required for the next independent score."
        ),
    }
    report["report_scope"] = {
        "region": args.region,
        "limit": args.limit,
        "selected_case_ids": [case["case_id"] for case in selected],
    }

    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    base.write_csv(results_path, rows)
    base.write_csv(
        mismatches_path,
        [row for row in rows if not row["correct"]],
    )
    base.print_report(report)
    print(f"\nReport saved: {report_path}")
    print(f"Results saved: {results_path}")
    print(f"Mismatches saved: {mismatches_path}")


if __name__ == "__main__":
    main()
