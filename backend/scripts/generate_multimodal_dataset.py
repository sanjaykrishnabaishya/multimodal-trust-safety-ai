import csv
import sys
from pathlib import Path


BACKEND_DIRECTORY = (
    Path(__file__)
    .resolve()
    .parents[1]
)

PROJECT_ROOT = (
    BACKEND_DIRECTORY.parent
)

DATASET_DIRECTORY = (
    PROJECT_ROOT
    / "datasets"
)

sys.path.insert(
    0,
    str(BACKEND_DIRECTORY),
)

from app.policy_config import (  # noqa: E402
    CATEGORY_POLICIES,
    POLICY_VERSION,
    ModerationCategory,
)


CATEGORY_EXAMPLES: dict[
    ModerationCategory,
    tuple[str, ...],
] = {
    ModerationCategory.RELIGIOUSLY_OFFENSIVE: (
        (
            "A post tells users to burn "
            "another community's religious book."
        ),
        (
            "The message encourages people to "
            "destroy a religious symbol."
        ),
        (
            "A user posts denigrating abuse "
            "directed at a religious prophet."
        ),
        (
            "The content celebrates damage to "
            "a place of worship."
        ),
    ),

    ModerationCategory.HATE_SPEECH: (
        (
            "A post says that a protected "
            "group is inferior."
        ),
        (
            "The message calls for a religious "
            "group to be excluded from society."
        ),
        (
            "A user attacks people because of "
            "their race and nationality."
        ),
        (
            "The content describes an ethnic "
            "group as not human."
        ),
    ),

    ModerationCategory.TERRORISM: (
        (
            "A post praises a banned terrorist "
            "organization and asks users to join."
        ),
        (
            "The message requests donations for "
            "a terrorist organization."
        ),
        (
            "The content distributes extremist "
            "recruitment propaganda."
        ),
        (
            "A user provides instructions "
            "intended to support a terrorist attack."
        ),
    ),

    ModerationCategory.VIOLENT_CONTENT: (
        (
            "A person sends the direct threat: "
            "I will kill you tonight."
        ),
        (
            "The content graphically depicts "
            "a person being tortured."
        ),
        (
            "The image description contains "
            "visible internal organs after an attack."
        ),
        (
            "A user says they are going to stab "
            "a specific person."
        ),
    ),

    ModerationCategory.DANGEROUS_CONTENT: (
        (
            "The video tells viewers to try a "
            "dangerous stunt without safety equipment."
        ),
        (
            "A post encourages users to jump "
            "from a roof as part of a challenge."
        ),
        (
            "The content gives instructions "
            "to cause an explosion at home."
        ),
        (
            "A user encourages another person "
            "to physically harm themselves."
        ),
    ),

    ModerationCategory.GRAPHIC_SEXUAL_CONTENT: (
        (
            "The content contains explicit "
            "adult sexual imagery."
        ),
        (
            "The image description indicates "
            "visible genitalia outside an allowed context."
        ),
        (
            "A post promotes a website selling "
            "explicit pornographic material."
        ),
        (
            "The content contains a morphed "
            "sexual image of an adult."
        ),
    ),

    ModerationCategory.SEXUAL_HARASSMENT: (
        (
            "A user repeatedly demands that "
            "another person send nude pictures."
        ),
        (
            "The message contains an unwanted "
            "request for a sexual favour."
        ),
        (
            "A person sends sexually explicit "
            "messages after being asked to stop."
        ),
        (
            "The content threatens consequences "
            "unless a person agrees to sexual activity."
        ),
    ),

    ModerationCategory.CYBERBULLYING: (
        (
            "A user repeatedly tells another "
            "person that they are worthless."
        ),
        (
            "Several accounts coordinate to "
            "publicly humiliate one individual."
        ),
        (
            "A person threatens to share private "
            "messages to embarrass someone."
        ),
        (
            "A user repeatedly pressures someone "
            "to provide their phone number."
        ),
    ),

    ModerationCategory.INVASION_OF_PRIVACY: (
        (
            "A private video was secretly "
            "recorded and shared without consent."
        ),
        (
            "The content contains a leaked "
            "intimate video posted without consent."
        ),
        (
            "A hidden-camera recording shows "
            "a person's private moment."
        ),
        (
            "A person reports that their private "
            "photograph was uploaded without consent."
        ),
    ),

    ModerationCategory.ILLEGAL_ACTIVITIES: (
        (
            "A post offers illegal drugs for sale."
        ),
        (
            "The message advertises an unapproved "
            "medicine as a guaranteed cure."
        ),
        (
            "A user advertises a gun for sale "
            "without a license."
        ),
        (
            "The content promotes an illegal "
            "foreign gambling website."
        ),
    ),

    ModerationCategory.PRIVATE_INFORMATION: (
        (
            "A post exposes another person's "
            "Aadhaar card number without permission."
        ),
        (
            "The content publishes someone's "
            "credit card number and contact details."
        ),
        (
            "A user leaks another person's "
            "private email address and phone number."
        ),
        (
            "The image contains an unredacted "
            "bank account statement."
        ),
    ),

    ModerationCategory.IDENTITY_THEFT: (
        (
            "An account impersonates a bank "
            "representative to deceive customers."
        ),
        (
            "A fake customer-support profile "
            "pretends to represent a company."
        ),
        (
            "A user operates an account using "
            "another person's stolen identity."
        ),
        (
            "The profile impersonates a public "
            "figure without a parody label."
        ),
    ),

    ModerationCategory.MISINFORMATION: (
        (
            "A fabricated report presents a "
            "made-up public event as fact."
        ),
        (
            "A manipulated headline makes a "
            "claim unsupported by the article."
        ),
        (
            "The post promotes a false medical "
            "claim as a confirmed cure."
        ),
        (
            "A fake election result is presented "
            "as an official announcement."
        ),
    ),

    ModerationCategory.SPAM_SCAM_PHISHING: (
        (
            "URGENT! Claim your prize now by "
            "sending your OTP on WhatsApp."
        ),
        (
            "A fake banking message asks the "
            "recipient to share their password."
        ),
        (
            "An unsolicited promotion promises "
            "guaranteed income and requests a fee."
        ),
        (
            "A repeated message tells users to "
            "click a suspicious payment link."
        ),
    ),

    ModerationCategory.INTELLECTUAL_PROPERTY: (
        (
            "A post distributes a pirated movie "
            "download without authorization."
        ),
        (
            "The content offers counterfeit "
            "products using a protected trademark."
        ),
        (
            "A user sells unauthorized copies "
            "of copyrighted software."
        ),
        (
            "The message provides an illegal "
            "download of copyrighted material."
        ),
    ),

    ModerationCategory.MALICIOUS_PROGRAMS: (
        (
            "A post provides a link to download "
            "credential-stealing malware."
        ),
        (
            "The content distributes a ransomware "
            "payload intended to compromise devices."
        ),
        (
            "A user shares a phishing kit for "
            "stealing account credentials."
        ),
        (
            "The instructions tell users to "
            "disable antivirus and install a trojan."
        ),
    ),

    ModerationCategory.ABUSIVE_WORDS: (
        (
            "A user directly tells another "
            "person: you are a disgusting idiot."
        ),
        (
            "The message calls a targeted person "
            "a stupid loser and piece of trash."
        ),
        (
            "A user repeatedly describes another "
            "person as worthless and pathetic."
        ),
        (
            "The comment contains obfuscated "
            "abusive words directed at an individual."
        ),
    ),

    ModerationCategory.CHILD_EXPLOITATION: (
        (
            "An adult asks a minor to keep "
            "their private conversation secret."
        ),
        (
            "An account asks a child to send "
            "private personal images."
        ),
        (
            "A user asks a minor to move to a "
            "private app and not tell their parents."
        ),
        (
            "The content describes physical "
            "harm being directed at a child."
        ),
    ),

    ModerationCategory.NORMAL_IGNORE: (
        (
            "A user shares a photograph of "
            "a meal with friends."
        ),
        (
            "A teacher posts an ordinary "
            "classroom announcement."
        ),
        (
            "A customer asks a business about "
            "its opening hours."
        ),
        (
            "A person tells a friend: you are "
            "a winner and you are born to rule."
        ),
        (
            "A cybersecurity lesson says never "
            "to share an OTP or password."
        ),
        (
            "A verified report corrects a "
            "previously circulated false claim."
        ),
        (
            "A museum description discusses "
            "a classical nude sculpture."
        ),
        (
            "A medical lesson contains a "
            "non-explicit anatomy illustration."
        ),
        (
            "A news report discusses violence "
            "without showing graphic imagery."
        ),
        (
            "A video shows a person demonstrating "
            "a harmless hobby."
        ),
    ),
}


