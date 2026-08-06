import argparse
import csv
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

import pdfplumber


BACKEND_DIRECTORY = (
    Path(__file__).resolve().parents[1]
)

PROJECT_DIRECTORY = (
    BACKEND_DIRECTORY.parent
)

DEFAULT_DICTIONARY_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "spam_dictionary.csv"
)

DEFAULT_EXCLUSION_PATH = (
    PROJECT_DIRECTORY
    / "datasets"
    / "spam_dictionary_exclusions.csv"
)

DEFAULT_REPORT_PATH = (
    PROJECT_DIRECTORY
    / "docs"
    / "spam_dictionary_import_report.json"
)

LANGUAGE_COLUMNS = (
    "english",
    "hindi",
    "kannada",
    "tamil",
    "telugu",
    "marathi",
    "bengali",
    "assamese",
    "gujarati",
    "punjabi",
)

PDF_LANGUAGE_COLUMNS = {
    "english": "english",
    "hindi": "hindi",
    "kannada": "kannada",
    "tamil": "tamil",
    "telugu": "telugu",
    "marathi": "marathi",
    "bengali": "bengali",
    "assamese": "assamese",
    "gujrati": "gujarati",
    "gujarati": "gujarati",
    "punjabi": "punjabi",
}

CID_PATTERN = re.compile(
    r"\(cid:\d+\)",
    flags=re.IGNORECASE,
)

WHITESPACE_PATTERN = re.compile(
    r"\s+"
)

MOJIBAKE_MARKERS = (
    "à¤",
    "à¦",
    "àª",
    "à¨",
    "à®",
    "à°",
    "à²",
)

HINDI_EXCLUSIONS = {
    "कार्रवाई आवश्यक है",
    "इलाज",
    "पहुँच",
    "पहुंच",
    "बीमार",
    "बीमारी",
    "सीडी पर पते",
    "सभी प्राकृतिक",
    "राशि",
    "अद्भुत प्रस्ताव",
    "मुझसे पूछो कैसे",
    "पर देखा",
    "इससे पहले की बहुत देर हो जाए",
    "किसी भी कीमत पर नहीं",
    "सबसे अच्छा प्रस्ताव",
    "साल का सबसे ज्यादा बिकने वाला उत्पाद",
    "अब तक की सबसे बड़ी सफलता",
    "क्या हमारे पास एक मिनट हो सकता है",
    "बापू",
    "चौंकना",
    "एक सदस्य होने के नाते",
    "मुझ पर विश्वास करो",
    "सेल फोन कैंसर घोटाला",
    "सेलफोन कैंसर घोटाला",
    "बिल",
    "ब्लॉग",
    "प्रतियोगिताएं",
    "प्रतियोगिता",
    "एकदम नया पेजर",
    "खरीदना",
    "केबल कनवर्टर",
    "पुकारना",
    "प्रसिद्ध व्यक्ति",
    "प्रमाणित",
    "टिप्पणी",
    "बधाई हो",
    "सही ढंग से कॉपी करें",
    "कोविड",
    "श्रेय",
    "घूमने की जगह",
    "सप्ताह के दिन",
    "प्रिय मित्र",
    "तेज",
    "वित्त",
    "वित्तीय",
    "कुछ भी पता करो",
    "वापस पीछा करो",
    "शुक्रवार से पहले",
    "इसे दूर हो जाओ",
    "अब समझे",
    "संकेत",
    "इसे दूर रखें",
    "महान",
    "महान प्रस्ताव",
    "नमस्ते",
    "आकर्षक",
    "खुला",
    "उत्तम",
    "प्रदर्शन",
    "पराजय",
    "अलग",
    "सफलता",
    "विजेता",
    "जीत",
}


def repair_mojibake(
    value: str,
) -> str:
    if not any(
        marker in value
        for marker in MOJIBAKE_MARKERS
    ):
        return value

    try:
        return value.encode(
            "latin-1"
        ).decode(
            "utf-8"
        )

    except (
        UnicodeEncodeError,
        UnicodeDecodeError,
    ):
        return value


def normalize_phrase(
    value: str | None,
) -> str:
    if not value:
        return ""

    repaired_value = (
        repair_mojibake(
            value
        )
    )

    normalized_value = (
        unicodedata.normalize(
            "NFKC",
            repaired_value,
        )
    )

    normalized_value = (
        WHITESPACE_PATTERN.sub(
            " ",
            normalized_value,
        )
    )

    return normalized_value.strip()


def contains_corrupted_text(
    value: str,
) -> bool:
    if CID_PATTERN.search(
        value
    ):
        return True

    if "\ufffd" in value:
        return True

    return any(
        marker in value
        for marker in MOJIBAKE_MARKERS
    )


