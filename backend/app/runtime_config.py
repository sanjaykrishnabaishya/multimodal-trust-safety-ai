"""Runtime configuration for safe local and deployed access."""

from __future__ import annotations

import os
import re


DEFAULT_ALLOWED_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)

PRIVATE_LAN_ORIGIN_REGEX = (
    r"^https?://(?:localhost|127\.0\.0\.1|"
    r"10(?:\.\d{1,3}){3}|"
    r"192\.168(?:\.\d{1,3}){2}|"
    r"172\.(?:1[6-9]|2\d|3[01])(?:\.\d{1,3}){2})"
    r"(?::\d{1,5})?$"
)


def get_allowed_origins() -> list[str]:
    """Return explicit browser origins without ever using a wildcard."""

    configured = os.getenv(
        "TRUSTSCOPE_ALLOWED_ORIGINS",
        "",
    )

    if not configured.strip():
        return list(DEFAULT_ALLOWED_ORIGINS)

    origins = []

    for item in configured.split(","):
        origin = item.strip().rstrip("/")

        if origin and origin not in origins:
            origins.append(origin)

    return origins


def get_private_lan_origin_regex() -> str | None:
    """Allow a phone on the same private LAN unless explicitly disabled."""

    enabled = os.getenv(
        "TRUSTSCOPE_ALLOW_PRIVATE_LAN",
        "true",
    ).strip().lower()

    if enabled in {"0", "false", "no", "off"}:
        return None

    return PRIVATE_LAN_ORIGIN_REGEX


def is_private_lan_origin(origin: str) -> bool:
    """Expose the origin contract for focused tests and diagnostics."""

    return bool(
        re.fullmatch(
            PRIVATE_LAN_ORIGIN_REGEX,
            origin,
        )
    )