def selected_category(
    index: int,
) -> ModerationCategory:
    categories = list(
        ModerationCategory
    )

    return categories[
        index
        % len(categories)
    ]


def selected_example(
    *,
    category: ModerationCategory,
    index: int,
) -> str:
    examples = (
        CATEGORY_EXAMPLES[
            category
        ]
    )

    category_cycle = (
        index
        // len(
            ModerationCategory
        )
    )

    return examples[
        category_cycle
        % len(examples)
    ]


def build_decision(
    *,
    category: ModerationCategory,
    index: int,
) -> dict:
    policy = (
        CATEGORY_POLICIES[
            category
        ]
    )

    if category == (
        ModerationCategory
        .NORMAL_IGNORE
    ):
        return {
            "severity": "None",
            "action": "Allow",
            "human_review_required": False,
            "grey_case": False,
            "reason": (
                "The content is safe, generic, "
                "educational, corrective, or "
                "otherwise does not meet a "
                "restrictive moderation condition."
            ),
        }

    grey_case = (
        index % 17 == 0
    )

    if grey_case:
        return {
            "severity": (
                policy.default_severity
            ),
            "action": (
                "Flag and send for "
                "human review"
            ),
            "human_review_required": True,
            "grey_case": True,
            "reason": (
                "The content contains indicators "
                f"of {category.value}, but the "
                "final enforcement decision "
                "requires human review."
            ),
        }

    return {
        "severity": (
            policy.default_severity
        ),
        "action": (
            policy.default_action
        ),
        "human_review_required": (
            policy.human_review_required
        ),
        "grey_case": False,
        "reason": (
            "The content matches the configured "
            f"conditions for {category.value}."
        ),
    }


