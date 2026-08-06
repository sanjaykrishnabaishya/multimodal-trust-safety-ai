import re
import unicodedata
from typing import Iterable

from app.policy_config import (
    ModerationCategory,
    get_category_policy,
    normalize_category_name,
)


NORMAL_CATEGORY = (
    ModerationCategory
    .NORMAL_IGNORE
    .value
)

CATEGORY_PRIORITY = [
    (
        ModerationCategory
        .CHILD_EXPLOITATION
        .value
    ),
    (
        ModerationCategory
        .TERRORISM
        .value
    ),
    (
        ModerationCategory
        .MALICIOUS_PROGRAMS
        .value
    ),
    (
        ModerationCategory
        .HATE_SPEECH
        .value
    ),
    (
        ModerationCategory
        .RELIGIOUSLY_OFFENSIVE
        .value
    ),
    (
        ModerationCategory
        .VIOLENT_CONTENT
        .value
    ),
    (
        ModerationCategory
        .DANGEROUS_CONTENT
        .value
    ),
    (
        ModerationCategory
        .GRAPHIC_SEXUAL_CONTENT
        .value
    ),
    (
        ModerationCategory
        .SEXUAL_HARASSMENT
        .value
    ),
    (
        ModerationCategory
        .INVASION_OF_PRIVACY
        .value
    ),
    (
        ModerationCategory
        .PRIVATE_INFORMATION
        .value
    ),
    (
        ModerationCategory
        .IDENTITY_THEFT
        .value
    ),
    (
        ModerationCategory
        .ILLEGAL_ACTIVITIES
        .value
    ),
    (
        ModerationCategory
        .CYBERBULLYING
        .value
    ),
    (
        ModerationCategory
        .ABUSIVE_WORDS
        .value
    ),
    (
        ModerationCategory
        .MISINFORMATION
        .value
    ),
    (
        ModerationCategory
        .INTELLECTUAL_PROPERTY
        .value
    ),
    (
        ModerationCategory
        .SPAM_SCAM_PHISHING
        .value
    ),
]

