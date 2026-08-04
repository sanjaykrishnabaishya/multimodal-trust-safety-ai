import csv
import random
from pathlib import Path


RANDOM_SEED = 42
random.seed(RANDOM_SEED)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATASET_DIR = PROJECT_ROOT / "datasets"

CATEGORIES = [
    "Child Abuse",
    "Spam",
    "Scam",
    "Harassment/Cyberbullying",
    "Hate Speech",
    "Fake News",
    "Violence",
    "Nudity",
    "Normal/Ignore",
]

CATEGORY_DATA = {
    "Child Abuse": {
        "contexts": ["private_message", "social_media", "child_safety_report"],
        "examples": [
            "An adult asks a minor to keep their private conversation secret.",
            "An account asks a child to send personal images.",
            "A user repeatedly attempts to move a conversation with a minor to a private app.",
            "A child-safety report describes suspicious contact without graphic details.",
        ],
    },
    "Spam": {
        "contexts": ["advertisement", "comment_section", "direct_message"],
        "examples": [
            "The same promotional message is posted repeatedly.",
            "An account sends unsolicited advertisements to many users.",
            "A comment contains repeated links unrelated to the discussion.",
            "A business announcement may be legitimate but was sent without consent.",
        ],
    },
    "Scam": {
        "contexts": ["banking", "shopping", "investment", "job_offer"],
        "examples": [
            "The message asks for an OTP to restore a blocked bank account.",
            "The sender promises a large guaranteed investment return.",
            "A fake prize notice asks the recipient to pay a processing fee.",
            "An unfamiliar recruiter requests payment before an interview.",
        ],
    },
    "Harassment/Cyberbullying": {
        "contexts": ["social_media", "gaming", "school", "workplace"],
        "examples": [
            "A user repeatedly posts humiliating comments about another person.",
            "Several accounts coordinate unwanted insulting messages.",
            "A person threatens to publish private messages to embarrass someone.",
            "Two friends exchange language that may be joking or insulting.",
        ],
    },
    "Hate Speech": {
        "contexts": ["comment_section", "forum", "news_report", "education"],
        "examples": [
            "A post attacks people because of a protected characteristic.",
            "A user calls for a protected group to be excluded from public life.",
            "A news report quotes hateful rhetoric while criticizing it.",
            "An educational document examines the history of discriminatory propaganda.",
        ],
    },
    "Fake News": {
        "contexts": ["social_media", "blog", "satire", "verified_news"],
        "examples": [
            "An unverified post presents a fabricated public event as fact.",
            "A manipulated headline makes a claim unsupported by its article.",
            "A satire article uses an intentionally fictional headline.",
            "A verified report corrects a previously circulated false claim.",
        ],
    },
    "Violence": {
        "contexts": ["real_threat", "news", "education", "gaming"],
        "examples": [
            "A person makes a specific threat to physically harm someone.",
            "A news report shows non-graphic footage of a damaged building.",
            "A history lesson discusses a past armed conflict.",
            "Players discuss defeating opponents inside a fictional game.",
        ],
    },
    "Nudity": {
        "contexts": ["explicit", "art", "medical", "news"],
        "examples": [
            "The content appears to contain explicit adult imagery.",
            "A museum image shows a classical nude marble sculpture.",
            "A medical lesson contains an anatomical illustration.",
            "A news report contains a blurred non-explicit image.",
        ],
    },
    "Normal/Ignore": {
        "contexts": ["personal", "education", "business", "entertainment"],
        "examples": [
            "A user shares a photograph of a meal with friends.",
            "A teacher posts a normal classroom announcement.",
            "A customer asks a business about its opening hours.",
            "A video shows a person demonstrating a harmless hobby.",
        ],
    },
}

