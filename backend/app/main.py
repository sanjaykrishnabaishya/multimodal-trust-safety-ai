from fastapi import FastAPI

from app.api.moderation_routes import (
    router as moderation_router,
)
from app.api.rag_routes import (
    router as rag_router,
)
from app.api.routes import (
    router as extraction_router,
)
from app.moderation_schemas import (
    ModerationResponse,
    ModerationTextRequest,
)
from app.services.moderation_service import (
    moderate_text,
)


app = FastAPI(
    title="AI Trust & Safety API",
    description=(
        "Multimodal extraction, moderation, "
        "and policy-retrieval API."
    ),
    version="0.4.0",
)

app.include_router(extraction_router)
app.include_router(moderation_router)
app.include_router(rag_router)


@app.get("/")
def home() -> dict[str, str]:
    return {
        "message": (
            "AI Trust & Safety API is running."
        ),
        "documentation": "/docs",
        "version": "0.4.0",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
    }


@app.post(
    "/moderate",
    response_model=ModerationResponse,
    deprecated=True,
)
def legacy_moderate_content(
    request: ModerationTextRequest,
) -> ModerationResponse:
    decision = moderate_text(
        text=request.text,
        source_context=request.source_context,
    )

    return ModerationResponse(
        content_type="text",
        source_context=request.source_context,
        analyzed_text_preview=request.text[:500],
        **decision,
    )