RULES: dict[
    str,
    tuple[str, ...],
] = {
    (
        ModerationCategory
        .RELIGIOUSLY_OFFENSIVE
        .value
    ): (
        "destroy their religious symbol",
        "damage their religious symbol",
        "burn their religious book",
        "desecrate their religious",
        "mock their god",
        "insult their god",
        "abuse their prophet",
        "insult their prophet",
        "religious figure is disgusting",
        "religious deity is disgusting",
        "demolish their temple",
        "demolish their church",
        "demolish their mosque",
        "demolish their gurudwara",
    ),

    (
        ModerationCategory
        .HATE_SPEECH
        .value
    ): (
        "protected group is inferior",
        "this race is inferior",
        "this religion is inferior",
        "this caste is inferior",
        "this nationality is inferior",
        "exclude this group",
        "boycott this religion",
        "destroy this group",
        "remove this race",
        "attack this protected group",
        "protected group should not exist",
        "people of this religion should not exist",
        "people of this race should not exist",
        "because of their race",
        "because of their religion",
        "because of their ethnicity",
        "because of their nationality",
        "because of their caste",
        "all members of this group are criminals",
        "this group is not human",
    ),

    (
        ModerationCategory
        .TERRORISM
        .value
    ): (
        "join the terrorist organization",
        "support the terrorist organization",
        "support this terror group",
        "praise this terrorist attack",
        "glory to the terrorist group",
        "donate to the terrorist group",
        "fund the terrorist organization",
        "recruit for the terrorist group",
        "terrorist training material",
        "terrorist propaganda",
        "extremist recruitment",
        "instructions for a terrorist attack",
        "help the banned organization",
    ),

    (
        ModerationCategory
        .VIOLENT_CONTENT
        .value
    ): (
        "i will kill you",
        "going to kill you",
        "i will murder you",
        "i will shoot you",
        "i will stab you",
        "i will hurt you",
        "going to hurt you",
        "physically harm you",
        "attack this person",
        "shoot this person",
        "stab this person",
        "specific threat",
        "graphic violence",
        "violent attack",
        "armed attack",
        "decapitated body",
        "severed body parts",
        "visible internal organs",
        "bloody mutilation",
        "person being tortured",
        "animal being tortured",
        "burned body",
        "bloated body",
    ),

    (
        ModerationCategory
        .DANGEROUS_CONTENT
        .value
    ): (
        "try this dangerous stunt",
        "perform this dangerous stunt",
        "do this dangerous challenge",
        "dangerous experiment at home",
        "do not use safety equipment",
        "harm yourself",
        "hurt yourself",
        "set yourself on fire",
        "jump from the roof",
        "cause an explosion",
        "destroy their property",
        "instructions to make an explosive",
        "instructions to cause bodily harm",
        "challenge can kill you",
        "copy this life threatening stunt",
    ),

    (
        ModerationCategory
        .GRAPHIC_SEXUAL_CONTENT
        .value
    ): (
        "explicit adult imagery",
        "explicit sexual imagery",
        "explicit nudity",
        "visible genitalia",
        "visible anus",
        "visible nipples",
        "sexual intercourse",
        "sexual activity",
        "sex toy",
        "sexual content involving animals",
        "morphed sexual image",
        "intimate sexual image",
        "rape video",
        "simulated rape",
        "non-consensual sexual content",
        "pornographic website",
        "buy explicit content",
        "nude photograph",
    ),

    (
        ModerationCategory
        .SEXUAL_HARASSMENT
        .value
    ): (
        "send me sexual pictures",
        "send me nude pictures",
        "send me intimate pictures",
        "send me pornography",
        "sexual favour",
        "sexual favor",
        "sleep with me or",
        "have sex with me or",
        "unwanted sexual message",
        "sexually explicit message",
        "sexual remarks about you",
        "show me your body",
        "send nudes",
        "share nudes",
        "sexual demand",
    ),

    (
        ModerationCategory
        .CYBERBULLYING
        .value
    ): (
        "nobody likes you",
        "you are useless",
        "you are worthless",
        "you are stupid",
        "publicly humiliate",
        "humiliating comments",
        "embarrass you online",
        "share your private messages",
        "everyone should shame",
        "keep insulting",
        "repeatedly insult",
        "give me your phone number again",
        "send me your number again",
        "dm me again",
        "message me privately again",
        "everyone attack this person",
        "everyone harass this person",
    ),

    (
        ModerationCategory
        .INVASION_OF_PRIVACY
        .value
    ): (
        "recorded without consent",
        "shared without consent",
        "posted without consent",
        "uploaded without consent",
        "private moment without consent",
        "intimate moment without consent",
        "secretly recorded",
        "hidden camera recording",
        "leaked private video",
        "leaked intimate video",
        "leaked private photo",
        "revenge porn",
    ),

    (
        ModerationCategory
        .ILLEGAL_ACTIVITIES
        .value
    ): (
        "buy illegal drugs",
        "sell illegal drugs",
        "unapproved medicine for sale",
        "unapproved drug for sale",
        "psychotropic substances for sale",
        "buy a gun without license",
        "weapon for sale without license",
        "guns for sale",
        "prostitution services",
        "sexual services for money",
        "foreign gambling website",
        "illegal gambling website",
        "online betting guaranteed",
        "fake government emblem",
        "misuse the national flag",
        "black magic service",
        "vashikaran service",
    ),

    (
        ModerationCategory
        .PRIVATE_INFORMATION
        .value
    ): (
        "aadhaar card number",
        "aadhar card number",
        "pan card number",
        "voter card number",
        "driving license number",
        "identity card number",
        "credit card number",
        "debit card number",
        "bank account statement",
        "bank passbook",
        "publish their phone number",
        "publish their email address",
        "share their home address",
        "leak their phone number",
        "leak their email address",
        "here is their password",
        "here is their otp",
    ),

    (
        ModerationCategory
        .IDENTITY_THEFT
        .value
    ): (
        "impersonating another person",
        "impersonating this person",
        "pretending to be this person",
        "pretending to be the bank",
        "fake official account",
        "fake verified account",
        "stolen identity",
        "use their identity",
        "using someone else's identity",
        "identity theft",
        "fake customer support account",
        "impersonate customer support",
    ),

    (
        ModerationCategory
        .MISINFORMATION
        .value
    ): (
        "fabricated report",
        "fabricated headline",
        "fake public announcement",
        "manipulated headline",
        "manipulated report",
        "manipulated video presented as real",
        "unverified claim presented as fact",
        "confirmed without evidence",
        "secret cure",
        "government is hiding the cure",
        "media will not tell you",
        "false election result",
        "fake election result",
        "false medical claim",
        "fake medical claim",
        "made-up news report",
    ),

    (
        ModerationCategory
        .SPAM_SCAM_PHISHING
        .value
    ): (
        "send your otp",
        "share your otp",
        "send your password",
        "share your password",
        "bank account is blocked",
        "account has been blocked",
        "account is suspended",
        "verify your banking identity",
        "processing fee",
        "guaranteed return",
        "double your money",
        "lottery winnings",
        "claim your prize",
        "gift card payment",
        "cryptocurrency payment",
        "click this suspicious link",
        "unsolicited advertisement",
        "repeated promotion",
        "repeated message",
        "bulk promotional message",
    ),

    (
        ModerationCategory
        .INTELLECTUAL_PROPERTY
        .value
    ): (
        "pirated movie download",
        "pirated software download",
        "download copyrighted material illegally",
        "unauthorized copy for sale",
        "stolen copyrighted work",
        "counterfeit trademark",
        "fake branded product",
        "copyright infringement",
        "trademark infringement",
        "distribute without permission",
    ),

    (
        ModerationCategory
        .MALICIOUS_PROGRAMS
        .value
    ): (
        "download this malware",
        "install this malware",
        "ransomware download",
        "credential stealing software",
        "steal login credentials",
        "malicious payload",
        "computer virus download",
        "trojan download",
        "spyware download",
        "keylogger download",
        "phishing kit download",
        "exploit this computer",
        "compromise this account",
        "disable antivirus",
        "bypass security and steal",
    ),

    (
        ModerationCategory
        .ABUSIVE_WORDS
        .value
    ): (
        "you are an idiot",
        "you are a moron",
        "you are disgusting",
        "you are pathetic",
        "shut up idiot",
        "stupid loser",
        "worthless person",
        "piece of trash",
        "piece of garbage",
        "foolish idiot",
        "you are trash",
        "you are a failure",
    ),
}