POLICIES = [
    {
        "category": "Child Abuse",
        "default_severity": "Critical",
        "default_action": "Block and escalate",
        "human_review_required": True,
        "notes": "Never store explicit child exploitation media. Use safe descriptions and escalate suspected cases.",
    },
    {
        "category": "Spam",
        "default_severity": "Low",
        "default_action": "Limit distribution",
        "human_review_required": False,
        "notes": "Consider repetition, consent, relevance, and sender behaviour.",
    },
    {
        "category": "Scam",
        "default_severity": "High",
        "default_action": "Block and warn",
        "human_review_required": False,
        "notes": "Look for credential theft, payment requests, impersonation, and unrealistic returns.",
    },
    {
        "category": "Harassment/Cyberbullying",
        "default_severity": "Medium",
        "default_action": "Restrict and warn",
        "human_review_required": False,
        "notes": "Consider targeting, repetition, power imbalance, humour, and credible threats.",
    },
    {
        "category": "Hate Speech",
        "default_severity": "High",
        "default_action": "Block",
        "human_review_required": True,
        "notes": "Distinguish attacks from counterspeech, news reporting, and education.",
    },
    {
        "category": "Fake News",
        "default_severity": "Medium",
        "default_action": "Label and reduce distribution",
        "human_review_required": True,
        "notes": "Check evidence, source reliability, satire, corrections, and potential real-world harm.",
    },
    {
        "category": "Violence",
        "default_severity": "High",
        "default_action": "Block or show warning",
        "human_review_required": True,
        "notes": "Differentiate threats and graphic media from news, history, sport, and gaming.",
    },
    {
        "category": "Nudity",
        "default_severity": "High",
        "default_action": "Block or age-restrict",
        "human_review_required": True,
        "notes": "Allow contextual exceptions for medical, educational, artistic, and news content.",
    },
    {
        "category": "Normal/Ignore",
        "default_severity": "None",
        "default_action": "Allow",
        "human_review_required": False,
        "notes": "Content has no meaningful policy violation.",
    },
]


def decision_for(category: str, context: str, index: int) -> dict:
    grey_case = index % 11 == 0

    if category == "Child Abuse":
        if context == "child_safety_report":
            return {
                "severity": "High",
                "action": "Allow report and escalate for review",
                "human_review_required": True,
                "grey_case": False,
                "reason": "The content reports a child-safety concern without containing prohibited media.",
            }

        return {
            "severity": "Critical",
            "action": "Block and escalate",
            "human_review_required": True,
            "grey_case": False,
            "reason": "The content contains indicators of unsafe contact involving a minor.",
        }

    if category == "Spam":
        return {
            "severity": "Low",
            "action": "Allow pending review" if grey_case else "Limit distribution",
            "human_review_required": grey_case,
            "grey_case": grey_case,
            "reason": "The content appears repetitive, unsolicited, promotional, or unrelated.",
        }

    if category == "Scam":
        return {
            "severity": "Medium" if grey_case else "High",
            "action": "Warn and review" if grey_case else "Block and warn",
            "human_review_required": grey_case,
            "grey_case": grey_case,
            "reason": "The content contains possible financial fraud, impersonation, or credential theft.",
        }

    if category == "Harassment/Cyberbullying":
        return {
            "severity": "Medium",
            "action": "Review context" if context == "gaming" or grey_case else "Restrict and warn",
            "human_review_required": context == "gaming" or grey_case,
            "grey_case": context == "gaming" or grey_case,
            "reason": "The decision depends on targeting, repetition, threat level, and conversational context.",
        }

    if category == "Hate Speech":
        if context in {"news_report", "education"}:
            return {
                "severity": "Low",
                "action": "Allow",
                "human_review_required": False,
                "grey_case": False,
                "reason": "Hateful material is discussed in reporting or educational context without endorsement.",
            }

        return {
            "severity": "High",
            "action": "Block",
            "human_review_required": grey_case,
            "grey_case": grey_case,
            "reason": "The content appears to attack people based on a protected characteristic.",
        }

    if category == "Fake News":
        if context in {"satire", "verified_news"}:
            return {
                "severity": "Low",
                "action": "Allow with context label",
                "human_review_required": False,
                "grey_case": False,
                "reason": "The context indicates satire, correction, or verified reporting.",
            }

        return {
            "severity": "Medium",
            "action": "Label and reduce distribution",
            "human_review_required": True,
            "grey_case": True,
            "reason": "The factual claim requires source verification before a final decision.",
        }

    if category == "Violence":
        if context == "real_threat":
            return {
                "severity": "Critical",
                "action": "Block and escalate",
                "human_review_required": True,
                "grey_case": False,
                "reason": "The content may contain a credible real-world threat.",
            }

        if context == "news":
            return {
                "severity": "Medium",
                "action": "Allow with sensitive-content warning",
                "human_review_required": False,
                "grey_case": False,
                "reason": "The content depicts or discusses violence in non-graphic news reporting.",
            }

        if context in {"education", "gaming"}:
            return {
                "severity": "Low",
                "action": "Allow",
                "human_review_required": context == "gaming" and grey_case,
                "grey_case": context == "gaming" and grey_case,
                "reason": "The violent language or imagery is educational, historical, fictional, or game-related.",
            }

    if category == "Nudity":
        if context in {"art", "medical"}:
            return {
                "severity": "Low",
                "action": "Allow",
                "human_review_required": False,
                "grey_case": False,
                "reason": "The material has legitimate artistic, medical, or educational context.",
            }

        if context == "news":
            return {
                "severity": "Medium",
                "action": "Blur and show warning",
                "human_review_required": grey_case,
                "grey_case": grey_case,
                "reason": "The material appears in news context and may require sensitive-content treatment.",
            }

        return {
            "severity": "High",
            "action": "Block or age-restrict",
            "human_review_required": True,
            "grey_case": grey_case,
            "reason": "The content may contain explicit adult nudity and requires age and consent checks.",
        }

    return {
        "severity": "None",
        "action": "Allow",
        "human_review_required": False,
        "grey_case": False,
        "reason": "No meaningful Trust and Safety policy violation was detected.",
    }