def make_base_record(
    *,
    index: int,
    content_type: str,
) -> dict:
    category = selected_category(
        index
    )

    example = selected_example(
        category=category,
        index=index,
    )

    decision = build_decision(
        category=category,
        index=index,
    )

    identifier_prefixes = {
        "text": "TEX",
        "document": "DOC",
        "image": "IMA",
        "video": "VID",
    }

    return {
        "id": (
            identifier_prefixes[
                content_type
            ]
            + "-"
            + f"{index + 1:04d}"
        ),
        "content_type": (
            content_type
        ),
        "category": (
            category.value
        ),
        "severity": (
            decision[
                "severity"
            ]
        ),
        "action": (
            decision[
                "action"
            ]
        ),
        "human_review_required": (
            decision[
                "human_review_required"
            ]
        ),
        "grey_case": (
            decision[
                "grey_case"
            ]
        ),
        "reason": (
            decision[
                "reason"
            ]
        ),
        "example": example,
        "policy_version": (
            POLICY_VERSION
        ),
    }


def generate_text_rows(
    count: int,
) -> list[dict]:
    rows: list[
        dict
    ] = []

    for index in range(
        count
    ):
        base = make_base_record(
            index=index,
            content_type="text",
        )

        variation = (
            index
            // len(
                ModerationCategory
            )
            + 1
        )

        rows.append(
            {
                "id": base["id"],
                "content_type": (
                    base[
                        "content_type"
                    ]
                ),
                "text": (
                    base["example"]
                    + " Synthetic variation "
                    + f"{variation}."
                ),
                "category": (
                    base["category"]
                ),
                "severity": (
                    base["severity"]
                ),
                "action": (
                    base["action"]
                ),
                "human_review_required": (
                    base[
                        "human_review_required"
                    ]
                ),
                "grey_case": (
                    base[
                        "grey_case"
                    ]
                ),
                "reason": (
                    base["reason"]
                ),
                "policy_version": (
                    base[
                        "policy_version"
                    ]
                ),
            }
        )

    return rows