CHILD_TERMS = (
    "child",
    "minor",
    "underage",
    "young student",
    "little boy",
    "little girl",
    "school child",
    "teenager",
)

CHILD_RISK_TERMS = (
    "send personal images",
    "send private images",
    "send intimate images",
    "send nude images",
    "keep this secret",
    "private conversation secret",
    "move to a private app",
    "do not tell your parents",
    "don't tell your parents",
    "meet without telling",
    "request personal images",
    "sexual content",
    "sexual picture",
    "sexual video",
    "physically abuse",
    "beat the child",
    "harm the child",
    "hurt the child",
    "groom the child",
)

COMMON_SAFE_CONTEXTS = (
    "awareness",
    "prevention",
    "educational",
    "education",
    "training",
    "documentary",
    "historical discussion",
    "academic discussion",
    "research paper",
    "safety guidance",
    "safety warning",
    "public service announcement",
    "condemn",
    "condemns",
    "condemned",
    "reporting on",
    "news report about",
    "example of",
    "fictional example",
    "hypothetical example",
)

CATEGORY_SAFE_CONTEXTS: dict[
    str,
    tuple[str, ...],
] = {
    (
        ModerationCategory
        .RELIGIOUSLY_OFFENSIVE
        .value
    ): (
        "religious history",
        "religious studies",
        "interfaith education",
        "good-faith criticism",
        "condemns religious hatred",
    ),

    (
        ModerationCategory
        .HATE_SPEECH
        .value
    ): (
        "counterspeech",
        "anti-hate",
        "condemns hate speech",
        "example of hate speech",
        "reporting hate speech",
    ),

    (
        ModerationCategory
        .TERRORISM
        .value
    ): (
        "counter-terrorism",
        "terrorism prevention",
        "condemns terrorism",
        "history of terrorism",
        "reporting on terrorism",
    ),

    (
        ModerationCategory
        .VIOLENT_CONTENT
        .value
    ): (
        "violence prevention",
        "crime report",
        "non-graphic news",
        "fictional violence",
        "gaming footage",
        "historical battle",
    ),

    (
        ModerationCategory
        .DANGEROUS_CONTENT
        .value
    ): (
        "do not try this",
        "trained professional",
        "professional supervision",
        "safety demonstration",
        "danger warning",
    ),

    (
        ModerationCategory
        .GRAPHIC_SEXUAL_CONTENT
        .value
    ): (
        "medical education",
        "medical illustration",
        "sexual health education",
        "health education",
        "museum artwork",
        "classical sculpture",
        "recognized artwork",
        "anatomy lesson",
    ),

    (
        ModerationCategory
        .SEXUAL_HARASSMENT
        .value
    ): (
        "sexual harassment awareness",
        "report sexual harassment",
        "reported sexual harassment",
        "condemns sexual harassment",
    ),

    (
        ModerationCategory
        .CYBERBULLYING
        .value
    ): (
        "cyberbullying awareness",
        "anti-bullying",
        "report bullying",
        "reported harassment",
        "condemns harassment",
    ),

    (
        ModerationCategory
        .INVASION_OF_PRIVACY
        .value
    ): (
        "privacy awareness",
        "consent education",
        "report a privacy violation",
        "reported privacy violation",
    ),

    (
        ModerationCategory
        .PRIVATE_INFORMATION
        .value
    ): (
        "redacted",
        "fictional phone number",
        "fictional email",
        "sample identity card",
        "test card number",
        "privacy awareness",
    ),

    (
        ModerationCategory
        .IDENTITY_THEFT
        .value
    ): (
        "identity theft awareness",
        "impersonation warning",
        "report impersonation",
        "reported fake account",
    ),

    (
        ModerationCategory
        .MISINFORMATION
        .value
    ): (
        "fact check",
        "fact-check",
        "verified correction",
        "corrects a false claim",
        "correction of a false claim",
        "satire",
        "parody",
        "clearly fictional",
    ),

    (
        ModerationCategory
        .SPAM_SCAM_PHISHING
        .value
    ): (
        "spam awareness",
        "phishing awareness",
        "scam prevention",
        "never share your otp",
        "do not share your otp",
        "never share your password",
        "do not share your password",
        "report this scam",
        "not a scam",
    ),

    (
        ModerationCategory
        .INTELLECTUAL_PROPERTY
        .value
    ): (
        "copyright education",
        "intellectual property education",
        "licensed use",
        "public domain",
        "authorized copy",
        "fair dealing",
    ),

    (
        ModerationCategory
        .MALICIOUS_PROGRAMS
        .value
    ): (
        "defensive security",
        "cybersecurity education",
        "malware analysis",
        "security research",
        "authorized penetration test",
        "malware prevention",
    ),

    (
        ModerationCategory
        .ABUSIVE_WORDS
        .value
    ): (
        "abuse awareness",
        "anti-abuse",
        "reported abusive language",
        "example of an insult",
        "condemns the insult",
    ),

    (
        ModerationCategory
        .CHILD_EXPLOITATION
        .value
    ): (
        "child safety education",
        "child protection training",
        "report child exploitation",
        "child abuse prevention",
        "grooming prevention",
    ),
}

