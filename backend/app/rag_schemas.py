from pydantic import BaseModel, Field


class RAGSearchRequest(BaseModel):
    query: str = Field(
        min_length=1,
        max_length=100_000,
    )
    top_k: int = Field(
        default=5,
        ge=1,
        le=10,
    )


class RetrievedEvidence(BaseModel):
    rank: int
    similarity: float
    rag_id: str
    source_file: str
    source_row: int
    record_id: str
    content_type: str
    category: str
    source_context: str
    severity: str
    action: str
    reason: str
    text_preview: str


class RAGSearchResponse(BaseModel):
    query: str
    model_name: str
    index_record_count: int
    results: list[RetrievedEvidence]