def generate_document_rows(
    count: int,
) -> list[dict]:
    rows: list[
        dict
    ] = []

    file_types = (
        "pdf",
        "docx",
        "txt",
    )

    for index in range(
        count
    ):
        base = make_base_record(
            index=index,
            content_type="document",
        )

        file_type = (
            file_types[
                index
                % len(file_types)
            ]
        )

        rows.append(
            {
                "id": base["id"],
                "content_type": (
                    base[
                        "content_type"
                    ]
                ),
                "file_name": (
                    "sample_document_"
                    f"{index + 1:04d}."
                    f"{file_type}"
                ),
                "file_type": (
                    file_type
                ),
                "document_title": (
                    "Synthetic "
                    f"{base['category']} "
                    "document"
                ),
                "extracted_text": (
                    base["example"]
                ),
                "embedded_image_description": (
                    "No embedded image."
                    if index % 3
                    else (
                        "A safe synthetic "
                        "illustration associated "
                        "with the labeled policy "
                        "example."
                    )
                ),
                "category": (
                    base["category"]
                ),
                "severity": (
                    base["severity"]
                ),
                "action": (
                    base["action"]
                ),
                "human_review_required": (
                    base[
                        "human_review_required"
                    ]
                ),
                "grey_case": (
                    base[
                        "grey_case"
                    ]
                ),
                "reason": (
                    base["reason"]
                ),
                "policy_version": (
                    base[
                        "policy_version"
                    ]
                ),
            }
        )

    return rows


def generate_image_rows(
    count: int,
) -> list[dict]:
    rows: list[
        dict
    ] = []

    image_types = (
        "jpg",
        "png",
        "webp",
    )

    for index in range(
        count
    ):
        base = make_base_record(
            index=index,
            content_type="image",
        )

        image_type = (
            image_types[
                index
                % len(image_types)
            ]
        )

        rows.append(
            {
                "id": base["id"],
                "content_type": (
                    base[
                        "content_type"
                    ]
                ),
                "file_name": (
                    "sample_image_"
                    f"{index + 1:04d}."
                    f"{image_type}"
                ),
                "image_caption": (
                    base["example"]
                ),
                "ocr_text": (
                    base["example"]
                    if index % 4
                    else ""
                ),
                "visual_signals": (
                    "Safe synthetic visual "
                    "description for the "
                    f"{base['category']} "
                    "policy category. No raw "
                    "harmful media is stored."
                ),
                "category": (
                    base["category"]
                ),
                "severity": (
                    base["severity"]
                ),
                "action": (
                    base["action"]
                ),
                "human_review_required": (
                    base[
                        "human_review_required"
                    ]
                ),
                "grey_case": (
                    base[
                        "grey_case"
                    ]
                ),
                "reason": (
                    base["reason"]
                ),
                "policy_version": (
                    base[
                        "policy_version"
                    ]
                ),
            }
        )

    return rows


def generate_video_rows(
    count: int,
) -> list[dict]:
    rows: list[
        dict
    ] = []

    for index in range(
        count
    ):
        base = make_base_record(
            index=index,
            content_type="video",
        )

        duration = (
            10
            + (
                index
                * 7
            )
            % 171
        )

        rows.append(
            {
                "id": base["id"],
                "content_type": (
                    base[
                        "content_type"
                    ]
                ),
                "file_name": (
                    "sample_video_"
                    f"{index + 1:04d}.mp4"
                ),
                "duration_seconds": (
                    duration
                ),
                "transcript": (
                    base["example"]
                ),
                "frame_descriptions": (
                    "Sampled frames contain "
                    "a safe synthetic description "
                    "associated with the "
                    f"{base['category']} "
                    "policy category."
                ),
                "ocr_text": (
                    base["example"]
                    if index % 3
                    else ""
                ),
                "audio_description": (
                    "Synthetic speech and "
                    "ordinary background audio. "
                    "No raw harmful media is "
                    "stored in the dataset."
                ),
                "category": (
                    base["category"]
                ),
                "severity": (
                    base["severity"]
                ),
                "action": (
                    base["action"]
                ),
                "human_review_required": (
                    base[
                        "human_review_required"
                    ]
                ),
                "grey_case": (
                    base[
                        "grey_case"
                    ]
                ),
                "reason": (
                    base["reason"]
                ),
                "policy_version": (
                    base[
                        "policy_version"
                    ]
                ),
            }
        )

    return rows