DIRECT_HARM_OR_ACTION_PATTERNS = (
    "send your",
    "share your",
    "click",
    "pay",
    "transfer",
    "contact me",
    "call me",
    "message me",
    "join",
    "download",
    "install",
    "attack",
    "kill",
    "hurt",
    "shoot",
    "stab",
    "destroy",
    "burn",
    "buy",
    "sell",
    "do not tell",
    "don't tell",
    "keep this secret",
)

NEGATION_PATTERNS = (
    "not",
    "never",
    "do not",
    "don't",
    "does not",
    "is not",
    "isn't",
    "should not",
    "must not",
    "against",
    "condemn",
    "avoid",
    "prevent",
    "warning",
)

PAN_PATTERN = re.compile(
    r"\b[A-Z]{5}[0-9]{4}[A-Z]\b",
    flags=re.IGNORECASE,
)

AADHAAR_PATTERN = re.compile(
    r"(?<!\d)\d{4}\s?\d{4}\s?\d{4}(?!\d)"
)

CARD_PATTERN = re.compile(
    r"(?<!\d)(?:\d[\s\-]?){13,19}(?!\d)"
)

EMAIL_PATTERN = re.compile(
    r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b",
    flags=re.IGNORECASE,
)

PHONE_PATTERN = re.compile(
    r"(?<!\d)(?:\+?\d[\d\s\-]{7,}\d)(?!\d)"
)


def normalize_text(
    text: str,
) -> str:
    normalized = (
        unicodedata.normalize(
            "NFKC",
            text,
        )
    )

    normalized = (
        normalized.casefold()
    )

    normalized = re.sub(
        r"\s+",
        " ",
        normalized,
    )

    return normalized.strip()


