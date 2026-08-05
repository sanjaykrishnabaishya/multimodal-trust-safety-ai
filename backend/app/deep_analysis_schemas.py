from typing import Any, Literal

from pydantic import BaseModel, Field


ContentType = Literal[
    "text",
    "document",
    "image",
    "video",
]


class DeepAnalysisTextRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=100_000,
    )


class SceneSummary(BaseModel):
    timestamp_seconds: float = Field(
        ge=0.0,
    )
    summary: str


class FactCheckSuggestion(BaseModel):
    claim: str
    suggestion: str
    priority: Literal[
        "Low",
        "Medium",
        "High",
    ] = "Medium"


class ContentSize(BaseModel):
    size_bytes: int = Field(
        ge=0,
    )
    character_count: int = Field(
        ge=0,
    )
    word_count: int = Field(
        ge=0,
    )


class DeepAnalysisResponse(BaseModel):
    content_type: ContentType
    file_name: str | None = None

    summary: str

    scene_by_scene_summary: list[
        SceneSummary
    ] = Field(
        default_factory=list,
    )

    exact_ocr_text: str = ""

    content_size: ContentSize

    media_duration_seconds: (
        float | None
    ) = None

    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    fact_check_suggestions: list[
        FactCheckSuggestion
    ] = Field(
        default_factory=list,
    )

    suggested_next_step: str

    analysis_status: dict[
        str,
        str,
    ] = Field(
        default_factory=dict,
    )

    extraction_metadata: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    warnings: list[str] = Field(
        default_factory=list,
    )