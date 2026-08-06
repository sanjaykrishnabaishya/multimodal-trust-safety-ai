import csv
import json
import sys
from pathlib import Path

import numpy as np
from sentence_transformers import (
    SentenceTransformer,
)


MODEL_NAME = (
    "sentence-transformers/"
    "all-MiniLM-L6-v2"
)

BACKEND_DIRECTORY = (
    Path(__file__)
    .resolve()
    .parents[1]
)

PROJECT_ROOT = (
    BACKEND_DIRECTORY.parent
)

sys.path.insert(
    0,
    str(BACKEND_DIRECTORY),
)

from app.policy_config import (  # noqa: E402
    POLICY_VERSION,
    normalize_category_name,
)


DATASET_DIR = (
    PROJECT_ROOT
    / "datasets"
)

OUTPUT_DIR = (
    BACKEND_DIRECTORY
    / "storage"
    / "rag"
)

DATASET_FILES = [
    "text_dataset.csv",
    "document_dataset.csv",
    "image_dataset.csv",
    "video_dataset.csv",
    "policies.csv",
]

SEARCH_FIELDS = [
    "text",
    "document_title",
    "extracted_text",
    "embedded_image_description",
    "image_caption",
    "ocr_text",
    "visual_signals",
    "transcript",
    "frame_descriptions",
    "audio_description",
    "category",
    "severity",
    "action",
    "reason",
    "default_severity",
    "default_action",
    "moderation_conditions",
    "allow_conditions",
    "review_conditions",
    "notes",
    "policy_version",
]


def clean_value(
    value: object,
) -> str:
    if value is None:
        return ""

    return str(
        value
    ).strip()


def safely_normalize_category(
    value: object,
) -> str:
    category = clean_value(
        value
    )

    if not category:
        return ""

    try:
        return (
            normalize_category_name(
                category
            )
        )

    except (
        ValueError,
        KeyError,
    ):
        return category


def create_search_text(
    row: dict,
) -> str:
    sections: list[str] = []

    for field in SEARCH_FIELDS:
        if field == "category":
            value = (
                safely_normalize_category(
                    row.get(
                        field
                    )
                )
            )

        else:
            value = clean_value(
                row.get(
                    field
                )
            )

        if value:
            readable_name = (
                field
                .replace(
                    "_",
                    " ",
                )
                .title()
            )

            sections.append(
                f"{readable_name}: "
                f"{value}"
            )

    return "\n".join(
        sections
    )


def load_dataset_records() -> (
    list[dict]
):
    records: list[
        dict
    ] = []

    for file_name in (
        DATASET_FILES
    ):
        file_path = (
            DATASET_DIR
            / file_name
        )

        if not file_path.exists():
            raise FileNotFoundError(
                "Required dataset is "
                f"missing: {file_path}"
            )

        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(
                csv_file
            )

            for row_number, row in (
                enumerate(
                    reader,
                    start=1,
                )
            ):
                normalized_category = (
                    safely_normalize_category(
                        row.get(
                            "category"
                        )
                    )
                )

                normalized_row = dict(
                    row
                )

                normalized_row[
                    "category"
                ] = (
                    normalized_category
                )

                search_text = (
                    create_search_text(
                        normalized_row
                    )
                )

                if not search_text:
                    continue

                severity = (
                    clean_value(
                        row.get(
                            "severity"
                        )
                    )
                    or clean_value(
                        row.get(
                            "default_severity"
                        )
                    )
                )

                action = (
                    clean_value(
                        row.get(
                            "action"
                        )
                    )
                    or clean_value(
                        row.get(
                            "default_action"
                        )
                    )
                )

                reason = (
                    clean_value(
                        row.get(
                            "reason"
                        )
                    )
                    or clean_value(
                        row.get(
                            "moderation_conditions"
                        )
                    )
                    or clean_value(
                        row.get(
                            "notes"
                        )
                    )
                )

                content_type = (
                    clean_value(
                        row.get(
                            "content_type"
                        )
                    )
                )

                if not content_type:
                    content_type = (
                        "policy"
                        if file_name
                        == "policies.csv"
                        else "unknown"
                    )

                records.append(
                    {
                        "rag_id": (
                            f"{file_path.stem}-"
                            f"{row_number:04d}"
                        ),
                        "source_file": (
                            file_name
                        ),
                        "source_row": (
                            row_number
                        ),
                        "record_id": (
                            clean_value(
                                row.get(
                                    "id"
                                )
                            )
                        ),
                        "content_type": (
                            content_type
                        ),
                        "category": (
                            normalized_category
                        ),
                        "source_context": "",
                        "severity": severity,
                        "action": action,
                        "reason": reason,
                        "search_text": (
                            search_text
                        ),
                    }
                )

    return records