def unique_values(
    values: Iterable[str],
) -> list[str]:
    return list(
        dict.fromkeys(
            values
        )
    )


def phrase_is_present(
    normalized_text: str,
    phrase: str,
) -> bool:
    normalized_phrase = (
        normalize_text(
            phrase
        )
    )

    if (
        not normalized_phrase
        or normalized_phrase
        not in normalized_text
    ):
        return False

    escaped_phrase = re.escape(
        normalized_phrase
    )

    left_boundary = (
        r"(?<!\w)"
        if normalized_phrase[
            0
        ].isalnum()
        else ""
    )

    right_boundary = (
        r"(?!\w)"
        if normalized_phrase[
            -1
        ].isalnum()
        else ""
    )

    return bool(
        re.search(
            left_boundary
            + escaped_phrase
            + right_boundary,
            normalized_text,
            flags=re.UNICODE,
        )
    )


def find_phrases(
    normalized_text: str,
    phrases: Iterable[str],
) -> list[str]:
    return [
        phrase
        for phrase in phrases
        if phrase_is_present(
            normalized_text,
            phrase,
        )
    ]


def has_direct_action(
    normalized_text: str,
) -> bool:
    direct_actions_that_remain_harmful = {
        "do not tell",
        "don't tell",
        "keep this secret",
    }

    negation_before_action_pattern = re.compile(
        r"""
        (?:
            \bnever
            |
            \bnot
            |
            \bdo\s+not
            |
            \bdon't
            |
            \bdoes\s+not
            |
            \bis\s+not
            |
            \bisn't
            |
            \bshould\s+not
            |
            \bmust\s+not
            |
            \bavoid
            |
            \bprevent
            |
            \bpreventing
            |
            \bwarn(?:ing|ed)?\s+(?:people\s+)?not\s+to
        )
        (?:\s+\w+){0,2}
        \s*$
        """,
        flags=(
            re.IGNORECASE
            | re.VERBOSE
        ),
    )

    for action_phrase in (
        DIRECT_HARM_OR_ACTION_PATTERNS
    ):
        normalized_action = normalize_text(
            action_phrase
        )

        if not normalized_action:
            continue

        escaped_action = re.escape(
            normalized_action
        )

        left_boundary = (
            r"(?<!\w)"
            if normalized_action[0].isalnum()
            else ""
        )

        right_boundary = (
            r"(?!\w)"
            if normalized_action[-1].isalnum()
            else ""
        )

        matches = re.finditer(
            left_boundary
            + escaped_action
            + right_boundary,
            normalized_text,
            flags=re.UNICODE,
        )

        for match in matches:
            if (
                normalized_action
                in direct_actions_that_remain_harmful
            ):
                return True

            preceding_text = normalized_text[
                max(0, match.start() - 80):
                match.start()
            ]

            action_is_negated = bool(
                negation_before_action_pattern.search(
                    preceding_text
                )
            )

            if action_is_negated:
                continue

            return True

    return False


def determine_context_flags(
    category: str,
    normalized_text: str,
) -> list[str]:
    context_flags: list[str] = []

    common_matches = find_phrases(
        normalized_text,
        COMMON_SAFE_CONTEXTS,
    )

    category_matches = find_phrases(
        normalized_text,
        CATEGORY_SAFE_CONTEXTS.get(
            category,
            (),
        ),
    )

    negation_matches = find_phrases(
        normalized_text,
        NEGATION_PATTERNS,
    )

    if common_matches:
        context_flags.append(
            "context:educational_or_reporting"
        )

    if category_matches:
        context_flags.append(
            "context:category_exception"
        )

    if negation_matches:
        context_flags.append(
            "context:negation_or_condemnation"
        )

    if has_direct_action(
        normalized_text
    ):
        context_flags.append(
            "context:direct_action"
        )

    return context_flags


