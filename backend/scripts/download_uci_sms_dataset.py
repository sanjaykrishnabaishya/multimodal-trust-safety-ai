from __future__ import annotations

import csv
import hashlib
import io
import json
import random
import zipfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import requests
from sklearn.model_selection import (
    train_test_split,
)


DATASET_URL = (
    "https://archive.ics.uci.edu/"
    "static/public/228/"
    "sms+spam+collection.zip"
)

SOURCE_NAME = "UCI SMS Spam Collection"

SOURCE_PAGE = (
    "https://archive.ics.uci.edu/"
    "dataset/228/"
    "sms+spam+collection"
)

LICENSE_NAME = "CC BY 4.0"

RANDOM_SEED = 42

TRAIN_SIZE = 0.70
VALIDATION_SIZE = 0.15
TEST_SIZE = 0.15

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "uci_sms"
)

MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "manifest.json"
)


CATEGORY_MAPPING = {
    "ham": "Normal/Ignore",
    "spam": "Spam, Scam & Phishing",
}


def create_record_id(
    original_label: str,
    text: str,
) -> str:
    value = (
        f"{SOURCE_NAME}|"
        f"{original_label}|"
        f"{text}"
    )

    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()

    return f"uci_sms_{digest[:20]}"


def download_dataset() -> bytes:
    print(
        "Downloading the UCI SMS "
        "Spam Collection..."
    )

    response = requests.get(
        DATASET_URL,
        timeout=120,
        headers={
            "User-Agent": (
                "TrustScope research dataset "
                "importer/1.0"
            )
        },
    )

    response.raise_for_status()

    print(
        "Download completed: "
        f"{len(response.content):,} bytes"
    )

    return response.content


def extract_source_text(
    archive_bytes: bytes,
) -> str:
    with zipfile.ZipFile(
        io.BytesIO(archive_bytes)
    ) as archive:
        possible_names = [
            name
            for name in archive.namelist()
            if (
                name.lower().endswith(
                    "smsspamcollection"
                )
                or (
                    "smsspamcollection"
                    in name.lower()
                )
            )
        ]

        if not possible_names:
            raise RuntimeError(
                "SMS Spam Collection file "
                "was not found in the archive."
            )

        source_name = possible_names[0]

        with archive.open(
            source_name
        ) as source_file:
            source_bytes = (
                source_file.read()
            )

    for encoding in (
        "utf-8",
        "utf-8-sig",
        "latin-1",
    ):
        try:
            return source_bytes.decode(
                encoding
            )

        except UnicodeDecodeError:
            continue

    raise RuntimeError(
        "The source dataset encoding "
        "could not be detected."
    )


def normalize_text(
    value: str,
) -> str:
    return " ".join(
        value.replace(
            "\x00",
            " ",
        ).split()
    )


def parse_records(
    source_text: str,
) -> tuple[
    list[dict[str, str]],
    int,
]:
    records: list[
        dict[str, str]
    ] = []

    duplicate_count = 0

    seen_texts: set[str] = set()

    for line_number, line in enumerate(
        source_text.splitlines(),
        start=1,
    ):
        if not line.strip():
            continue

        parts = line.split(
            "\t",
            maxsplit=1,
        )

        if len(parts) != 2:
            print(
                "Skipping malformed line "
                f"{line_number}."
            )
            continue

        original_label = (
            parts[0]
            .strip()
            .lower()
        )

        text = normalize_text(
            parts[1]
        )

        if (
            original_label
            not in CATEGORY_MAPPING
        ):
            print(
                "Skipping unknown label "
                f"on line {line_number}: "
                f"{original_label}"
            )
            continue

        if not text:
            continue

        duplicate_key = (
            text.casefold()
        )

        if duplicate_key in seen_texts:
            duplicate_count += 1
            continue

        seen_texts.add(
            duplicate_key
        )

        records.append(
            {
                "record_id": (
                    create_record_id(
                        original_label,
                        text,
                    )
                ),
                "text": text,
                "category": (
                    CATEGORY_MAPPING[
                        original_label
                    ]
                ),
                "original_label": (
                    original_label
                ),
                "content_type": "text",
                "language": "english",
                "source_dataset": (
                    SOURCE_NAME
                ),
                "source_url": (
                    SOURCE_PAGE
                ),
                "license": (
                    LICENSE_NAME
                ),
            }
        )

    return records, duplicate_count


