"""Retired importer retained only to prevent accidental reuse.

The original importer was disabled after reviewing the source permissions:

* The United Nations website terms grant copying only for personal,
  non-commercial use and prohibit redistribution or derivative compilations
  unless separate permission applies.
* The Ministry of Home Affairs website policy requires permission before its
  contents are reproduced partially or fully.

TrustScopeAI is a public product, so these sources must not be copied into a
local product registry without written permission or a source-specific open
licence.
"""


def main() -> None:
    raise SystemExit(
        "DISABLED: this importer must not retrieve or reproduce UN or MHA "
        "website materials without documented permission or a specific open "
        "licence. No data was downloaded."
    )


if __name__ == "__main__":
    main()
