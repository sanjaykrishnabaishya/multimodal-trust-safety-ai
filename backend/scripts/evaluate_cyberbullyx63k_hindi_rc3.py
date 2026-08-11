from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import xml.etree.ElementTree as ET
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from app.services.hindi_abusive_context_service import (
    ABUSIVE_CATEGORY,
    CYBER_CATEGORY,
    analyze_hindi_abusive_context,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIRECTORY = (
    REPO_ROOT
    / "reports"
    / "evaluation"
    / "cyberbullying"
    / "cyberbullyx63k_hindi_rc3"
)
REPORT_PATH = REPORT_DIRECTORY / "aggregate_report.json"
CANDIDATE_MANIFEST_PATH = (
    REPO_ROOT
    / "backend"
    / "storage"
    / "candidates"
    / "hindi-abusive-context-rc3"
    / "manifest.json"
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

DATASET_ID = "s2t8khj9ht"
DATASET_VERSION = 1
DATASET_DOI = "10.17632/s2t8khj9ht.1"
DATASET_PAGE = "https://data.mendeley.com/datasets/s2t8khj9ht/1"

XLSX_NAMESPACE = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL_NAMESPACE = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
PACKAGE_REL_NAMESPACE = "{http://schemas.openxmlformats.org/package/2006/relationships}"

TEXT_HEADER_CANDIDATES = {
    "text",
    "tweet",
    "tweettext",
    "fulltext",
    "cleanedtext",
    "content",
    "comment",
    "post",
}
LABEL_HEADER_CANDIDATES = {
    "finallabel",
    "label",
    "cyberbullying",
    "cyberbullyinglabel",
    "class",
    "target",
}

POSITIVE_LABELS = {
    "1",
    "1.0",
    "cyberbullying",
    "cyber bullying",
    "bullying",
    "positive",
    "yes",
    "true",
}
NEGATIVE_LABELS = {
    "0",
    "0.0",
    "not cyberbullying",
    "non cyberbullying",
    "non-cyberbullying",
    "negative",
    "no",
    "false",
}


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Hindi/Hinglish RC3 against a local CyberbullyX-63K XLSX "
            "without storing raw text or using the dataset for training."
        )
    )
    parser.add_argument("--xlsx", type=Path, required=True)
    parser.add_argument("--per-label", type=int, default=2000)
    return parser.parse_args()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_frozen_candidate() -> dict[str, object]:
    if not CANDIDATE_MANIFEST_PATH.is_file():
        raise FileNotFoundError(
            "RC3 is not frozen. Run freeze_hindi_abusive_context_rc3 before "
            "opening or evaluating the external dataset."
        )
    manifest = json.loads(CANDIDATE_MANIFEST_PATH.read_text(encoding="utf-8"))
    if manifest.get("candidate") != "hindi-abusive-context-rc3":
        raise RuntimeError("Unexpected candidate manifest.")
    hashes = manifest.get("frozen_input_hashes", {})
    expected_service = hashes.get("service")
    expected_lexicon = hashes.get("lexicon")
    if not SERVICE_PATH.is_file() or sha256_file(SERVICE_PATH) != expected_service:
        raise RuntimeError(
            "The live RC3 service no longer matches the frozen candidate. "
            "Do not evaluate it as RC3."
        )
    if not LEXICON_PATH.is_file() or sha256_file(LEXICON_PATH) != expected_lexicon:
        raise RuntimeError(
            "The live RC3 lexicon no longer matches the frozen candidate. "
            "Do not evaluate it as RC3."
        )
    return manifest


def normalize_header(value: object) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value or "").casefold())


def column_number(reference: str) -> int:
    letters = re.match(r"[A-Za-z]+", reference or "")
    if not letters:
        return 0
    value = 0
    for character in letters.group(0).upper():
        value = value * 26 + (ord(character) - ord("A") + 1)
    return value - 1


def read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    path = "xl/sharedStrings.xml"
    if path not in archive.namelist():
        return []
    root = ET.fromstring(archive.read(path))
    output: list[str] = []
    for item in root.findall(f"{XLSX_NAMESPACE}si"):
        fragments = [
            node.text or "" for node in item.iter(f"{XLSX_NAMESPACE}t")
        ]
        output.append("".join(fragments))
    return output