def validate_records(
    records: list[dict],
) -> None:
    if not records:
        raise ValueError(
            "No RAG records were "
            "created."
        )

    missing_categories = [
        record[
            "rag_id"
        ]
        for record in records
        if not record[
            "category"
        ]
    ]

    if missing_categories:
        preview = ", ".join(
            missing_categories[
                :10
            ]
        )

        raise ValueError(
            "RAG records are missing "
            "categories: "
            f"{preview}"
        )

    old_category_names = {
        "Child Abuse",
        "Spam",
        "Scam",
        "Harassment/Cyberbullying",
        "Hate Speech",
        "Fake News",
        "Violence",
        "Nudity",
    }

    remaining_old_records = [
        record[
            "rag_id"
        ]
        for record in records
        if record[
            "category"
        ]
        in old_category_names
    ]

    if remaining_old_records:
        raise ValueError(
            "Old category names remain "
            "in the RAG records."
        )


def build_manifest(
    *,
    records: list[dict],
    embeddings: np.ndarray,
) -> dict:
    category_counts: dict[
        str,
        int,
    ] = {}

    for record in records:
        category = record[
            "category"
        ]

        category_counts[
            category
        ] = (
            category_counts.get(
                category,
                0,
            )
            + 1
        )

    return {
        "model_name": MODEL_NAME,
        "record_count": len(
            records
        ),
        "embedding_dimensions": int(
            embeddings.shape[
                1
            ]
        ),
        "dataset_files": (
            DATASET_FILES
        ),
        "policy_version": (
            POLICY_VERSION
        ),
        "source_context_used": False,
        "category_counts": dict(
            sorted(
                category_counts.items()
            )
        ),
    }


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = (
        load_dataset_records()
    )

    validate_records(
        records
    )

    print(
        "Loading embedding model: "
        f"{MODEL_NAME}"
    )

    print(
        "The first run may download "
        "the model."
    )

    model = SentenceTransformer(
        MODEL_NAME
    )

    corpus = [
        record[
            "search_text"
        ]
        for record in records
    ]

    print(
        "Creating embeddings for "
        f"{len(corpus)} records..."
    )

    embeddings = model.encode(
        corpus,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(
        np.float32
    )

    if (
        embeddings.ndim != 2
        or embeddings.shape[
            0
        ] != len(records)
    ):
        raise ValueError(
            "The generated embedding "
            "shape is invalid."
        )

    np.save(
        OUTPUT_DIR
        / "embeddings.npy",
        embeddings,
    )

    with (
        OUTPUT_DIR
        / "records.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            records,
            output_file,
            ensure_ascii=False,
            indent=2,
        )

    manifest = build_manifest(
        records=records,
        embeddings=embeddings,
    )

    with (
        OUTPUT_DIR
        / "manifest.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            manifest,
            output_file,
            ensure_ascii=False,
            indent=2,
        )

    print()
    print(
        "RAG index created "
        "successfully."
    )

    print(
        "Output: "
        f"{OUTPUT_DIR}"
    )

    print(
        "Records: "
        f"{len(records)}"
    )

    print(
        "Embedding dimensions: "
        f"{embeddings.shape[1]}"
    )

    print(
        "Policy version: "
        f"{POLICY_VERSION}"
    )

    print(
        "Source context used: False"
    )

    print()
    print(
        "Category counts:"
    )

    for category, count in (
        manifest[
            "category_counts"
        ].items()
    ):
        print(
            f"  {category}: {count}"
        )


if __name__ == "__main__":
    main()