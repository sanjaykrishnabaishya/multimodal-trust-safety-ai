from __future__ import annotations

from pathlib import Path


BACKEND_DIRECTORY = Path(__file__).resolve().parents[1]

SERVICE_PATH = (
    BACKEND_DIRECTORY
    / "app"
    / "services"
    / "identity_impersonation_service.py"
)


REFINEMENT_BLOCK = r'''

# ---------------------------------------------------------------------------
# Refined patterns added after mismatch analysis
# ---------------------------------------------------------------------------

EXPLICIT_IMPERSONATION_PATTERNS.update(
    {
        "fake_support_identity": re.compile(
            r"""
            \b
            fake
            \s+
            (?:
                customer\s+
                |
                technical\s+
                |
                bank\s+
                |
                government\s+
            )?
            (?:
                support\s+
            )?
            (?:
                profile
                |
                account
                |
                agent
                |
                representative
                |
                officer
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)


IDENTITY_CLAIM_PATTERNS.update(
    {
        "official_institution_claim": re.compile(
            r"""
            \b
            (?:
                i\s+am
                |
                i'm
                |
                we\s+are
                |
                this\s+is
            )
            \s+
            (?:
                the\s+
            )?
            (?:
                official
                |
                verified
                |
                authorized
                |
                genuine
            )
            \s+
            (?:
                bank\s+
                |
                government\s+
                |
                company\s+
                |
                customer\s+
                |
                technical\s+
            )?
            (?:
                customer\s+
                |
                technical\s+
            )?
            (?:
                support\s+
            )?
            (?:
                agent
                |
                representative
                |
                officer
                |
                team
                |
                department
                |
                account
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)


DECEPTIVE_REQUEST_PATTERNS.update(
    {
        "expanded_credential_request": re.compile(
            r"""
            \b
            (?:
                ask(?:ed|ing)?\s+for
                |
                request(?:ed|ing)?
                |
                send
                |
                share
                |
                provide
                |
                confirm
                |
                verify
                |
                enter
                |
                submit
            )
            \s+
            (?:
                me\s+to\s+
            )?
            (?:
                your
                |
                my
                |
                the
            )?
            \s*
            (?:
                otp
                |
                password
                |
                passcode
                |
                pin
                |
                cvv
                |
                credentials
                |
                login
                |
                account\s+details
                |
                banking\s+details
                |
                bank\s+details
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),

        "expanded_money_request": re.compile(
            r"""
            \b
            (?:
                ask(?:ed|ing)?\s+(?:me\s+)?to\s+
                |
                request(?:ed|ing)?\s+
                |
                send\s+
                |
                pay\s+
                |
                transfer\s+
                |
                deposit\s+
            )
            (?:
                your\s+
                |
                my\s+
                |
                the\s+
                |
                a\s+
            )?
            (?:
                money
                |
                funds
                |
                payment
                |
                cash
                |
                fee
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)


SAFE_CONTEXT_PATTERNS.update(
    {
        "news_documentary_reporting": re.compile(
            r"""
            \b
            (?:
                article
                |
                news\s+article
                |
                news\s+report
                |
                report
                |
                documentary
                |
                research\s+paper
                |
                academic\s+paper
                |
                study
            )
            \s+
            (?:
                reports?
                |
                describes?
                |
                discusses?
                |
                mentions?
                |
                examines?
                |
                investigates?
                |
                explains?
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),

        "historical_reporting": re.compile(
            r"""
            \b
            (?:
                documentary
                |
                article
                |
                report
                |
                study
            )
            .{0,40}
            \b
            (?:
                historical
                |
                history\s+of
                |
                investigation
                |
                research
            )
            \b
            """,
            re.IGNORECASE | re.VERBOSE,
        ),
    }
)
'''


INSERTION_MARKER = """def _normalize_text(text: str) -> str:
"""


def main() -> None:
    if not SERVICE_PATH.exists():
        raise FileNotFoundError(
            f"File not found: {SERVICE_PATH}"
        )

    source = SERVICE_PATH.read_text(
        encoding="utf-8"
    )

    identifier = (
        '"official_institution_claim"'
    )

    if identifier in source:
        print(
            "Identity-impersonation refinements "
            "are already installed."
        )
        return

    if INSERTION_MARKER not in source:
        raise RuntimeError(
            "Could not find the insertion marker. "
            "No file was changed."
        )

    updated_source = source.replace(
        INSERTION_MARKER,
        (
            REFINEMENT_BLOCK
            + "\n\n"
            + INSERTION_MARKER
        ),
        1,
    )

    compile(
        updated_source,
        str(SERVICE_PATH),
        "exec",
    )

    SERVICE_PATH.write_text(
        updated_source,
        encoding="utf-8",
    )

    print(
        "Identity-impersonation detector "
        "refined successfully."
    )
    print(
        f"Updated: {SERVICE_PATH}"
    )


if __name__ == "__main__":
    main()