from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests


DATASET_URL = (
    "https://raw.githubusercontent.com/"
    "hate-alert/HateXplain/master/"
    "Data/dataset.json"
)

SPLIT_URL = (
    "https://raw.githubusercontent.com/"
    "hate-alert/HateXplain/master/"
    "Data/post_id_divisions.json"
)

SOURCE_PAGE = (
    "https://github.com/"
    "hate-alert/HateXplain"
)

SOURCE_NAME = "HateXplain"

LICENSE_NAME = "MIT"

PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

OUTPUT_DIRECTORY = (
    PROJECT_ROOT
    / "datasets"
    / "public"
    / "hatexplain"
)

MANIFEST_PATH = (
    OUTPUT_DIRECTORY
    / "manifest.json"
)


LABEL_MAPPING = {
    "hate": (
        "Hate Speech & Discrimination"
    ),
    "hatespeech": (
        "Hate Speech & Discrimination"
    ),
    "hate speech": (
        "Hate Speech & Discrimination"
    ),
    "offensive": "Abusive Words",
    "normal": "Normal/Ignore",
}


SPLIT_NAME_MAPPING = {
    "train": "train",
    "val": "validation",
    "validation": "validation",
    "test": "test",
}


def download_json(
    url: str,
    description: str,
) -> tuple[
    Any,
    bytes,
]:
    print(
        f"Downloading {description}..."
    )

    response = requests.get(
        url,
        timeout=180,
        headers={
            "User-Agent": (
                "TrustScope public dataset "
                "importer/1.0"
            )
        },
    )

    response.raise_for_status()

    content = response.content

    print(
        f"Downloaded "
        f"{len(content):,} bytes."
    )

    return (
        response.json(),
        content,
    )


def normalize_label(
    label: str,
) -> str:
    return " ".join(
        str(label)
        .strip()
        .lower()
        .replace("_", " ")
        .split()
    )


def normalize_text(
    tokens: Any,
) -> str:
    if isinstance(
        tokens,
        list,
    ):
        text = " ".join(
            str(token)
            for token in tokens
        )

    else:
        text = str(
            tokens or ""
        )

    return " ".join(
        text.replace(
            "\x00",
            " ",
        ).split()
    )


def create_record_id(
    source_id: str,
    text: str,
) -> str:
    digest = hashlib.sha256(
        (
            f"{SOURCE_NAME}|"
            f"{source_id}|"
            f"{text}"
        ).encode("utf-8")
    ).hexdigest()

    return (
        f"hatexplain_"
        f"{digest[:20]}"
    )


def majority_annotation(
    annotators: Any,
) -> tuple[
    str | None,
    list[str],
    list[str],
]:
    if not isinstance(
        annotators,
        list,
    ):
        return None, [], []

    labels: list[str] = []
    targets: list[str] = []

    for annotation in annotators:
        if not isinstance(
            annotation,
            dict,
        ):
            continue

        label = normalize_label(
            annotation.get(
                "label",
                "",
            )
        )

        if label in LABEL_MAPPING:
            labels.append(label)

        annotation_targets = (
            annotation.get(
                "target",
                [],
            )
        )

        if isinstance(
            annotation_targets,
            list,
        ):
            targets.extend(
                str(target).strip()
                for target
                in annotation_targets
                if str(target).strip()
            )

    if not labels:
        return None, [], []

    counts = Counter(
        labels
    )

    ordered_counts = (
        counts.most_common()
    )

    if (
        len(ordered_counts) > 1
        and ordered_counts[0][1]
        == ordered_counts[1][1]
    ):
        return (
            None,
            labels,
            sorted(set(targets)),
        )

    majority_label = (
        ordered_counts[0][0]
    )

    return (
        majority_label,
        labels,
        sorted(set(targets)),
    )


def build_split_lookup(
    split_data: Any,
) -> dict[str, str]:
    if not isinstance(
        split_data,
        dict,
    ):
        raise RuntimeError(
            "The official split file has "
            "an invalid structure."
        )

    lookup: dict[
        str,
        str,
    ] = {}

    for original_name, identifiers in (
        split_data.items()
    ):
        normalized_name = (
            SPLIT_NAME_MAPPING.get(
                str(original_name)
                .strip()
                .lower()
            )
        )

        if normalized_name is None:
            continue

        if not isinstance(
            identifiers,
            list,
        ):
            continue

        for identifier in identifiers:
            lookup[
                str(identifier)
            ] = normalized_name

    return lookup