def is_usable_phrase(
    value: str,
) -> bool:
    if not value:
        return False

    if len(value) > 160:
        return False

    if contains_corrupted_text(
        value
    ):
        return False

    if value.casefold() in {
        language.casefold()
        for language
        in PDF_LANGUAGE_COLUMNS
    }:
        return False

    return any(
        character.isalnum()
        for character in value
    )


def normalized_lookup_value(
    value: str,
) -> str:
    return normalize_phrase(
        value
    ).casefold()


def build_exclusion_lookup() -> set[str]:
    return {
        normalized_lookup_value(
            phrase
        )
        for phrase in HINDI_EXCLUSIONS
    }


def determine_weight(
    phrase: str,
) -> float:
    lowered_phrase = (
        phrase.casefold()
    )

    high_risk_fragments = (
        "otp",
        "password",
        "credit card",
        "debit card",
        "bank transfer",
        "bitcoin",
        "crypto",
        "urgent",
        "act now",
        "claim your prize",
        "winner",
        "you have been selected",
        "100% free",
        "guaranteed income",
        "make money",
        "work from home",
        "limited time",
        "click here",
        "whatsapp",
        "telegram",
        "xanax",
        "viagra",
        "vicodin",
    )

    if any(
        fragment in lowered_phrase
        for fragment in high_risk_fragments
    ):
        return 1.5

    if len(
        phrase.split()
    ) >= 3:
        return 1.25

    return 1.0


def extract_dictionary(
    pdf_path: Path,
) -> tuple[
    list[dict[str, Any]],
    dict[str, Any],
]:
    accepted_entries: list[
        dict[str, Any]
    ] = []

    skipped_by_language: dict[
        str,
        int,
    ] = defaultdict(int)

    accepted_by_language: dict[
        str,
        int,
    ] = defaultdict(int)

    duplicates_by_language: dict[
        str,
        int,
    ] = defaultdict(int)

    exclusion_skips = 0

    seen_entries: set[
        tuple[str, str]
    ] = set()

    exclusion_lookup = (
        build_exclusion_lookup()
    )

    with pdfplumber.open(
        pdf_path
    ) as pdf:
        dictionary_page_count = min(
            16,
            len(pdf.pages),
        )

        for page_number in range(
            1,
            dictionary_page_count + 1,
        ):
            page = pdf.pages[
                page_number - 1
            ]

            tables = (
                page.extract_tables()
            )

            for table in tables:
                if not table:
                    continue

                raw_headers = table[0][
                    :len(LANGUAGE_COLUMNS)
                ]

                headers = [
                    PDF_LANGUAGE_COLUMNS.get(
                        normalize_phrase(
                            header
                        ).casefold(),
                        "",
                    )
                    for header in raw_headers
                ]

                for row in table[1:]:
                    for column_index, cell in (
                        enumerate(
                            row[
                                :len(headers)
                            ]
                        )
                    ):
                        language = headers[
                            column_index
                        ]

                        if not language:
                            continue

                        phrase = (
                            normalize_phrase(
                                cell
                            )
                        )

                        if not is_usable_phrase(
                            phrase
                        ):
                            if phrase:
                                skipped_by_language[
                                    language
                                ] += 1

                            continue

                        normalized_phrase = (
                            normalized_lookup_value(
                                phrase
                            )
                        )

                        if (
                            language == "hindi"
                            and normalized_phrase
                            in exclusion_lookup
                        ):
                            exclusion_skips += 1
                            continue

                        entry_key = (
                            language,
                            normalized_phrase,
                        )

                        if entry_key in seen_entries:
                            duplicates_by_language[
                                language
                            ] += 1
                            continue

                        seen_entries.add(
                            entry_key
                        )

                        accepted_entries.append(
                            {
                                "language": (
                                    language
                                ),
                                "phrase": phrase,
                                "normalized_phrase": (
                                    normalized_phrase
                                ),
                                "weight": (
                                    determine_weight(
                                        phrase
                                    )
                                ),
                                "source_page": (
                                    page_number
                                ),
                            }
                        )

                        accepted_by_language[
                            language
                        ] += 1

    accepted_entries.sort(
        key=lambda entry: (
            entry["language"],
            entry[
                "normalized_phrase"
            ],
        )
    )

    report = {
        "source_pdf": str(
            pdf_path
        ),
        "dictionary_pages_processed": (
            min(
                16,
                len(pdf.pages),
            )
        ),
        "total_entries_accepted": len(
            accepted_entries
        ),
        "total_corrupted_or_invalid_skipped": (
            sum(
                skipped_by_language.values()
            )
        ),
        "total_duplicates_skipped": (
            sum(
                duplicates_by_language.values()
            )
        ),
        "total_exclusions_applied": (
            exclusion_skips
        ),
        "accepted_by_language": {
            language: (
                accepted_by_language.get(
                    language,
                    0,
                )
            )
            for language
            in LANGUAGE_COLUMNS
        },
        "corrupted_or_invalid_by_language": {
            language: (
                skipped_by_language.get(
                    language,
                    0,
                )
            )
            for language
            in LANGUAGE_COLUMNS
        },
        "duplicates_by_language": {
            language: (
                duplicates_by_language.get(
                    language,
                    0,
                )
            )
            for language
            in LANGUAGE_COLUMNS
        },
        "quality_warning": (
            "The source PDF contains broken "
            "font mappings in some Indian-language "
            "cells. Entries containing PDF CID "
            "placeholders or corrupted characters "
            "were intentionally excluded."
        ),
    }

    return accepted_entries, report


