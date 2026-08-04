from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel, Field

from app.api.routes import router as extraction_router


app = FastAPI(
    title="AI Trust & Safety API",
    description=(
        "Multimodal API for extracting and moderating "
        "text, documents, images, and videos."
    ),
    version="0.2.0",
)

app.include_router(extraction_router)


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


class ModerationRequest(BaseModel):
    text: str = Field(
        min_length=1,
        max_length=100_000,
        description="Content that needs to be moderated.",
    )
    source_type: str = Field(
        default="user",
        description="Examples: user, news, education, art, medical, gaming.",
    )


class ModerationResponse(BaseModel):
    text: str
    category: ModerationCategory
    confidence: float
    action: str
    human_review_required: bool
    reason: str


@app.get("/")
def home() -> dict[str, str]:
    return {
        "message": "AI Trust & Safety API is running.",
        "documentation": "/docs",
        "version": "0.2.0",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "healthy"}


@app.post("/moderate", response_model=ModerationResponse)
def moderate_content(
    request: ModerationRequest,
) -> ModerationResponse:
    return ModerationResponse(
        text=request.text,
        category="Normal/Ignore",
        confidence=0.50,
        action="Allow",
        human_review_required=True,
        reason=(
            "The final moderation model has not been connected yet. "
            "The content has been sent for human review."
        ),
    )