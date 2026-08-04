import re
from typing import Iterable


CATEGORY_PRIORITY = [
    "Child Abuse",
    "Scam",
    "Violence",
    "Hate Speech",
    "Harassment/Cyberbullying",
    "Fake News",
    "Nudity",
    "Spam",
]


RULES = {
    "Spam": [
        "unsolicited advertisement",
        "repeated promotion",
        "repeated message",
        "bulk message",
        "click my link",
        "subscribe now",
        "limited offer",
        "promotional message",
    ],
    "Scam": [
        "send your otp",
        "share your otp",
        "send otp",
        "share otp",
        "send your password",
        "share your password",
        "bank account is blocked",
        "account has been blocked",
        "account is suspended",
        "processing fee",
        "guaranteed return",
        "guaranteed investment",
        "double your money",
        "lottery winnings",
        "claim your prize",
        "card details",
        "gift card payment",
        "cryptocurrency payment",
        "registration fee",
        "verify your banking identity",
    ],
    "Harassment/Cyberbullying": [
        "nobody likes you",
        "you are useless",
        "you are stupid",
        "publicly humiliate",
        "humiliating comments",
        "embarrass you",
        "share your private messages",
        "everyone should shame",
        "keep insulting",
        "repeatedly insult",
    ],
    "Hate Speech": [
        "protected group is inferior",
        "exclude this group",
        "because of their race",
        "because of their religion",
        "because of their ethnicity",
        "because of their nationality",
        "attack this protected group",
        "protected group should not exist",
    ],
    "Fake News": [
        "fabricated report",
        "fabricated headline",
        "unverified claim",
        "no supporting evidence",
        "secret cure",
        "government is hiding",
        "media will not tell you",
        "confirmed without evidence",
        "fake public announcement",
        "manipulated headline",
    ],
    "Violence": [
        "i will kill you",
        "going to kill you",
        "i will hurt you",
        "going to hurt you",
        "physically harm",
        "attack this person",
        "specific threat",
        "armed attack",
        "graphic violence",
        "violent attack",
        "shoot this person",
        "stab this person",
    ],
    "Nudity": [
        "explicit adult imagery",
        "explicit nudity",
        "sexual image",
        "intimate image",
        "adult content",
        "nude image",
        "nude photograph",
        "anatomical illustration",
        "nude sculpture",
    ],
}


CHILD_TERMS = [
    "child",
    "minor",
    "underage",
    "young student",
]

CHILD_RISK_TERMS = [
    "send personal images",
    "send private images",
    "keep this secret",
    "private conversation secret",
    "move to a private app",
    "do not tell your parents",
    "meet without telling",
    "request personal images",
]


def normalize_text(text: str) -> str:
    lowered = text.lower()
    lowered = re.sub(r"\s+", " ", lowered)

    return lowered.strip()


def unique_values(
    values: Iterable[str],
) -> list[str]:
    return list(dict.fromkeys(values))


def find_category_matches(
    normalized_text: str,
) -> dict[str, list[str]]:
    matches: dict[str, list[str]] = {}

    child_matches = [
        term
        for term in CHILD_TERMS
        if term in normalized_text
    ]

    child_risk_matches = [
        term
        for term in CHILD_RISK_TERMS
        if term in normalized_text
    ]

    if child_matches and child_risk_matches:
        matches["Child Abuse"] = unique_values(
            child_matches + child_risk_matches
        )

    for category, signals in RULES.items():
        category_matches = [
            signal
            for signal in signals
            if signal in normalized_text
        ]

        if category_matches:
            matches[category] = category_matches

    return matches


def select_category(
    matches: dict[str, list[str]],
) -> str:
    for category in CATEGORY_PRIORITY:
        if category in matches:
            return category

    return "Normal/Ignore"


