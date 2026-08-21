from contextlib import (
    asynccontextmanager,
)

from fastapi import FastAPI
from fastapi.middleware.cors import (
    CORSMiddleware,
)

from app.api.deep_analysis_routes import (
    router as deep_analysis_router,
)
from app.api.moderation_routes import (
    router as moderation_router,
)
from app.api.rag_routes import (
    router as rag_router,
)
from app.api.review_routes import (
    router as review_router,
)
from app.api.routes import (
    router as extraction_router,
)
from app.moderation_schemas import (
    ModerationResponse,
    ModerationTextRequest,
)
from app.runtime_config import (
    get_allowed_origins,
    get_private_lan_origin_regex,
)
from app.services.fusion_service import (
    fuse_moderation_decision,
)
from app.services.review_database_service import (
    initialize_database,
)


@asynccontextmanager
async def application_lifespan(
    app: FastAPI,
):
    initialize_database()

    yield


app = FastAPI(
    title="AI Trust & Safety API",
    description=(
        "Multimodal extraction, moderation, "
        "policy retrieval, decision fusion, "
        "deep analysis, human review, and "
        "audit-history API."
    ),
    version="0.8.0",
    lifespan=application_lifespan,
)

ALLOWED_ORIGINS = get_allowed_origins()
ALLOWED_ORIGIN_REGEX = (
    get_private_lan_origin_regex()
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_origin_regex=(
        ALLOWED_ORIGIN_REGEX
    ),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(
    extraction_router
)

app.include_router(
    moderation_router
)

app.include_router(
    rag_router
)

app.include_router(
    deep_analysis_router
)

app.include_router(
    review_router
)


@app.get("/")
def home() -> dict[str, str]:
    return {
        "message": (
            "AI Trust & Safety API "
            "is running."
        ),
        "documentation": "/docs",
        "version": "0.8.0",
    }


@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "healthy",
        "version": "0.8.0",
    }


@app.post(
    "/moderate",
    response_model=(
        ModerationResponse
    ),
    deprecated=True,
)
def legacy_moderate_content(
    request: ModerationTextRequest,
) -> ModerationResponse:
    decision = (
        fuse_moderation_decision(
            text=request.text,
            source_context=(
                request.source_context
            ),
            input_sources=["text"],
        )
    )

    fusion_warnings = (
        decision.pop(
            "fusion_warnings",
            [],
        )
    )

    return ModerationResponse(
        content_type="text",
        source_context=(
            request.source_context
        ),
        analyzed_text_preview=(
            request.text[:500]
        ),
        warnings=fusion_warnings,
        **decision,
    )