def parse_records(
    dataset: Any,
    split_lookup: dict[str, str],
) -> tuple[
    dict[str, list[dict[str, str]]],
    dict[str, int],
]:
    if not isinstance(
        dataset,
        dict,
    ):
        raise RuntimeError(
            "The HateXplain dataset has "
            "an invalid structure."
        )

    split_records: dict[
        str,
        list[dict[str, str]],
    ] = {
        "train": [],
        "validation": [],
        "test": [],
    }

    statistics = {
        "source_records": 0,
        "accepted_records": 0,
        "missing_split": 0,
        "empty_text": 0,
        "invalid_annotations": 0,
        "annotation_ties": 0,
        "duplicates_removed": 0,
    }

    seen_texts: set[str] = set()

    for source_id, item in (
        dataset.items()
    ):
        statistics[
            "source_records"
        ] += 1

        if not isinstance(
            item,
            dict,
        ):
            statistics[
                "invalid_annotations"
            ] += 1
            continue

        split_name = (
            split_lookup.get(
                str(source_id)
            )
        )

        if split_name is None:
            statistics[
                "missing_split"
            ] += 1
            continue

        text = normalize_text(
            item.get(
                "post_tokens",
                [],
            )
        )

        if not text:
            statistics[
                "empty_text"
            ] += 1
            continue

        (
            majority_label,
            annotation_labels,
            targets,
        ) = majority_annotation(
            item.get(
                "annotators",
                [],
            )
        )

        if majority_label is None:
            if annotation_labels:
                statistics[
                    "annotation_ties"
                ] += 1

            else:
                statistics[
                    "invalid_annotations"
                ] += 1

            continue

        duplicate_key = (
            text.casefold()
        )

        if duplicate_key in seen_texts:
            statistics[
                "duplicates_removed"
            ] += 1
            continue

        seen_texts.add(
            duplicate_key
        )

        category = LABEL_MAPPING[
            majority_label
        ]

        record = {
            "record_id": (
                create_record_id(
                    str(source_id),
                    text,
                )
            ),
            "source_record_id": (
                str(source_id)
            ),
            "text": text,
            "category": category,
            "original_label": (
                majority_label
            ),
            "annotator_labels": (
                json.dumps(
                    annotation_labels,
                    ensure_ascii=False,
                )
            ),
            "target_groups": (
                json.dumps(
                    targets,
                    ensure_ascii=False,
                )
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
            "split": split_name,
        }

        split_records[
            split_name
        ].append(record)

        statistics[
            "accepted_records"
        ] += 1

    return (
        split_records,
        statistics,
    )


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
        "source_record_id",
        "text",
        "category",
        "original_label",
        "annotator_labels",
        "target_groups",
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

        writer.writerows(
            records
        )

    return output_path


def category_counts(
    records: list[dict[str, str]],
) -> dict[str, int]:
    return dict(
        sorted(
            Counter(
                record["category"]
                for record in records
            ).items()
        )
    )


def main() -> None:
    OUTPUT_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    (
        dataset,
        dataset_bytes,
    ) = download_json(
        DATASET_URL,
        "HateXplain records",
    )

    (
        split_data,
        split_bytes,
    ) = download_json(
        SPLIT_URL,
        "official HateXplain splits",
    )

    split_lookup = (
        build_split_lookup(
            split_data
        )
    )

    (
        split_records,
        statistics,
    ) = parse_records(
        dataset,
        split_lookup,
    )

    output_files: dict[
        str,
        str,
    ] = {}

    print()
    print("=" * 60)
    print("HATEXPLAIN IMPORT RESULTS")
    print("=" * 60)

    for split_name, records in (
        split_records.items()
    ):
        output_path = write_split(
            split_name,
            records,
        )

        output_files[
            split_name
        ] = str(output_path)

        print()
        print(
            f"{split_name.title()}: "
            f"{len(records):,}"
        )

        for category, count in (
            category_counts(
                records
            ).items()
        ):
            print(
                f"  {category}: "
                f"{count:,}"
            )

        print(
            f"  Saved: {output_path}"
        )

    manifest = {
        "dataset_name": (
            SOURCE_NAME
        ),
        "source_page": (
            SOURCE_PAGE
        ),
        "dataset_url": (
            DATASET_URL
        ),
        "split_url": (
            SPLIT_URL
        ),
        "license": (
            LICENSE_NAME
        ),
        "downloaded_at_utc": (
            datetime.now(
                timezone.utc
            ).isoformat()
        ),
        "dataset_sha256": (
            hashlib.sha256(
                dataset_bytes
            ).hexdigest()
        ),
        "split_sha256": (
            hashlib.sha256(
                split_bytes
            ).hexdigest()
        ),
        "label_mapping": (
            LABEL_MAPPING
        ),
        "statistics": (
            statistics
        ),
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
                "path": output_files[
                    split_name
                ],
            }
            for split_name, records
            in split_records.items()
        },
        "important_rules": [
            (
                "The official test split must "
                "never be used for training, "
                "threshold selection, RAG, or "
                "prompt construction."
            ),
            (
                "The validation split may be "
                "used for threshold selection "
                "and confidence calibration."
            ),
            (
                "HateXplain offensive labels "
                "are mapped only to Abusive "
                "Words, not automatically to "
                "cyberbullying or sexual "
                "harassment."
            ),
            (
                "The dataset contains offensive "
                "and hateful language and should "
                "not be displayed unnecessarily."
            ),
        ],
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

    print()
    print("Import statistics:")

    for name, value in (
        statistics.items()
    ):
        print(
            f"  {name}: {value:,}"
        )

    print()
    print(
        f"Manifest saved: "
        f"{MANIFEST_PATH}"
    )

    print()
    print(
        "Warning: this dataset contains "
        "offensive and hateful language."
    )

    print(
        "Never add test.csv to training "
        "or the RAG index."
    )


if __name__ == "__main__":
    main()