def selected_category(index: int) -> str:
    return CATEGORIES[index % len(CATEGORIES)]


def source_for(context: str) -> str:
    if context in {"news", "news_report", "verified_news"}:
        return "news"
    if context in {"education", "medical"}:
        return "education"
    if context == "art":
        return "art"
    if context == "gaming":
        return "gaming"
    return "user"


def make_base(index: int, content_type: str) -> dict:
    category = selected_category(index)
    category_data = CATEGORY_DATA[category]
    contexts = category_data["contexts"]
    examples = category_data["examples"]

    context = contexts[(index // len(CATEGORIES)) % len(contexts)]
    example = examples[(index // len(CATEGORIES)) % len(examples)]
    decision = decision_for(category, context, index)

    return {
        "id": f"{content_type[:3].upper()}-{index + 1:04d}",
        "content_type": content_type,
        "category": category,
        "source_context": context,
        "source_type": source_for(context),
        "severity": decision["severity"],
        "action": decision["action"],
        "human_review_required": decision["human_review_required"],
        "grey_case": decision["grey_case"],
        "reason": decision["reason"],
        "example": example,
    }


def generate_text_rows(count: int) -> list[dict]:
    rows = []

    for index in range(count):
        base = make_base(index, "text")
        variation = (index // len(CATEGORIES)) + 1

        rows.append(
            {
                "id": base["id"],
                "content_type": base["content_type"],
                "text": f"{base['example']} Synthetic variation {variation}.",
                "source_type": base["source_type"],
                "source_context": base["source_context"],
                "category": base["category"],
                "severity": base["severity"],
                "action": base["action"],
                "human_review_required": base["human_review_required"],
                "grey_case": base["grey_case"],
                "reason": base["reason"],
            }
        )

    return rows


def generate_document_rows(count: int) -> list[dict]:
    rows = []
    file_types = ["pdf", "docx", "txt"]

    for index in range(count):
        base = make_base(index, "document")
        file_type = file_types[index % len(file_types)]

        rows.append(
            {
                "id": base["id"],
                "content_type": base["content_type"],
                "file_name": f"sample_document_{index + 1:04d}.{file_type}",
                "file_type": file_type,
                "document_title": f"Synthetic {base['category']} document example",
                "extracted_text": base["example"],
                "embedded_image_description": (
                    "No embedded image."
                    if index % 3
                    else "A safe synthetic illustration relevant to the document."
                ),
                "source_type": base["source_type"],
                "source_context": base["source_context"],
                "category": base["category"],
                "severity": base["severity"],
                "action": base["action"],
                "human_review_required": base["human_review_required"],
                "grey_case": base["grey_case"],
                "reason": base["reason"],
            }
        )

    return rows


def generate_image_rows(count: int) -> list[dict]:
    rows = []
    image_types = ["jpg", "png", "webp"]

    for index in range(count):
        base = make_base(index, "image")
        image_type = image_types[index % len(image_types)]

        rows.append(
            {
                "id": base["id"],
                "content_type": base["content_type"],
                "file_name": f"sample_image_{index + 1:04d}.{image_type}",
                "image_caption": base["example"],
                "ocr_text": (
                    f"Visible synthetic text related to {base['category']}."
                    if index % 4 != 0
                    else ""
                ),
                "visual_signals": (
                    f"Safe annotated visual indicators for the {base['category']} category."
                ),
                "source_type": base["source_type"],
                "source_context": base["source_context"],
                "category": base["category"],
                "severity": base["severity"],
                "action": base["action"],
                "human_review_required": base["human_review_required"],
                "grey_case": base["grey_case"],
                "reason": base["reason"],
            }
        )

    return rows


def generate_video_rows(count: int) -> list[dict]:
    rows = []

    for index in range(count):
        base = make_base(index, "video")
        duration = 10 + ((index * 7) % 171)

        rows.append(
            {
                "id": base["id"],
                "content_type": base["content_type"],
                "file_name": f"sample_video_{index + 1:04d}.mp4",
                "duration_seconds": duration,
                "transcript": base["example"],
                "frame_descriptions": (
                    f"Sampled frames contain safe synthetic indicators related to "
                    f"{base['category']} in {base['source_context']} context."
                ),
                "ocr_text": (
                    f"On-screen synthetic text for {base['category']}."
                    if index % 3 != 0
                    else ""
                ),
                "audio_description": (
                    "Speech and ordinary background audio; no raw media is stored in this dataset."
                ),
                "source_type": base["source_type"],
                "source_context": base["source_context"],
                "category": base["category"],
                "severity": base["severity"],
                "action": base["action"],
                "human_review_required": base["human_review_required"],
                "grey_case": base["grey_case"],
                "reason": base["reason"],
            }
        )

    return rows


def write_csv(file_path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows supplied for {file_path.name}")

    with file_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def validate_rows(name: str, rows: list[dict], expected_count: int) -> None:
    if len(rows) != expected_count:
        raise ValueError(
            f"{name} has {len(rows)} rows; expected {expected_count}."
        )

    missing_categories = set(CATEGORIES) - {
        row["category"] for row in rows
    }

    if missing_categories:
        raise ValueError(
            f"{name} is missing categories: {sorted(missing_categories)}"
        )


def main() -> None:
    DATASET_DIR.mkdir(parents=True, exist_ok=True)

    text_rows = generate_text_rows(400)
    document_rows = generate_document_rows(200)
    image_rows = generate_image_rows(250)
    video_rows = generate_video_rows(150)

    validate_rows("text_dataset.csv", text_rows, 400)
    validate_rows("document_dataset.csv", document_rows, 200)
    validate_rows("image_dataset.csv", image_rows, 250)
    validate_rows("video_dataset.csv", video_rows, 150)

    write_csv(DATASET_DIR / "text_dataset.csv", text_rows)
    write_csv(DATASET_DIR / "document_dataset.csv", document_rows)
    write_csv(DATASET_DIR / "image_dataset.csv", image_rows)
    write_csv(DATASET_DIR / "video_dataset.csv", video_rows)
    write_csv(DATASET_DIR / "policies.csv", POLICIES)

    total_records = (
        len(text_rows)
        + len(document_rows)
        + len(image_rows)
        + len(video_rows)
    )

    print("Multimodal dataset generation completed.")
    print(f"Output folder: {DATASET_DIR}")
    print(f"Text records: {len(text_rows)}")
    print(f"Document records: {len(document_rows)}")
    print(f"Image records: {len(image_rows)}")
    print(f"Video records: {len(video_rows)}")
    print(f"Total moderation records: {total_records}")
    print(f"Policy records: {len(POLICIES)}")


if __name__ == "__main__":
    main()