def detect_private_information(
    normalized_text: str,
) -> list[str]:
    matches: list[str] = []

    privacy_language = find_phrases(
        normalized_text,
        (
            "aadhaar",
            "aadhar",
            "pan card",
            "voter card",
            "driving license",
            "identity card",
            "credit card",
            "debit card",
            "bank statement",
            "bank passbook",
            "phone number",
            "email address",
            "home address",
            "publish",
            "leak",
            "expose",
        ),
    )

    if privacy_language:
        if PAN_PATTERN.search(
            normalized_text
        ):
            matches.append(
                "detected_pan_format"
            )

        if AADHAAR_PATTERN.search(
            normalized_text
        ):
            matches.append(
                "detected_aadhaar_format"
            )

        if CARD_PATTERN.search(
            normalized_text
        ):
            matches.append(
                "detected_card_number_format"
            )

        if EMAIL_PATTERN.search(
            normalized_text
        ):
            matches.append(
                "detected_email_address"
            )

        if PHONE_PATTERN.search(
            normalized_text
        ):
            matches.append(
                "detected_phone_number"
            )

    return matches


def find_category_matches(
    normalized_text: str,
) -> dict[
    str,
    list[str],
]:
    matches: dict[
        str,
        list[str],
    ] = {}

    child_matches = find_phrases(
        normalized_text,
        CHILD_TERMS,
    )

    child_risk_matches = (
        find_phrases(
            normalized_text,
            CHILD_RISK_TERMS,
        )
    )

    if (
        child_matches
        and child_risk_matches
    ):
        category = (
            ModerationCategory
            .CHILD_EXPLOITATION
            .value
        )

        matches[
            category
        ] = unique_values(
            child_matches
            + child_risk_matches
            + determine_context_flags(
                category,
                normalized_text,
            )
        )

    for category, signals in (
        RULES.items()
    ):
        category_matches = (
            find_phrases(
                normalized_text,
                signals,
            )
        )

        if category_matches:
            matches[
                category
            ] = unique_values(
                category_matches
                + determine_context_flags(
                    category,
                    normalized_text,
                )
            )

    private_information_matches = (
        detect_private_information(
            normalized_text
        )
    )

    if private_information_matches:
        category = (
            ModerationCategory
            .PRIVATE_INFORMATION
            .value
        )

        existing_matches = (
            matches.get(
                category,
                [],
            )
        )

        matches[
            category
        ] = unique_values(
            existing_matches
            + private_information_matches
            + determine_context_flags(
                category,
                normalized_text,
            )
        )

    return matches


def select_category(
    matches: dict[
        str,
        list[str],
    ],
) -> str:
    for category in (
        CATEGORY_PRIORITY
    ):
        if category in matches:
            return category

    return NORMAL_CATEGORY


def context_allows_content(
    category: str,
    matched_signals: list[str],
) -> bool:
    has_safe_context = (
        "context:educational_or_reporting"
        in matched_signals
        or "context:category_exception"
        in matched_signals
        or "context:negation_or_condemnation"
        in matched_signals
    )

    direct_action = (
        "context:direct_action"
        in matched_signals
    )

    if category == (
        ModerationCategory
        .CHILD_EXPLOITATION
        .value
    ):
        return False

    if category == (
        ModerationCategory
        .PRIVATE_INFORMATION
        .value
    ):
        return (
            has_safe_context
            and not direct_action
        )

    return (
        has_safe_context
        and not direct_action
    )