def split_records(
    records: list[dict[str, str]],
) -> dict[
    str,
    list[dict[str, str]],
]:
    labels = [
        record["original_label"]
        for record in records
    ]

    train_records, temporary_records = (
        train_test_split(
            records,
            test_size=(
                1.0 - TRAIN_SIZE
            ),
            random_state=RANDOM_SEED,
            stratify=labels,
        )
    )

    temporary_labels = [
        record["original_label"]
        for record in temporary_records
    ]

    relative_test_size = (
        TEST_SIZE
        / (
            VALIDATION_SIZE
            + TEST_SIZE
        )
    )

    validation_records, test_records = (
        train_test_split(
            temporary_records,
            test_size=(
                relative_test_size
            ),
            random_state=RANDOM_SEED,
            stratify=temporary_labels,
        )
    )

    split_data = {
        "train": train_records,
        "validation": (
            validation_records
        ),
        "test": test_records,
    }

    random_generator = random.Random(
        RANDOM_SEED
    )

    for split_records_list in (
        split_data.values()
    ):
        random_generator.shuffle(
            split_records_list
        )

    return split_data


def write_split(
    split_name: str,
    records: list[dict[str, str]],
) -> Path:
    output_path = (
        OUTPUT_DIRECTORY
        / f"{split_name}.csv"
    )

    fieldnames = [
        "record_id",
        "text",
        "category",
        "original_label",
        "content_type",
        "language",
        "source_dataset",
        "source_url",
        "license",
        "split",
    ]

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for record in records:
            output_record = dict(
                record
            )

            output_record["split"] = (
                split_name
            )

            writer.writerow(
                output_record
            )

    return output_path


def category_counts(
    records: list[dict[str, str]],
) -> dict[str, int]:
    counts = Counter(
        record["category"]
        for record in records
    )

    return dict(
        sorted(
            counts.items()
        )
    )


def write_manifest(
    *,
    archive_bytes: bytes,
    all_records: list[
        dict[str, str]
    ],
    split_data: dict[
        str,
        list[dict[str, str]],
    ],
    duplicate_count: int,
) -> None:
    manifest = {
        "dataset_name": (
            SOURCE_NAME
        ),
        "source_page": (
            SOURCE_PAGE
        ),
        "download_url": (
            DATASET_URL
        ),
        "license": (
            LICENSE_NAME
        ),
        "downloaded_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "archive_sha256": (
            hashlib.sha256(
                archive_bytes
            ).hexdigest()
        ),
        "random_seed": (
            RANDOM_SEED
        ),
        "duplicate_records_removed": (
            duplicate_count
        ),
        "accepted_records": len(
            all_records
        ),
        "category_mapping": (
            CATEGORY_MAPPING
        ),
        "split_policy": {
            "train_percent": 70,
            "validation_percent": 15,
            "test_percent": 15,
        },
        "important_rules": [
            (
                "The test split must never "
                "be used for training."
            ),
            (
                "The test split must never "
                "be added to the RAG index."
            ),
            (
                "The validation split may "
                "be used for thresholds and "
                "confidence calibration."
            ),
        ],
        "splits": {
            split_name: {
                "records": len(
                    records
                ),
                "category_counts": (
                    category_counts(
                        records
                    )
                ),
            }
            for split_name, records
            in split_data.items()
        },
    }

    with MANIFEST_PATH.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            manifest,
            output_file,
            indent=2,
            ensure_ascii=False,
        )


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    archive_bytes = (
        download_dataset()
    )

    source_text = (
        extract_source_text(
            archive_bytes
        )
    )

    records, duplicate_count = (
        parse_records(
            source_text
        )
    )

    if not records:
        raise RuntimeError(
            "No valid dataset records "
            "were imported."
        )

    split_data = split_records(
        records
    )

    print()
    print(
        f"Accepted unique records: "
        f"{len(records):,}"
    )

    print(
        f"Duplicate records removed: "
        f"{duplicate_count:,}"
    )

    print()

    for split_name, split_records_list in (
        split_data.items()
    ):
        output_path = write_split(
            split_name,
            split_records_list,
        )

        print(
            f"{split_name.title()}: "
            f"{len(split_records_list):,}"
        )

        for category, count in (
            category_counts(
                split_records_list
            ).items()
        ):
            print(
                f"  {category}: {count:,}"
            )

        print(
            f"  Saved: {output_path}"
        )

    write_manifest(
        archive_bytes=archive_bytes,
        all_records=records,
        split_data=split_data,
        duplicate_count=(
            duplicate_count
        ),
    )

    print()
    print(
        "Manifest saved: "
        f"{MANIFEST_PATH}"
    )

    print()
    print(
        "Important: do not add test.csv "
        "to training or the RAG index."
    )


if __name__ == "__main__":
    main()