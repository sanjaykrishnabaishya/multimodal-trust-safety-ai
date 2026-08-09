from __future__ import annotations

import sys

from scripts import freeze_stable_knowledge_v3_candidate as freezer


RC2_ENGINE_VERSION = "india-world-english-v3.4-rc2-development"
RC2_CANDIDATE_ID = "rc2"
RC2_DEVELOPMENT_RUN = "full-development-rc2-v1"


def main() -> None:
    freezer.EXPECTED_ENGINE_VERSION = RC2_ENGINE_VERSION
    sys.argv = [
        sys.argv[0],
        "--candidate-id",
        RC2_CANDIDATE_ID,
        "--development-run",
        RC2_DEVELOPMENT_RUN,
    ]
    freezer.main()


if __name__ == "__main__":
    main()