def write_dictionary(
    entries: list[dict[str, Any]],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=(
                "language",
                "phrase",
                "normalized_phrase",
                "weight",
                "source_page",
            ),
        )

        writer.writeheader()
        writer.writerows(
            entries
        )


def write_exclusions(
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    exclusions = sorted(
        HINDI_EXCLUSIONS,
        key=lambda phrase: (
            normalize_phrase(
                phrase
            ).casefold()
        ),
    )

    with output_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as output_file:
        writer = csv.DictWriter(
            output_file,
            fieldnames=(
                "language",
                "phrase",
                "normalized_phrase",
                "reason",
            ),
        )

        writer.writeheader()

        for phrase in exclusions:
            writer.writerow(
                {
                    "language": "hindi",
                    "phrase": phrase,
                    "normalized_phrase": (
                        normalized_lookup_value(
                            phrase
                        )
                    ),
                    "reason": (
                        "Explicitly listed for "
                        "removal in the source PDF."
                    ),
                }
            )


def write_report(
    report: dict[str, Any],
    output_path: Path,
) -> None:
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as output_file:
        json.dump(
            report,
            output_file,
            ensure_ascii=False,
            indent=2,
        )


def parse_arguments() -> (
    argparse.Namespace
):
    parser = argparse.ArgumentParser(
        description=(
            "Import the multilingual spam "
            "dictionary from the supplied PDF."
        )
    )

    parser.add_argument(
        "pdf_path",
        type=Path,
        help=(
            "Path to the spam dictionary PDF."
        ),
    )

    parser.add_argument(
        "--dictionary-output",
        type=Path,
        default=(
            DEFAULT_DICTIONARY_PATH
        ),
    )

    parser.add_argument(
        "--exclusion-output",
        type=Path,
        default=(
            DEFAULT_EXCLUSION_PATH
        ),
    )

    parser.add_argument(
        "--report-output",
        type=Path,
        default=(
            DEFAULT_REPORT_PATH
        ),
    )

    return parser.parse_args()


def main() -> None:
    arguments = parse_arguments()

    pdf_path = (
        arguments.pdf_path
        .expanduser()
        .resolve()
    )

    if not pdf_path.exists():
        raise FileNotFoundError(
            "Spam dictionary PDF "
            f"not found: {pdf_path}"
        )

    if (
        pdf_path.suffix.lower()
        != ".pdf"
    ):
        raise ValueError(
            "The input file must be a PDF."
        )

    entries, report = (
        extract_dictionary(
            pdf_path
        )
    )

    if not entries:
        raise ValueError(
            "No reliable dictionary entries "
            "could be extracted."
        )

    dictionary_output = (
        arguments.dictionary_output
        .resolve()
    )

    exclusion_output = (
        arguments.exclusion_output
        .resolve()
    )

    report_output = (
        arguments.report_output
        .resolve()
    )

    write_dictionary(
        entries,
        dictionary_output,
    )

    write_exclusions(
        exclusion_output
    )

    report[
        "dictionary_output"
    ] = str(
        dictionary_output
    )

    report[
        "exclusion_output"
    ] = str(
        exclusion_output
    )

    report[
        "report_output"
    ] = str(
        report_output
    )

    write_report(
        report,
        report_output,
    )

    print()
    print(
        "Spam dictionary import complete."
    )

    print(
        "Accepted entries: "
        f"{report['total_entries_accepted']}"
    )

    print(
        "Corrupted or invalid cells skipped: "
        f"{report['total_corrupted_or_invalid_skipped']}"
    )

    print(
        "Duplicate entries skipped: "
        f"{report['total_duplicates_skipped']}"
    )

    print(
        "Exclusions applied during import: "
        f"{report['total_exclusions_applied']}"
    )

    print()
    print("Accepted entries by language:")

    for language, count in (
        report[
            "accepted_by_language"
        ].items()
    ):
        print(
            f"  {language}: {count}"
        )

    print()
    print(
        "Dictionary: "
        f"{dictionary_output}"
    )

    print(
        "Exclusions: "
        f"{exclusion_output}"
    )

    print(
        "Audit report: "
        f"{report_output}"
    )


if __name__ == "__main__":
    main()