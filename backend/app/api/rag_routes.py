from fastapi import APIRouter, HTTPException

from app.rag_schemas import (
    RAGSearchRequest,
    RAGSearchResponse,
)
from app.services.rag_service import (
    MODEL_NAME,
    RAGProcessingError,
    get_rag_status,
    load_rag_index,
    retrieve_evidence,
)


router = APIRouter(
    prefix="/rag",
    tags=["RAG"],
)


@router.get("/health")
def rag_health() -> dict:
    status = get_rag_status()

    if not status["available"]:
        raise HTTPException(
            status_code=503,
            detail=status,
        )

    return status


@router.post(
    "/search",
    response_model=RAGSearchResponse,
)
def rag_search(
    request: RAGSearchRequest,
) -> RAGSearchResponse:
    try:
        _, _, manifest = load_rag_index()

        results = retrieve_evidence(
            query=request.query,
            top_k=request.top_k,
        )

    except RAGProcessingError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc

    return RAGSearchResponse(
        query=request.query,
        model_name=MODEL_NAME,
        index_record_count=manifest[
            "record_count"
        ],
        results=results,
    )