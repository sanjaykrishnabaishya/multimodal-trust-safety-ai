from typing import Any, Literal

from pydantic import BaseModel, Field


ModerationCategory = Literal[
    "Child Abuse",
    "Spam",
    "Scam",
    "Harassment/Cyberbullying",
    "Hate Speech",
    "Fake News",
    "Violence",
    "Nudity",
    "Normal/Ignore",
]

ContentType = Literal[
    "text",
    "document",
    "image",
    "video",
]


class ModerationTextRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=100_000,
    )
    source_context: str = Field(
        default="user",
        max_length=100,
    )


class ModerationResponse(BaseModel):
    content_type: ContentType
    file_name: str | None = None

    category: ModerationCategory
    severity: str
    action: str
    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )
    human_review_required: bool
    reason: str

    source_context: str
    matched_signals: list[str] = Field(
        default_factory=list
    )
    decision_sources: list[str] = Field(
        default_factory=list
    )

    rag_used: bool = False
    rag_consensus: dict[str, Any] = Field(
        default_factory=dict
    )
    retrieved_evidence: list[
        dict[str, Any]
    ] = Field(
        default_factory=list
    )

    analyzed_text_preview: str = ""
    extraction_metadata: dict[str, Any] = Field(
        default_factory=dict
    )
    warnings: list[str] = Field(
        default_factory=list
    )