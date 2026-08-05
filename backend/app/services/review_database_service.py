import json
import sqlite3
import uuid
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path
from typing import Any


BACKEND_DIRECTORY = (
    Path(__file__)
    .resolve()
    .parents[2]
)

DATA_DIRECTORY = (
    BACKEND_DIRECTORY
    / "data"
)

DATABASE_PATH = (
    DATA_DIRECTORY
    / "trust_safety.db"
)

ALLOWED_REVIEW_STATUSES = {
    "pending",
    "approved",
    "overturned",
    "escalated",
    "closed",
}


class ReviewDatabaseError(
    Exception
):
    pass


def current_utc_time() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def get_connection() -> (
    sqlite3.Connection
):
    DATA_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    connection = sqlite3.connect(
        DATABASE_PATH,
        timeout=30,
    )

    connection.row_factory = (
        sqlite3.Row
    )

    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    connection.execute(
        "PRAGMA journal_mode = WAL"
    )

    return connection


def row_to_dictionary(
    row: sqlite3.Row | None,
) -> dict[str, Any] | None:
    if row is None:
        return None

    result = dict(row)

    result[
        "human_review_required"
    ] = bool(
        result.get(
            "human_review_required",
            0,
        )
    )

    return result


def initialize_database() -> None:
    DATA_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    try:
        with get_connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS moderation_cases (
                    case_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,

                    content_type TEXT NOT NULL,
                    file_name TEXT,
                    content_preview TEXT NOT NULL DEFAULT '',

                    category TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    action TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    human_review_required INTEGER NOT NULL,
                    reason TEXT NOT NULL,

                    review_status TEXT NOT NULL DEFAULT 'pending',
                    reviewer_name TEXT,
                    reviewer_notes TEXT,
                    final_category TEXT,
                    final_action TEXT,
                    reviewed_at TEXT,

                    CHECK (
                        confidence >= 0.0
                        AND confidence <= 1.0
                    ),

                    CHECK (
                        human_review_required
                        IN (0, 1)
                    ),

                    CHECK (
                        review_status IN (
                            'pending',
                            'approved',
                            'overturned',
                            'escalated',
                            'closed'
                        )
                    )
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    case_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    event_data TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,

                    FOREIGN KEY (case_id)
                    REFERENCES moderation_cases(case_id)
                    ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_moderation_cases_status_created
                ON moderation_cases(
                    review_status,
                    created_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_moderation_cases_created
                ON moderation_cases(
                    created_at DESC
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                idx_audit_events_case_created
                ON audit_events(
                    case_id,
                    created_at ASC
                )
                """
            )

            connection.execute(
                "PRAGMA optimize"
            )

    except sqlite3.Error as exc:
        raise ReviewDatabaseError(
            "The review database could "
            "not be initialized."
        ) from exc


def add_audit_event(
    *,
    connection: sqlite3.Connection,
    case_id: str,
    event_type: str,
    event_data: (
        dict[str, Any] | None
    ) = None,
) -> None:
    connection.execute(
        """
        INSERT INTO audit_events (
            case_id,
            event_type,
            event_data,
            created_at
        )
        VALUES (?, ?, ?, ?)
        """,
        (
            case_id,
            event_type,
            json.dumps(
                event_data or {},
                ensure_ascii=False,
            ),
            current_utc_time(),
        ),
    )


def create_review_case(
    *,
    content_type: str,
    file_name: str | None,
    content_preview: str,
    category: str,
    severity: str,
    action: str,
    confidence: float,
    human_review_required: bool,
    reason: str,
) -> dict[str, Any]:
    initialize_database()

    case_id = str(
        uuid.uuid4()
    )

    timestamp = current_utc_time()

    safe_preview = (
        content_preview.strip()[:500]
    )

    review_status = (
        "pending"
        if human_review_required
        else "approved"
    )

    try:
        with get_connection() as connection:
            connection.execute(
                """
                INSERT INTO moderation_cases (
                    case_id,
                    created_at,
                    updated_at,
                    content_type,
                    file_name,
                    content_preview,
                    category,
                    severity,
                    action,
                    confidence,
                    human_review_required,
                    reason,
                    review_status
                )
                VALUES (
                    ?, ?, ?, ?, ?, ?, ?,
                    ?, ?, ?, ?, ?, ?
                )
                """,
                (
                    case_id,
                    timestamp,
                    timestamp,
                    content_type,
                    file_name,
                    safe_preview,
                    category,
                    severity,
                    action,
                    round(
                        float(
                            confidence
                        ),
                        4,
                    ),
                    int(
                        human_review_required
                    ),
                    reason,
                    review_status,
                ),
            )

            add_audit_event(
                connection=connection,
                case_id=case_id,
                event_type=(
                    "case_created"
                ),
                event_data={
                    "category": category,
                    "severity": severity,
                    "action": action,
                    "confidence": (
                        confidence
                    ),
                    "human_review_required": (
                        human_review_required
                    ),
                    "review_status": (
                        review_status
                    ),
                },
            )

            row = connection.execute(
                """
                SELECT *
                FROM moderation_cases
                WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()

    except sqlite3.Error as exc:
        raise ReviewDatabaseError(
            "The moderation case could "
            "not be saved."
        ) from exc

    result = row_to_dictionary(
        row
    )

    if result is None:
        raise ReviewDatabaseError(
            "The saved moderation case "
            "could not be retrieved."
        )

    return result


def get_review_case(
    case_id: str,
) -> dict[str, Any] | None:
    initialize_database()

    try:
        with get_connection() as connection:
            row = connection.execute(
                """
                SELECT *
                FROM moderation_cases
                WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()

    except sqlite3.Error as exc:
        raise ReviewDatabaseError(
            "The moderation case could "
            "not be retrieved."
        ) from exc

    return row_to_dictionary(
        row
    )


def list_review_cases(
    *,
    review_status: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict[str, Any]]:
    initialize_database()

    safe_limit = max(
        1,
        min(
            int(limit),
            100,
        ),
    )

    safe_offset = max(
        0,
        int(offset),
    )

    if (
        review_status is not None
        and review_status
        not in ALLOWED_REVIEW_STATUSES
    ):
        raise ReviewDatabaseError(
            "The requested review "
            "status is invalid."
        )

    try:
        with get_connection() as connection:
            if review_status:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM moderation_cases
                    WHERE review_status = ?
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (
                        review_status,
                        safe_limit,
                        safe_offset,
                    ),
                ).fetchall()

            else:
                rows = connection.execute(
                    """
                    SELECT *
                    FROM moderation_cases
                    ORDER BY created_at DESC
                    LIMIT ? OFFSET ?
                    """,
                    (
                        safe_limit,
                        safe_offset,
                    ),
                ).fetchall()

    except sqlite3.Error as exc:
        raise ReviewDatabaseError(
            "The review queue could "
            "not be retrieved."
        ) from exc

    return [
        row_to_dictionary(row)
        for row in rows
        if row is not None
    ]


def get_case_audit_events(
    case_id: str,
) -> list[dict[str, Any]]:
    initialize_database()

    try:
        with get_connection() as connection:
            rows = connection.execute(
                """
                SELECT
                    event_id,
                    case_id,
                    event_type,
                    event_data,
                    created_at
                FROM audit_events
                WHERE case_id = ?
                ORDER BY created_at ASC,
                         event_id ASC
                """,
                (case_id,),
            ).fetchall()

    except sqlite3.Error as exc:
        raise ReviewDatabaseError(
            "The audit history could "
            "not be retrieved."
        ) from exc

    events: list[
        dict[str, Any]
    ] = []

    for row in rows:
        event = dict(row)

        try:
            event["event_data"] = (
                json.loads(
                    event[
                        "event_data"
                    ]
                )
            )

        except (
            json.JSONDecodeError,
            TypeError,
        ):
            event["event_data"] = {}

        events.append(event)

    return events


def update_review_case(
    *,
    case_id: str,
    review_status: str,
    reviewer_name: str,
    reviewer_notes: str = "",
    final_category: str | None = None,
    final_action: str | None = None,
) -> dict[str, Any] | None:
    initialize_database()

    if (
        review_status
        not in ALLOWED_REVIEW_STATUSES
    ):
        raise ReviewDatabaseError(
            "The new review status "
            "is invalid."
        )

    cleaned_reviewer = (
        reviewer_name.strip()[:100]
    )

    if not cleaned_reviewer:
        raise ReviewDatabaseError(
            "A reviewer name is required."
        )

    cleaned_notes = (
        reviewer_notes.strip()[
            :2_000
        ]
    )

    timestamp = current_utc_time()

    try:
        with get_connection() as connection:
            existing_row = (
                connection.execute(
                    """
                    SELECT *
                    FROM moderation_cases
                    WHERE case_id = ?
                    """,
                    (case_id,),
                ).fetchone()
            )

            if existing_row is None:
                return None

            connection.execute(
                """
                UPDATE moderation_cases
                SET
                    updated_at = ?,
                    review_status = ?,
                    reviewer_name = ?,
                    reviewer_notes = ?,
                    final_category = ?,
                    final_action = ?,
                    reviewed_at = ?
                WHERE case_id = ?
                """,
                (
                    timestamp,
                    review_status,
                    cleaned_reviewer,
                    cleaned_notes,
                    final_category,
                    final_action,
                    timestamp,
                    case_id,
                ),
            )

            add_audit_event(
                connection=connection,
                case_id=case_id,
                event_type=(
                    "human_review_updated"
                ),
                event_data={
                    "previous_status": (
                        existing_row[
                            "review_status"
                        ]
                    ),
                    "new_status": (
                        review_status
                    ),
                    "reviewer_name": (
                        cleaned_reviewer
                    ),
                    "reviewer_notes": (
                        cleaned_notes
                    ),
                    "final_category": (
                        final_category
                    ),
                    "final_action": (
                        final_action
                    ),
                },
            )

            updated_row = (
                connection.execute(
                    """
                    SELECT *
                    FROM moderation_cases
                    WHERE case_id = ?
                    """,
                    (case_id,),
                ).fetchone()
            )

    except sqlite3.Error as exc:
        raise ReviewDatabaseError(
            "The moderation case could "
            "not be updated."
        ) from exc

    return row_to_dictionary(
        updated_row
    )