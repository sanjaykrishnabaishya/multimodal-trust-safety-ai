from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


EXPECTED_HEADERS = (
    "Hindi transliteration",
    "Devanagari",
    "Rough English translation",
)

# These forms have common non-abusive meanings in English or other technical
# contexts. They must never become unconditional keyword rules.
KNOWN_AMBIGUOUS_FORMS = {
    "b.c.": "May mean Before Christ or another English abbreviation.",
    "bc": "May mean British Columbia, Before Christ, because, or business continuity.",
    "m.c.": "May mean master of ceremonies or another English abbreviation.",
    "mc": "May mean master of ceremonies, Minecraft, motorcycle club, or another abbreviation.",
    "gu": "Very short form with many possible names and abbreviations.",
    "hag": "Can occur as an English word and still requires target and context checks.",
    "ling": "Can be a name, suffix, or technical abbreviation.",
    "maar": "Can occur in names or transliterated non-abusive phrases.",
    "maro": "Can occur in names or transliterated non-abusive phrases.",
    "paji": "Can be a respectful Punjabi/Hindi address depending on spelling and context.",
    "rand": "Can refer to a name, currency, or random-number function.",
}


def normalize_cell(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def normalize_latin_term(value: object) -> str:
    return normalize_cell(value).casefold()


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def stable_id(transliteration: str, devanagari: str) -> str:
    material = f"{transliteration}\u241f{devanagari}".encode("utf-8")
    return f"hin-abuse-{sha256_bytes(material)[:16]}"


def evidence_policy(term: str) -> tuple[str, str]:
    compact = re.sub(r"[^a-z0-9]", "", term)
    if term in KNOWN_AMBIGUOUS_FORMS:
        return "context_required", KNOWN_AMBIGUOUS_FORMS[term]
    if len(compact) <= 4:
        return (
            "context_required",
            "Short Romanized form; require Hindi/Hinglish and direct-target context.",
        )
    return (
        "lexical_candidate",
        "Still requires reporting/quotation, target, and category-boundary checks.",
    )


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Import an unverified Hindi abusive-word list as RC3 development "
            "evidence without connecting it to live moderation."
        )
    )
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    return parser.parse_args()