def worksheet_paths(archive: zipfile.ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(archive.read("xl/workbook.xml"))
    relationships = ET.fromstring(
        archive.read("xl/_rels/workbook.xml.rels")
    )
    relationship_targets = {
        relation.attrib["Id"]: relation.attrib["Target"]
        for relation in relationships.findall(
            f"{PACKAGE_REL_NAMESPACE}Relationship"
        )
    }
    output: list[tuple[str, str]] = []
    for sheet in workbook.iter(f"{XLSX_NAMESPACE}sheet"):
        relationship_id = sheet.attrib.get(f"{REL_NAMESPACE}id", "")
        target = relationship_targets.get(relationship_id, "")
        if not target:
            continue
        if target.startswith("/"):
            path = target.lstrip("/")
        elif target.startswith("xl/"):
            path = target
        else:
            path = f"xl/{target.lstrip('./')}"
        output.append((sheet.attrib.get("name", "Sheet"), path))
    return output


def cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    cell_type = cell.attrib.get("t", "")
    if cell_type == "inlineStr":
        return "".join(
            node.text or "" for node in cell.iter(f"{XLSX_NAMESPACE}t")
        )
    value_node = cell.find(f"{XLSX_NAMESPACE}v")
    if value_node is None or value_node.text is None:
        return ""
    value = value_node.text
    if cell_type == "s":
        try:
            return shared_strings[int(value)]
        except (IndexError, ValueError):
            return ""
    if cell_type == "b":
        return "1" if value == "1" else "0"
    return value


def worksheet_rows(
    archive: zipfile.ZipFile,
    worksheet_path: str,
    shared_strings: list[str],
) -> Iterator[list[str]]:
    with archive.open(worksheet_path) as handle:
        for _, element in ET.iterparse(handle, events=("end",)):
            if element.tag != f"{XLSX_NAMESPACE}row":
                continue
            values: dict[int, str] = {}
            for cell in element.findall(f"{XLSX_NAMESPACE}c"):
                index = column_number(cell.attrib.get("r", ""))
                values[index] = cell_value(cell, shared_strings)
            if values:
                maximum = max(values)
                yield [values.get(index, "") for index in range(maximum + 1)]
            element.clear()


def find_column(headers: list[str], candidates: set[str]) -> int | None:
    normalized = [normalize_header(value) for value in headers]
    for candidate in candidates:
        if candidate in normalized:
            return normalized.index(candidate)
    for index, value in enumerate(normalized):
        if any(candidate in value for candidate in candidates):
            return index
    return None


def extract_records(path: Path) -> tuple[list[tuple[str, str]], dict[str, object]]:
    with zipfile.ZipFile(path) as archive:
        shared_strings = read_shared_strings(archive)
        sheets = worksheet_paths(archive)
        diagnostics: list[dict[str, object]] = []

        for sheet_name, sheet_path in sheets:
            iterator = worksheet_rows(archive, sheet_path, shared_strings)
            headers: list[str] | None = None
            text_index: int | None = None
            label_index: int | None = None
            records: list[tuple[str, str]] = []

            for row in iterator:
                if headers is None:
                    candidate_text = find_column(row, TEXT_HEADER_CANDIDATES)
                    candidate_label = find_column(row, LABEL_HEADER_CANDIDATES)
                    if candidate_text is not None and candidate_label is not None:
                        headers = row
                        text_index = candidate_text
                        label_index = candidate_label
                    continue

                assert text_index is not None
                assert label_index is not None
                text = row[text_index].strip() if text_index < len(row) else ""
                label = row[label_index].strip() if label_index < len(row) else ""
                if text and label:
                    records.append((text, label))

            diagnostics.append(
                {
                    "sheet_name": sheet_name,
                    "headers": headers or [],
                    "records_found": len(records),
                }
            )
            if records and headers is not None:
                return records, {
                    "sheet_name": sheet_name,
                    "headers": headers,
                    "text_column": headers[text_index],
                    "label_column": headers[label_index],
                    "sheet_diagnostics": diagnostics,
                }

    raise ValueError(
        "No worksheet contained a recognizable text column and label column. "
        "Inspect the workbook headers before changing the evaluator."
    )


def normalize_label(value: str) -> int | None:
    normalized = re.sub(r"\s+", " ", str(value or "").strip().casefold())
    if normalized in POSITIVE_LABELS:
        return 1
    if normalized in NEGATIVE_LABELS:
        return 0
    return None


def sanitize_text(value: str) -> str:
    text = str(value or "")
    text = re.sub(r"https?://\S+|www\.\S+", "[URL]", text, flags=re.I)
    text = re.sub(r"(?<!\w)@[A-Za-z0-9_]{1,30}", "@USER", text)
    text = re.sub(
        r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b",
        "[EMAIL]",
        text,
        flags=re.I,
    )
    text = re.sub(r"(?<!\d)(?:\+?\d[\d ()-]{7,}\d)(?!\d)", "[PHONE]", text)
    return re.sub(r"\s+", " ", text).strip()


def metric_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def classification_metrics(counts: Counter[str]) -> dict[str, float | int]:
    tp = counts["tp"]
    tn = counts["tn"]
    fp = counts["fp"]
    fn = counts["fn"]
    total = tp + tn + fp + fn
    precision = metric_divide(tp, tp + fp)
    recall = metric_divide(tp, tp + fn)
    specificity = metric_divide(tn, tn + fp)
    f1 = metric_divide(2 * precision * recall, precision + recall)
    return {
        "records": total,
        "accuracy_percent": round(metric_divide(tp + tn, total) * 100, 2),
        "precision_percent": round(precision * 100, 2),
        "recall_percent": round(recall * 100, 2),
        "specificity_percent": round(specificity * 100, 2),
        "f1_percent": round(f1 * 100, 2),
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
    }


def update_counts(counts: Counter[str], expected: int, predicted: bool) -> None:
    if expected == 1 and predicted:
        counts["tp"] += 1
    elif expected == 0 and not predicted:
        counts["tn"] += 1
    elif expected == 0 and predicted:
        counts["fp"] += 1
    else:
        counts["fn"] += 1


def sample_records(
    records: list[tuple[str, str]],
    per_label: int,
) -> tuple[list[tuple[str, int, str]], Counter[str]]:
    pools: dict[int, dict[str, str]] = {0: {}, 1: {}}
    audit: Counter[str] = Counter()
    for raw_text, raw_label in records:
        label = normalize_label(raw_label)
        if label is None:
            audit["invalid_labels"] += 1
            continue
        text = sanitize_text(raw_text)
        if not text:
            audit["empty_after_sanitization"] += 1
            continue
        digest = hashlib.sha256(text.casefold().encode("utf-8")).hexdigest()
        pools[label].setdefault(digest, text)

    selected: list[tuple[str, int, str]] = []
    for label in (0, 1):
        ordered = sorted(pools[label].items())
        if len(ordered) < per_label:
            raise ValueError(
                f"Only {len(ordered)} unique records were available for label {label}; "
                f"requested {per_label}."
            )
        selected.extend((digest, label, text) for digest, text in ordered[:per_label])
        audit[f"unique_label_{label}"] = len(ordered)
        audit[f"selected_label_{label}"] = per_label
    selected.sort(key=lambda item: item[0])
    return selected, audit


def main() -> None:
    args = parse_arguments()
    candidate_manifest = verify_frozen_candidate()
    path = args.xlsx.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(
            f"CyberbullyX-63K.xlsx was not found: {path}\n"
            f"Download Version 1 from {DATASET_PAGE} and keep it outside the repository."
        )
    if path.suffix.casefold() != ".xlsx":
        raise ValueError("The input must be the original .xlsx file.")
    if args.per_label < 1:
        raise ValueError("--per-label must be at least 1.")

    print("Reading the external XLSX without saving raw records...")
    records, workbook_info = extract_records(path)
    selected, sample_audit = sample_records(records, args.per_label)

    strict_counts: Counter[str] = Counter()
    broad_counts: Counter[str] = Counter()
    predicted_categories: Counter[str] = Counter()
    contract_failures = 0
    bc_mc_safe_records = 0
    bc_mc_safe_false_positives = 0

    for index, (_, expected, text) in enumerate(selected, start=1):
        result = analyze_hindi_abusive_context(text)
        category = result["primary_category"] if result["detected"] else "No boundary override"
        predicted_categories[category] += 1

        strict_positive = category == CYBER_CATEGORY
        broad_positive = category in {CYBER_CATEGORY, ABUSIVE_CATEGORY}
        update_counts(strict_counts, expected, strict_positive)
        update_counts(broad_counts, expected, broad_positive)

        if result.get("automatic_enforcement_allowed") is not False:
            contract_failures += 1
        if expected == 0 and re.search(r"(?<!\w)(?:bc|mc)(?!\w)", text, re.I):
            bc_mc_safe_records += 1
            if broad_positive:
                bc_mc_safe_false_positives += 1

        if index % 500 == 0 or index == len(selected):
            print(f"Processed {index}/{len(selected)}")

    strict_metrics = classification_metrics(strict_counts)
    broad_metrics = classification_metrics(broad_counts)
    report = {
        "benchmark": "CyberbullyX-63K external evaluation-only sample",
        "candidate": candidate_manifest.get("candidate"),
        "candidate_frozen_at_utc": candidate_manifest.get("frozen_at_utc"),
        "dataset_id": DATASET_ID,
        "dataset_version": DATASET_VERSION,
        "dataset_doi": DATASET_DOI,
        "dataset_page": DATASET_PAGE,
        "dataset_license": "CC BY 4.0",
        "usage_restriction_observed": "academic and non-commercial research purposes",
        "source_file_name": path.name,
        "source_sha256": sha256_file(path),
        "evaluated_at_utc": datetime.now(timezone.utc).isoformat(),
        "workbook": workbook_info,
        "raw_rows_read": len(records),
        "sample_audit": dict(sample_audit),
        "records_evaluated": len(selected),
        "strict_cyberbullying_category_metrics": strict_metrics,
        "broad_harmful_language_signal_metrics": broad_metrics,
        "predicted_category_counts": dict(predicted_categories),
        "bc_mc_safe_records": bc_mc_safe_records,
        "bc_mc_safe_false_positives": bc_mc_safe_false_positives,
        "automatic_enforcement_contract_failures": contract_failures,
        "raw_text_stored": False,
        "record_level_predictions_stored": False,
        "used_for_training": False,
        "connected_to_live_moderation": False,
        "interpretation": (
            "This measures agreement with the dataset's binary labels. Strict metrics "
            "count only Cyberbullying & Harassment as positive. Broad metrics count "
            "Cyberbullying & Harassment or Abusive Words as harmful-language evidence."
        ),
        "readiness_gate": {
            "minimum_strict_accuracy_percent": 85.0,
            "minimum_strict_f1_percent": 85.0,
            "minimum_strict_specificity_percent": 85.0,
            "passed": bool(
                strict_metrics["accuracy_percent"] >= 85.0
                and strict_metrics["f1_percent"] >= 85.0
                and strict_metrics["specificity_percent"] >= 85.0
                and contract_failures == 0
            ),
        },
    }

    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print()
    print("CYBERBULLYX-63K HINDI/HINGLISH RC3 EXTERNAL EVALUATION")
    print("=" * 60)
    print(f"Records evaluated: {len(selected):,}")
    print(f"Label 0 records: {sample_audit['selected_label_0']:,}")
    print(f"Label 1 records: {sample_audit['selected_label_1']:,}")
    print()
    print("STRICT CYBERBULLYING CATEGORY")
    print("-" * 60)
    for key, value in strict_metrics.items():
        print(f"{key}: {value}")
    print()
    print("BROAD HARMFUL-LANGUAGE SIGNAL")
    print("-" * 60)
    for key, value in broad_metrics.items():
        print(f"{key}: {value}")
    print()
    print(f"BC/MC safe-label records: {bc_mc_safe_records}")
    print(f"BC/MC safe-label false positives: {bc_mc_safe_false_positives}")
    print(f"Automatic-enforcement contract failures: {contract_failures}")
    print(f"Passed strict 85% readiness gate: {report['readiness_gate']['passed']}")
    print(f"Report: {REPORT_PATH}")
    print("Raw text stored: False")
    print("Used for training: False")
    print("Connected to live moderation: False")
    print("This is external label agreement, not proven real-world accuracy.")


if __name__ == "__main__":
    main()
