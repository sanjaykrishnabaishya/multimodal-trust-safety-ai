import json
from functools import lru_cache
from pathlib import Path

import numpy as np
from sentence_transformers import SentenceTransformer


MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
RAG_DIR = PROJECT_ROOT / "backend" / "storage" / "rag"

EMBEDDINGS_PATH = RAG_DIR / "embeddings.npy"
RECORDS_PATH = RAG_DIR / "records.json"
MANIFEST_PATH = RAG_DIR / "manifest.json"


class RAGProcessingError(Exception):
    pass


def rag_files_exist() -> bool:
    return all(
        path.exists()
        for path in [
            EMBEDDINGS_PATH,
            RECORDS_PATH,
            MANIFEST_PATH,
        ]
    )


@lru_cache(maxsize=1)
def get_rag_model() -> SentenceTransformer:
    try:
        return SentenceTransformer(MODEL_NAME)

    except Exception as exc:
        raise RAGProcessingError(
            "The embedding model could not be loaded."
        ) from exc


@lru_cache(maxsize=1)
def load_rag_index() -> tuple:
    if not rag_files_exist():
        raise RAGProcessingError(
            "The RAG index does not exist. Run "
            "'python scripts/build_rag_index.py' first."
        )

    try:
        embeddings = np.load(
            EMBEDDINGS_PATH,
            allow_pickle=False,
        )

        with RECORDS_PATH.open(
            "r",
            encoding="utf-8",
        ) as input_file:
            records = json.load(input_file)

        with MANIFEST_PATH.open(
            "r",
            encoding="utf-8",
        ) as input_file:
            manifest = json.load(input_file)

    except Exception as exc:
        raise RAGProcessingError(
            "The RAG index could not be loaded."
        ) from exc

    if len(records) != embeddings.shape[0]:
        raise RAGProcessingError(
            "The RAG records and embeddings "
            "have different sizes."
        )

    return embeddings, records, manifest


def get_rag_status() -> dict:
    status = {
        "available": rag_files_exist(),
        "engine": "sentence-transformers",
        "model": MODEL_NAME,
        "index_directory": str(RAG_DIR),
        "model_loaded": (
            get_rag_model.cache_info().currsize > 0
        ),
        "index_loaded": (
            load_rag_index.cache_info().currsize > 0
        ),
    }

    if rag_files_exist():
        try:
            _, _, manifest = load_rag_index()

            status.update(
                {
                    "record_count": manifest[
                        "record_count"
                    ],
                    "embedding_dimensions": manifest[
                        "embedding_dimensions"
                    ],
                    "dataset_files": manifest[
                        "dataset_files"
                    ],
                }
            )

        except RAGProcessingError as exc:
            status["available"] = False
            status["error"] = str(exc)

    else:
        status["error"] = (
            "RAG index files are missing."
        )

    return status


def retrieve_evidence(
    query: str,
    top_k: int = 5,
) -> list[dict]:
    cleaned_query = query.strip()

    if not cleaned_query:
        return []

    embeddings, records, _ = load_rag_index()
    model = get_rag_model()

    query_embedding = model.encode(
        [cleaned_query],
        convert_to_numpy=True,
        normalize_embeddings=True,
    )[0].astype(np.float32)

    similarity_scores = embeddings @ query_embedding

    result_count = min(
        top_k,
        len(records),
    )

    best_indices = np.argsort(
        similarity_scores
    )[::-1][:result_count]

    results: list[dict] = []

    for rank, index in enumerate(
        best_indices,
        start=1,
    ):
        record = records[int(index)]

        results.append(
            {
                "rank": rank,
                "similarity": round(
                    float(similarity_scores[index]),
                    4,
                ),
                "rag_id": record["rag_id"],
                "source_file": record["source_file"],
                "source_row": record["source_row"],
                "record_id": record["record_id"],
                "content_type": record[
                    "content_type"
                ],
                "category": record["category"],
                "source_context": record[
                    "source_context"
                ],
                "severity": record["severity"],
                "action": record["action"],
                "reason": record["reason"],
                "text_preview": record[
                    "search_text"
                ][:500],
            }
        )

    return results