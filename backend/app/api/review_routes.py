from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.review_schemas import (
    AuditEventResponse,
    ReviewCaseResponse,
    ReviewCaseUpdateRequest,
    ReviewStatus,
)
from app.services.review_database_service import (
    ReviewDatabaseError,
    get_case_audit_events,
    get_review_case,
    list_review_cases,
    update_review_case,
)


router = APIRouter(
    prefix="/review",
    tags=["Human Review"],
)


@router.get("/health")
def review_health() -> dict:
    try:
        cases = list_review_cases(
            limit=1,
            offset=0,
        )

        return {
            "status": "available",
            "database_connected": True,
            "sampled_case_count": len(
                cases
            ),
        }

    except ReviewDatabaseError as exc:
        raise HTTPException(
            status_code=503,
            detail=str(exc),
        ) from exc


@router.get(
    "/cases",
    response_model=list[
        ReviewCaseResponse
    ],
)
def get_review_queue(
    review_status: (
        ReviewStatus | None
    ) = Query(
        default=None,
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=100,
    ),
    offset: int = Query(
        default=0,
        ge=0,
    ),
) -> list[ReviewCaseResponse]:
    try:
        cases = list_review_cases(
            review_status=(
                review_status
            ),
            limit=limit,
            offset=offset,
        )

        return [
            ReviewCaseResponse(
                **case
            )
            for case in cases
        ]

    except ReviewDatabaseError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.get(
    "/cases/{case_id}",
    response_model=ReviewCaseResponse,
)
def get_review_case_by_id(
    case_id: str,
) -> ReviewCaseResponse:
    try:
        case = get_review_case(
            case_id
        )

    except ReviewDatabaseError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc

    if case is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The requested review "
                "case was not found."
            ),
        )

    return ReviewCaseResponse(
        **case
    )


@router.get(
    "/cases/{case_id}/audit",
    response_model=list[
        AuditEventResponse
    ],
)
def get_review_case_audit(
    case_id: str,
) -> list[AuditEventResponse]:
    try:
        case = get_review_case(
            case_id
        )

        if case is None:
            raise HTTPException(
                status_code=404,
                detail=(
                    "The requested review "
                    "case was not found."
                ),
            )

        events = (
            get_case_audit_events(
                case_id
            )
        )

        return [
            AuditEventResponse(
                **event
            )
            for event in events
        ]

    except HTTPException:
        raise

    except ReviewDatabaseError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
        ) from exc


@router.patch(
    "/cases/{case_id}",
    response_model=ReviewCaseResponse,
)
def submit_human_review(
    case_id: str,
    request: (
        ReviewCaseUpdateRequest
    ),
) -> ReviewCaseResponse:
    try:
        updated_case = (
            update_review_case(
                case_id=case_id,
                review_status=(
                    request.review_status
                ),
                reviewer_name=(
                    request.reviewer_name
                ),
                reviewer_notes=(
                    request.reviewer_notes
                ),
                final_category=(
                    request.final_category
                ),
                final_action=(
                    request.final_action
                ),
            )
        )

    except ReviewDatabaseError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    if updated_case is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "The requested review "
                "case was not found."
            ),
        )

    return ReviewCaseResponse(
        **updated_case
    )