def write_csv(
    file_path: Path,
    rows: list[dict],
) -> None:
    if not rows:
        raise ValueError(
            "No rows supplied for "
            f"{file_path.name}."
        )

    with file_path.open(
        "w",
        newline="",
        encoding="utf-8-sig",
    ) as csv_file:
        writer = csv.DictWriter(
            csv_file,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def validate_rows(
    *,
    file_name: str,
    rows: list[dict],
    expected_count: int,
) -> None:
    if (
        len(rows)
        != expected_count
    ):
        raise ValueError(
            f"{file_name} has "
            f"{len(rows)} rows; "
            f"expected {expected_count}."
        )

    expected_categories = {
        category.value
        for category
        in ModerationCategory
    }

    actual_categories = {
        row["category"]
        for row in rows
    }

    missing_categories = (
        expected_categories
        - actual_categories
    )

    unexpected_categories = (
        actual_categories
        - expected_categories
    )

    if missing_categories:
        raise ValueError(
            f"{file_name} is missing "
            "categories: "
            f"{sorted(missing_categories)}"
        )

    if unexpected_categories:
        raise ValueError(
            f"{file_name} has unexpected "
            "categories: "
            f"{sorted(unexpected_categories)}"
        )

    identifiers = [
        row["id"]
        for row in rows
    ]

    if (
        len(identifiers)
        != len(
            set(
                identifiers
            )
        )
    ):
        raise ValueError(
            f"{file_name} contains "
            "duplicate identifiers."
        )

    for row in rows:
        if (
            row[
                "policy_version"
            ]
            != POLICY_VERSION
        ):
            raise ValueError(
                f"{file_name} contains an "
                "incorrect policy version."
            )


def category_counts(
    rows: list[dict],
) -> dict[str, int]:
    counts: dict[
        str,
        int,
    ] = {}

    for row in rows:
        category = (
            row[
                "category"
            ]
        )

        counts[
            category
        ] = (
            counts.get(
                category,
                0,
            )
            + 1
        )

    return dict(
        sorted(
            counts.items()
        )
    )


def main() -> None:
    DATASET_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    text_rows = (
        generate_text_rows(
            400
        )
    )

    document_rows = (
        generate_document_rows(
            200
        )
    )

    image_rows = (
        generate_image_rows(
            250
        )
    )

    video_rows = (
        generate_video_rows(
            150
        )
    )

    datasets = (
        (
            "text_dataset.csv",
            text_rows,
            400,
        ),
        (
            "document_dataset.csv",
            document_rows,
            200,
        ),
        (
            "image_dataset.csv",
            image_rows,
            250,
        ),
        (
            "video_dataset.csv",
            video_rows,
            150,
        ),
    )

    for (
        file_name,
        rows,
        expected_count,
    ) in datasets:
        validate_rows(
            file_name=file_name,
            rows=rows,
            expected_count=(
                expected_count
            ),
        )

        write_csv(
            DATASET_DIRECTORY
            / file_name,
            rows,
        )

    total_records = sum(
        len(rows)
        for _, rows, _
        in datasets
    )

    print(
        "Multimodal dataset generation "
        "completed."
    )

    print(
        "Policy version: "
        f"{POLICY_VERSION}"
    )

    print(
        "Output folder: "
        f"{DATASET_DIRECTORY}"
    )

    print(
        "Text records: "
        f"{len(text_rows)}"
    )

    print(
        "Document records: "
        f"{len(document_rows)}"
    )

    print(
        "Image records: "
        f"{len(image_rows)}"
    )

    print(
        "Video records: "
        f"{len(video_rows)}"
    )

    print(
        "Total moderation records: "
        f"{total_records}"
    )

    print()
    print(
        "Combined category counts:"
    )

    combined_rows = (
        text_rows
        + document_rows
        + image_rows
        + video_rows
    )

    for category, count in (
        category_counts(
            combined_rows
        ).items()
    ):
        print(
            f"  {category}: {count}"
        )

    print()
    print(
        "policies.csv was preserved."
    )

    print(
        "spam_dictionary.csv was "
        "preserved."
    )

    print(
        "spam_dictionary_exclusions.csv "
        "was preserved."
    )


if __name__ == "__main__":
    main()