def apply_context_policy(
    category: str,
    source_context: str,
    confidence: float,
    matched_signals: list[str],
) -> dict:
    context = source_context.lower().strip()

    if category == "Child Abuse":
        return {
            "severity": "Critical",
            "action": "Block and escalate",
            "human_review_required": True,
            "reason": (
                "The content contains child-safety risk "
                "signals and requires immediate review."
            ),
        }

    if category == "Scam":
        return {
            "severity": "High",
            "action": "Block and warn",
            "human_review_required": confidence < 0.75,
            "reason": (
                "The content contains financial fraud, "
                "credential-theft, or impersonation signals."
            ),
        }

    if category == "Violence":
        if context in {
            "news",
            "verified_news",
        }:
            return {
                "severity": "Medium",
                "action": (
                    "Allow with sensitive-content warning"
                ),
                "human_review_required": False,
                "reason": (
                    "Violence-related material appears in "
                    "news-reporting context."
                ),
            }

        if context in {
            "education",
            "history",
            "gaming",
            "fiction",
        }:
            return {
                "severity": "Low",
                "action": "Allow",
                "human_review_required": (
                    confidence < 0.80
                ),
                "reason": (
                    "Violence-related language appears in "
                    "educational, historical, fictional, "
                    "or gaming context."
                ),
            }

        return {
            "severity": "Critical",
            "action": "Block and escalate",
            "human_review_required": True,
            "reason": (
                "The content contains possible real-world "
                "violent-threat signals."
            ),
        }

    if category == "Hate Speech":
        if context in {
            "news",
            "verified_news",
            "education",
            "history",
            "counterspeech",
        }:
            return {
                "severity": "Medium",
                "action": "Allow with context label",
                "human_review_required": True,
                "reason": (
                    "Potential hate-speech language appears "
                    "in reporting, education, history, or "
                    "counterspeech context."
                ),
            }

        return {
            "severity": "High",
            "action": "Block and review",
            "human_review_required": True,
            "reason": (
                "The content contains possible attacks "
                "based on a protected characteristic."
            ),
        }

    if category == "Harassment/Cyberbullying":
        return {
            "severity": "Medium",
            "action": "Restrict and warn",
            "human_review_required": (
                confidence < 0.80
                or context == "gaming"
            ),
            "reason": (
                "The content contains targeted insulting, "
                "humiliating, or bullying signals."
            ),
        }

    if category == "Fake News":
        if context == "satire":
            return {
                "severity": "Low",
                "action": "Allow with satire label",
                "human_review_required": False,
                "reason": (
                    "The disputed claim appears in "
                    "declared satire context."
                ),
            }

        return {
            "severity": "Medium",
            "action": "Label and reduce distribution",
            "human_review_required": True,
            "reason": (
                "The content contains an unverified or "
                "potentially fabricated factual claim."
            ),
        }

    if category == "Nudity":
        if context in {
            "art",
            "museum",
            "medical",
            "education",
        }:
            return {
                "severity": "Low",
                "action": "Allow",
                "human_review_required": False,
                "reason": (
                    "The material appears in legitimate "
                    "artistic, medical, museum, or "
                    "educational context."
                ),
            }

        if context in {
            "news",
            "verified_news",
        }:
            return {
                "severity": "Medium",
                "action": "Blur and show warning",
                "human_review_required": True,
                "reason": (
                    "The material appears in a news context "
                    "but may require sensitive treatment."
                ),
            }

        return {
            "severity": "High",
            "action": "Block or age-restrict",
            "human_review_required": True,
            "reason": (
                "The content contains possible explicit "
                "adult or intimate-image signals."
            ),
        }

    if category == "Spam":
        return {
            "severity": "Low",
            "action": "Limit distribution",
            "human_review_required": (
                confidence < 0.70
            ),
            "reason": (
                "The content contains repetitive, "
                "unsolicited, or promotional signals."
            ),
        }

    return {
        "severity": "None",
        "action": "Allow",
        "human_review_required": False,
        "reason": (
            "No rule-based moderation signal was detected."
        ),
    }


def moderate_text(
    text: str,
    source_context: str,
) -> dict:
    normalized_text = normalize_text(text)

    if not normalized_text:
        return {
            "category": "Normal/Ignore",
            "severity": "None",
            "action": "Allow",
            "confidence": 0.50,
            "human_review_required": True,
            "reason": (
                "No readable text was available for the "
                "baseline moderation engine."
            ),
            "matched_signals": [],
        }

    matches = find_category_matches(
        normalized_text
    )

    category = select_category(matches)
    matched_signals = matches.get(
        category,
        [],
    )

    if category == "Normal/Ignore":
        confidence = 0.65
    else:
        confidence = min(
            0.95,
            0.68 + (0.07 * len(matched_signals)),
        )

    policy = apply_context_policy(
        category=category,
        source_context=source_context,
        confidence=confidence,
        matched_signals=matched_signals,
    )

    return {
        "category": category,
        "severity": policy["severity"],
        "action": policy["action"],
        "confidence": round(confidence, 2),
        "human_review_required": policy[
            "human_review_required"
        ],
        "reason": policy["reason"],
        "matched_signals": matched_signals,
    }


def combine_extracted_signals(
    extracted_text: str = "",
    ocr_text: str = "",
    audio_transcript: str = "",
    visual_description: str = "",
) -> str:
    sections: list[str] = []

    if extracted_text.strip():
        sections.append(
            f"Extracted text:\n{extracted_text.strip()}"
        )

    if ocr_text.strip():
        sections.append(
            f"OCR text:\n{ocr_text.strip()}"
        )

    if audio_transcript.strip():
        sections.append(
            "Audio transcript:\n"
            f"{audio_transcript.strip()}"
        )

    if visual_description.strip():
        sections.append(
            "Visual description:\n"
            f"{visual_description.strip()}"
        )

    return "\n\n".join(sections)