def apply_context_policy(
    category: str,
    source_context: str,
    confidence: float,
    matched_signals: list[str],
) -> dict:
    del source_context

    normalized_category = (
        normalize_category_name(
            category
        )
    )

    policy = get_category_policy(
        normalized_category
    )

    safe_context = (
        context_allows_content(
            normalized_category,
            matched_signals,
        )
    )

    if normalized_category == (
        NORMAL_CATEGORY
    ):
        return {
            "severity": "None",
            "action": "Allow",
            "human_review_required": False,
            "reason": (
                "No sufficiently supported "
                "moderation violation was "
                "detected."
            ),
        }

    if normalized_category == (
        ModerationCategory
        .CHILD_EXPLOITATION
        .value
    ):
        return {
            "severity": "Critical",
            "action": (
                "Block and immediately escalate"
            ),
            "human_review_required": True,
            "reason": (
                "The content contains combined "
                "child-safety and exploitation, "
                "grooming, sexual, or physical "
                "harm indicators."
            ),
        }

    if safe_context:
        if normalized_category == (
            ModerationCategory
            .VIOLENT_CONTENT
            .value
        ):
            return {
                "severity": "Low",
                "action": (
                    "Allow with sensitive-content "
                    "warning"
                ),
                "human_review_required": False,
                "reason": (
                    "Violence-related material "
                    "appears in non-promotional "
                    "reporting, education, history, "
                    "fiction, gaming, or prevention "
                    "context."
                ),
            }

        if normalized_category == (
            ModerationCategory
            .GRAPHIC_SEXUAL_CONTENT
            .value
        ):
            return {
                "severity": "Low",
                "action": "Allow",
                "human_review_required": False,
                "reason": (
                    "Potentially sensitive anatomy "
                    "or sexual terminology appears "
                    "in legitimate medical, health, "
                    "educational, artistic, or "
                    "museum context."
                ),
            }

        if normalized_category == (
            ModerationCategory
            .MISINFORMATION
            .value
        ):
            return {
                "severity": "None",
                "action": "Allow",
                "human_review_required": False,
                "reason": (
                    "The content appears to correct, "
                    "fact-check, condemn, satirize, "
                    "or report a false claim rather "
                    "than endorse it."
                ),
            }

        if normalized_category == (
            ModerationCategory
            .MALICIOUS_PROGRAMS
            .value
        ):
            return {
                "severity": "Low",
                "action": "Allow",
                "human_review_required": (
                    confidence < 0.80
                ),
                "reason": (
                    "Security terminology appears "
                    "in defensive, educational, "
                    "research, or prevention context."
                ),
            }

        if normalized_category == (
            ModerationCategory
            .SPAM_SCAM_PHISHING
            .value
        ):
            return {
                "severity": "None",
                "action": "Allow",
                "human_review_required": False,
                "reason": (
                    "Spam or phishing terminology "
                    "appears in warning, awareness, "
                    "prevention, or negated context."
                ),
            }

        return {
            "severity": "Low",
            "action": (
                "Allow with context label"
            ),
            "human_review_required": (
                confidence < 0.80
            ),
            "reason": (
                "Potential policy terminology "
                "appears in reporting, education, "
                "prevention, condemnation, "
                "quotation, or another allowed "
                "context."
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
        "reason": (
            "The content matches the conditions "
            f"for {normalized_category} under "
            "the configured moderation policy."
        ),
    }


def count_policy_signals(
    matched_signals: list[str],
) -> int:
    return sum(
        not signal.startswith(
            "context:"
        )
        for signal in matched_signals
    )


def moderate_text(
    text: str,
    source_context: str,
) -> dict:
    normalized_text = (
        normalize_text(
            text
        )
    )

    if not normalized_text:
        return {
            "category": (
                NORMAL_CATEGORY
            ),
            "severity": "None",
            "action": "Allow",
            "confidence": 0.50,
            "human_review_required": True,
            "reason": (
                "No readable text was available "
                "for moderation."
            ),
            "matched_signals": [],
        }

    matches = (
        find_category_matches(
            normalized_text
        )
    )

    category = select_category(
        matches
    )

    matched_signals = (
        matches.get(
            category,
            [],
        )
    )

    if category == (
        NORMAL_CATEGORY
    ):
        confidence = 0.70

    else:
        signal_count = max(
            1,
            count_policy_signals(
                matched_signals
            ),
        )

        confidence = min(
            0.96,
            0.66
            + (
                0.07
                * signal_count
            ),
        )

        if (
            "context:educational_or_reporting"
            in matched_signals
            or "context:category_exception"
            in matched_signals
            or "context:negation_or_condemnation"
            in matched_signals
        ):
            confidence = max(
                0.60,
                confidence - 0.08,
            )

    policy = apply_context_policy(
        category=category,
        source_context=(
            source_context
        ),
        confidence=confidence,
        matched_signals=(
            matched_signals
        ),
    )

    if (
        policy["action"] == "Allow"
        and policy["severity"] == "None"
    ):
        category = (
            NORMAL_CATEGORY
        )

    return {
        "category": (
            normalize_category_name(
                category
            )
        ),
        "severity": (
            policy["severity"]
        ),
        "action": (
            policy["action"]
        ),
        "confidence": round(
            confidence,
            2,
        ),
        "human_review_required": (
            policy[
                "human_review_required"
            ]
        ),
        "reason": (
            policy["reason"]
        ),
        "matched_signals": (
            matched_signals
        ),
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
            "Extracted text:\n"
            f"{extracted_text.strip()}"
        )

    if ocr_text.strip():
        sections.append(
            "OCR text:\n"
            f"{ocr_text.strip()}"
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

    return "\n\n".join(
        sections
    )