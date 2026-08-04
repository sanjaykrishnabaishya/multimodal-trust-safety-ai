from typing import Any, Literal

from pydantic import BaseModel, Field


ContentType = Literal["text", "document", "image", "video"]


class TextExtractionRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=100_000,
        description="Plain text to prepare for moderation.",
    )
    source_context: str = Field(
        default="user",
        max_length=100,
        description="Examples: user, news, education, art, medical, gaming.",
    )


class ExtractionResponse(BaseModel):
    content_type: ContentType
    file_name: str | None = None
    file_extension: str | None = None
    media_type: str | None = None
    file_size_bytes: int | None = None

    extracted_text: str = ""
    visual_description: str = ""
    audio_transcript: str = ""
    ocr_text: str = ""

    source_context: str = "user"
    metadata: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)