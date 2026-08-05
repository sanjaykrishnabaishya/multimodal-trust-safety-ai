from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

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
from app.services.fusion_service import (
    fuse_moderation_decision,
)


app = FastAPI(
    title="AI Trust & Safety API",
    description=(
        "Multimodal extraction, moderation, "
        "policy retrieval, and decision-fusion API "
        "for text, documents, images, and videos."
    ),
    version="0.6.0",
)

ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
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
        "version": "0.6.0",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "version": "0.6.0",
    }


@app.post(
    "/moderate",
    response_model=ModerationResponse,
    deprecated=True,
)
def legacy_moderate_content(
    request: ModerationTextRequest,
) -> ModerationResponse:
    decision = fuse_moderation_decision(
        text=request.text,
        source_context=request.source_context,
        input_sources=["text"],
    )

    fusion_warnings = decision.pop(
        "fusion_warnings",
        [],
    )

    return ModerationResponse(
        content_type="text",
        source_context=request.source_context,
        analyzed_text_preview=(
            request.text[:500]
        ),
        warnings=fusion_warnings,
        **decision,
    )