def main() -> None:
    args = parse_arguments()
    source = args.source.expanduser().resolve()
    repo_root = args.repo_root.expanduser().resolve()

    if not source.is_file():
        raise FileNotFoundError(f"Source CSV was not found: {source}")

    source_bytes = source.read_bytes()
    source_sha256 = sha256_bytes(source_bytes)

    try:
        decoded = source_bytes.decode("utf-8-sig")
        source_encoding = "utf-8-sig"
    except UnicodeDecodeError as error:
        raise ValueError(
            "The source must be UTF-8/UTF-8-BOM so Devanagari text is preserved."
        ) from error

    reader = csv.DictReader(decoded.splitlines())
    headers = tuple(reader.fieldnames or ())
    if headers != EXPECTED_HEADERS:
        raise ValueError(
            "Unexpected CSV columns. Expected exactly: "
            + ", ".join(EXPECTED_HEADERS)
        )

    raw_rows = list(reader)
    imported_rows: list[dict[str, str]] = []
    skipped_empty = 0
    exact_duplicate_rows = 0
    missing_devanagari = 0
    seen_pairs: set[tuple[str, str]] = set()
    transliteration_counts: Counter[str] = Counter()

    for raw_row in raw_rows:
        transliteration = normalize_latin_term(
            raw_row.get("Hindi transliteration")
        )
        devanagari = normalize_cell(raw_row.get("Devanagari"))
        translation = normalize_cell(
            raw_row.get("Rough English translation")
        )

        if not transliteration:
            skipped_empty += 1
            continue

        pair = (transliteration, devanagari)
        if pair in seen_pairs:
            exact_duplicate_rows += 1
            continue
        seen_pairs.add(pair)
        transliteration_counts[transliteration] += 1

        if not devanagari:
            missing_devanagari += 1

        mode, reason = evidence_policy(transliteration)
        imported_rows.append(
            {
                "entry_id": stable_id(transliteration, devanagari),
                "transliteration": transliteration,
                "devanagari": devanagari,
                "rough_english_translation": translation,
                "evidence_mode": mode,
                "ambiguity_or_safety_note": reason,
                "requires_direct_target_check": "true",
                "requires_reporting_context_check": "true",
                "automatic_enforcement_allowed": "false",
                "verification_status": "unverified_development_input",
            }
        )

    imported_rows.sort(
        key=lambda row: (row["transliteration"], row["devanagari"])
    )

    output_directory = (
        repo_root / "datasets" / "development" / "hindi_abusive_rc3"
    )
    report_directory = (
        repo_root
        / "reports"
        / "evaluation"
        / "cyberbullying"
        / "hindi_abusive_rc3"
    )
    output_directory.mkdir(parents=True, exist_ok=True)
    report_directory.mkdir(parents=True, exist_ok=True)

    lexicon_path = output_directory / "lexicon.csv"
    provenance_path = output_directory / "provenance.json"
    report_path = report_directory / "import_report.json"

    fieldnames = [
        "entry_id",
        "transliteration",
        "devanagari",
        "rough_english_translation",
        "evidence_mode",
        "ambiguity_or_safety_note",
        "requires_direct_target_check",
        "requires_reporting_context_check",
        "automatic_enforcement_allowed",
        "verification_status",
    ]
    with lexicon_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(imported_rows)

    context_required_count = sum(
        row["evidence_mode"] == "context_required" for row in imported_rows
    )
    repeated_transliterations = {
        term: count
        for term, count in sorted(transliteration_counts.items())
        if count > 1
    }
    generated_at = datetime.now(timezone.utc).isoformat()

    provenance = {
        "dataset_name": "Hindi abusive lexicon RC3 development input",
        "generated_at_utc": generated_at,
        "source_file_name": source.name,
        "source_sha256": source_sha256,
        "source_encoding": source_encoding,
        "source_license_status": "unknown",
        "redistribution_allowed": False,
        "live_moderation_allowed": False,
        "automatic_enforcement_allowed": False,
        "training_status": "not_a_contextual_training_dataset",
        "required_next_step": (
            "Create labeled Hindi/Hinglish abusive and non-abusive sentence "
            "contexts, including ambiguous abbreviations, then evaluate on a "
            "separate untouched holdout."
        ),
    }
    provenance_path.write_text(
        json.dumps(provenance, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    report = {
        **provenance,
        "raw_rows": len(raw_rows),
        "accepted_unique_rows": len(imported_rows),
        "skipped_empty_rows": skipped_empty,
        "exact_duplicate_rows_removed": exact_duplicate_rows,
        "repeated_transliterations_with_distinct_script_forms": (
            repeated_transliterations
        ),
        "missing_devanagari_rows": missing_devanagari,
        "context_required_rows": context_required_count,
        "lexical_candidate_rows": len(imported_rows) - context_required_count,
        "lexicon_sha256": sha256_bytes(lexicon_path.read_bytes()),
        "guardrails": [
            "BC, B.C., MC, and M.C. never trigger abuse without context.",
            "All short Romanized forms require Hindi/Hinglish and direct-target evidence.",
            "Reporting, education, quotation, and counterspeech must be checked.",
            "One primary category only; abusive language is supporting evidence when cyberbullying is primary.",
            "No record from this import may automatically enforce a moderation action.",
            "Frozen cyberbullying-v2-rc2 files must not be modified.",
        ],
    }
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("HINDI ABUSIVE LEXICON RC3 IMPORT")
    print("=" * 60)
    print(f"Raw rows: {len(raw_rows)}")
    print(f"Accepted unique rows: {len(imported_rows)}")
    print(f"Exact duplicate rows removed: {exact_duplicate_rows}")
    print(f"Missing Devanagari rows: {missing_devanagari}")
    print(f"Context-required entries: {context_required_count}")
    print(
        "Lexical candidates requiring target/reporting checks: "
        f"{len(imported_rows) - context_required_count}"
    )
    print(f"Lexicon: {lexicon_path}")
    print(f"Provenance: {provenance_path}")
    print(f"Report: {report_path}")
    print("Live moderation changed: False")
    print("Frozen RC2 changed: False")
    print("Automatic enforcement allowed: False")
    print(
        "Next: build labeled Hindi/Hinglish contexts and an untouched RC3 holdout."
    )


if __name__ == "__main__":
    main()
