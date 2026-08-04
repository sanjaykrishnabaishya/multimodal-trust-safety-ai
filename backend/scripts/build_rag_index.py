import csv
import json
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "datasets"
OUTPUT_DIR = PROJECT_ROOT / "backend" / "storage" / "rag"

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
    "source_context",
    "source_type",
    "severity",
    "action",
    "reason",
    "default_severity",
    "default_action",
    "notes",
]


def clean_value(value: object) -> str:
    if value is None:
        return ""

    return str(value).strip()


def create_search_text(row: dict) -> str:
    sections: list[str] = []

    for field in SEARCH_FIELDS:
        value = clean_value(row.get(field))

        if value:
            readable_name = field.replace("_", " ").title()
            sections.append(
                f"{readable_name}: {value}"
            )

    return "\n".join(sections)


def load_dataset_records() -> list[dict]:
    records: list[dict] = []

    for file_name in DATASET_FILES:
        file_path = DATASET_DIR / file_name

        if not file_path.exists():
            raise FileNotFoundError(
                f"Required dataset is missing: {file_path}"
            )

        with file_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as csv_file:
            reader = csv.DictReader(csv_file)

            for row_number, row in enumerate(
                reader,
                start=1,
            ):
                search_text = create_search_text(row)

                if not search_text:
                    continue

                records.append(
                    {
                        "rag_id": (
                            f"{file_path.stem}-"
                            f"{row_number:04d}"
                        ),
                        "source_file": file_name,
                        "source_row": row_number,
                        "record_id": clean_value(
                            row.get("id")
                        ),
                        "content_type": clean_value(
                            row.get("content_type")
                        )
                        or (
                            "policy"
                            if file_name == "policies.csv"
                            else "unknown"
                        ),
                        "category": clean_value(
                            row.get("category")
                        ),
                        "source_context": clean_value(
                            row.get("source_context")
                        ),
                        "severity": (
                            clean_value(row.get("severity"))
                            or clean_value(
                                row.get("default_severity")
                            )
                        ),
                        "action": (
                            clean_value(row.get("action"))
                            or clean_value(
                                row.get("default_action")
                            )
                        ),
                        "reason": (
                            clean_value(row.get("reason"))
                            or clean_value(row.get("notes"))
                        ),
                        "search_text": search_text,
                    }
                )

    return records


def main() -> None:
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    records = load_dataset_records()

    if not records:
        raise ValueError(
            "No RAG records were created."
        )

    print(f"Loading embedding model: {MODEL_NAME}")
    print(
        "The first run downloads the model. "
        "This can take several minutes."
    )

    model = SentenceTransformer(MODEL_NAME)

    corpus = [
        record["search_text"]
        for record in records
    ]

    print(
        f"Creating embeddings for "
        f"{len(corpus)} records..."
    )

    embeddings = model.encode(
        corpus,
        batch_size=32,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True,
    ).astype(np.float32)

    np.save(
        OUTPUT_DIR / "embeddings.npy",
        embeddings,
    )

    with (
        OUTPUT_DIR / "records.json"
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

    manifest = {
        "model_name": MODEL_NAME,
        "record_count": len(records),
        "embedding_dimensions": int(
            embeddings.shape[1]
        ),
        "dataset_files": DATASET_FILES,
    }

    with (
        OUTPUT_DIR / "manifest.json"
    ).open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            manifest,
            output_file,
            indent=2,
        )

    print("RAG index created successfully.")
    print(f"Output: {OUTPUT_DIR}")
    print(f"Records: {len(records)}")
    print(
        f"Embedding dimensions: "
        f"{embeddings.shape[1]}"
    )


if __name__ == "__main__":
    main()