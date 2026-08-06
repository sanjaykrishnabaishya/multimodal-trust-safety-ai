from dataclasses import dataclass
from enum import Enum


POLICY_VERSION = "2026.08"


class ModerationCategory(
    str,
    Enum,
):
    RELIGIOUSLY_OFFENSIVE = (
        "Religiously Offensive Content"
    )

    HATE_SPEECH = (
        "Hate Speech & Discrimination"
    )

    TERRORISM = (
        "Terrorism & Extremism"
    )

    VIOLENT_CONTENT = (
        "Violent Content"
    )

    DANGEROUS_CONTENT = (
        "Dangerous Content"
    )

    GRAPHIC_SEXUAL_CONTENT = (
        "Graphic, Obscene & Sexual Content"
    )

    SEXUAL_HARASSMENT = (
        "Sexual Harassment"
    )

    CYBERBULLYING = (
        "Cyberbullying & Harassment"
    )

    INVASION_OF_PRIVACY = (
        "Invasion of Privacy"
    )

    ILLEGAL_ACTIVITIES = (
        "Illegal Activities"
    )

    PRIVATE_INFORMATION = (
        "Publishing Private Information"
    )

    IDENTITY_THEFT = (
        "Identity Theft & Impersonation"
    )

    MISINFORMATION = (
        "Misinformation & Fake News"
    )

    SPAM_SCAM_PHISHING = (
        "Spam, Scam & Phishing"
    )

    INTELLECTUAL_PROPERTY = (
        "Intellectual Property Infringement"
    )

    MALICIOUS_PROGRAMS = (
        "Malicious Programs"
    )

    ABUSIVE_WORDS = (
        "Abusive Words"
    )

    CHILD_EXPLOITATION = (
        "Child Exploitation"
    )

    NORMAL_IGNORE = (
        "Normal/Ignore"
    )


@dataclass(frozen=True)
class CategoryPolicy:
    category: ModerationCategory
    default_severity: str
    default_action: str
    human_review_required: bool

    moderation_conditions: tuple[
        str,
        ...,
    ]

    allow_conditions: tuple[
        str,
        ...,
    ] = ()

    review_conditions: tuple[
        str,
        ...,
    ] = ()

    notes: tuple[
        str,
        ...,
    ] = ()


CATEGORY_POLICIES: dict[
    ModerationCategory,
    CategoryPolicy,
] = {
    ModerationCategory.RELIGIOUSLY_OFFENSIVE: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .RELIGIOUSLY_OFFENSIVE
            ),
            default_severity="High",
            default_action=(
                "Remove and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Religious names, symbols, "
                    "emblems, books, flags, "
                    "statues, or buildings are "
                    "morphed, destroyed, damaged, "
                    "mutilated, mocked, or "
                    "desecrated."
                ),
                (
                    "Gods, religious deities, "
                    "prophets, figureheads, "
                    "reincarnations, or religious "
                    "leaders are abused or "
                    "described using denigrating "
                    "language."
                ),
            ),
            allow_conditions=(
                (
                    "Neutral educational, "
                    "historical, documentary, or "
                    "news discussion that does not "
                    "attack a religion or its "
                    "followers."
                ),
                (
                    "Good-faith criticism of ideas "
                    "that does not demean people "
                    "because of their religion."
                ),
            ),
            review_conditions=(
                (
                    "Satire, artistic expression, "
                    "or disputed religious context "
                    "where intent is unclear."
                ),
            ),
        )
    ),

    ModerationCategory.HATE_SPEECH: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .HATE_SPEECH
            ),
            default_severity="High",
            default_action=(
                "Remove and escalate"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Unsubstantiated, inflammatory, "
                    "fear-mongering, instigating, "
                    "excessively provoking, or "
                    "demeaning claims target a "
                    "person or group based on "
                    "religion, caste, nationality, "
                    "ethnicity, or another protected "
                    "characteristic."
                ),
                (
                    "Content calls to destroy, "
                    "exclude, block, boycott, "
                    "terminate, or harm a protected "
                    "person or group."
                ),
                (
                    "Dehumanizing or discriminatory "
                    "language is directed at a "
                    "protected person or group."
                ),
            ),
            allow_conditions=(
                (
                    "Counterspeech, reporting, "
                    "education, or condemnation "
                    "that quotes hateful language "
                    "without endorsing it."
                ),
            ),
            review_conditions=(
                (
                    "Quoted, reclaimed, satirical, "
                    "or ambiguous language where "
                    "endorsement is uncertain."
                ),
            ),
        )
    ),

    ModerationCategory.TERRORISM: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .TERRORISM
            ),
            default_severity="Critical",
            default_action=(
                "Block and escalate"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content supports, praises, "
                    "glorifies, recruits for, or "
                    "provides operational assistance "
                    "to a banned terrorist or "
                    "extremist organization."
                ),
                (
                    "Content distributes links, "
                    "propaganda, instructions, or "
                    "resources intended to support "
                    "a banned organization."
                ),
            ),
            allow_conditions=(
                (
                    "Neutral news reporting, "
                    "academic analysis, historical "
                    "discussion, or condemnation "
                    "without praise or assistance."
                ),
            ),
            review_conditions=(
                (
                    "Organization identity or legal "
                    "status is uncertain."
                ),
                (
                    "Content references an "
                    "organization listed by the "
                    "Ministry of Home Affairs, "
                    "Government of India."
                ),
            ),
            notes=(
                (
                    "The banned-organization list "
                    "must be maintained separately "
                    "and reviewed regularly."
                ),
            ),
        )
    ),

    ModerationCategory.VIOLENT_CONTENT: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .VIOLENT_CONTENT
            ),
            default_severity="High",
            default_action=(
                "Block or apply a sensitive-content "
                "warning"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content depicts mutilation, "
                    "torture, decapitation, beating, "
                    "or bodily harm involving a "
                    "human or animal."
                ),
                (
                    "Content depicts scattered, "
                    "splattered, deformed, burned, "
                    "or bloated blood, organs, body "
                    "parts, heads, brains, bones, "
                    "flesh, or eyes."
                ),
                (
                    "The violent depiction may be "
                    "real, artificial, animated, "
                    "or digitally generated."
                ),
            ),
            allow_conditions=(
                (
                    "Violent imagery is sufficiently "
                    "blurred and no graphic details "
                    "remain visible."
                ),
                (
                    "Non-graphic reporting or "
                    "discussion of violence may be "
                    "allowed with an appropriate "
                    "warning."
                ),
            ),
            review_conditions=(
                (
                    "Graphic severity, documentary "
                    "value, or degree of blurring "
                    "is uncertain."
                ),
            ),
        )
    ),

    ModerationCategory.DANGEROUS_CONTENT: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .DANGEROUS_CONTENT
            ),
            default_severity="High",
            default_action=(
                "Remove and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content encourages or "
                    "demonstrates dangerous stunts, "
                    "experiments, or actions not "
                    "performed under appropriate "
                    "professional controls."
                ),
                (
                    "Content depicts or encourages "
                    "actual bodily harm to oneself "
                    "or another person."
                ),
                (
                    "Content asks others to perform "
                    "actions likely to cause injury, "
                    "death, or destruction of "
                    "property."
                ),
            ),
            allow_conditions=(
                (
                    "Professional, educational, or "
                    "safety demonstrations with "
                    "clear precautions and no "
                    "encouragement to imitate."
                ),
            ),
            review_conditions=(
                (
                    "Professional supervision or "
                    "the likelihood of imitation "
                    "cannot be determined."
                ),
            ),
        )
    ),

    ModerationCategory.GRAPHIC_SEXUAL_CONTENT: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .GRAPHIC_SEXUAL_CONTENT
            ),
            default_severity="High",
            default_action=(
                "Block or age-restrict"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Visible genitalia, anus, or "
                    "female nipples are presented "
                    "outside an allowed context."
                ),
                (
                    "Sexual intercourse or sexual "
                    "activity is simulated, implied, "
                    "enacted, animated, morphed, or "
                    "real."
                ),
                (
                    "Sexual objects or sex toys are "
                    "shown or used sexually."
                ),
                (
                    "Sexual content involves "
                    "animals."
                ),
                (
                    "Content depicts sexual "
                    "violence, rape, simulated rape, "
                    "or non-consensual sexual acts."
                ),
                (
                    "Content contains morphed sexual "
                    "imagery or promotes the sale or "
                    "viewing of explicit sexual "
                    "material."
                ),
            ),
            allow_conditions=(
                (
                    "Recognized artwork, sculpture, "
                    "or other established artistic "
                    "material."
                ),
                (
                    "Non-adult-rated film posters "
                    "without explicit sexual detail."
                ),
                (
                    "Medical, health, educational, "
                    "or sexual-health material with "
                    "a clear legitimate purpose."
                ),
                (
                    "Educational or health material "
                    "clearly identifies the "
                    "responsible organization."
                ),
            ),
            review_conditions=(
                (
                    "Age, consent, educational "
                    "purpose, artistic context, or "
                    "degree of explicitness is "
                    "uncertain."
                ),
            ),
        )
    ),

    ModerationCategory.SEXUAL_HARASSMENT: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .SEXUAL_HARASSMENT
            ),
            default_severity="High",
            default_action=(
                "Remove and escalate"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "A person is subjected to "
                    "unwanted requests or demands "
                    "for sexual favors."
                ),
                (
                    "A person receives unwanted "
                    "pornography, sexually explicit "
                    "messages, or sexually colored "
                    "remarks."
                ),
                (
                    "Content contains other "
                    "unwelcome conduct that is "
                    "sexual in nature."
                ),
            ),
            review_conditions=(
                (
                    "Consent, relationship, or "
                    "whether the conduct is welcome "
                    "cannot be determined."
                ),
            ),
        )
    ),

    ModerationCategory.CYBERBULLYING: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .CYBERBULLYING
            ),
            default_severity="Medium",
            default_action=(
                "Limit, flag, and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "A person is repeatedly targeted "
                    "with derogatory comments, "
                    "images, intimidation, or "
                    "humiliation."
                ),
                (
                    "A person is repeatedly "
                    "pressured to provide a phone "
                    "number, send a private message, "
                    "or continue unwanted contact."
                ),
                (
                    "Content coordinates or "
                    "encourages harassment of an "
                    "individual."
                ),
            ),
            allow_conditions=(
                (
                    "Good-faith disagreement or "
                    "criticism that does not include "
                    "targeted abuse or repeated "
                    "unwanted contact."
                ),
            ),
            review_conditions=(
                (
                    "A repeated pattern or the "
                    "target's objection cannot be "
                    "confirmed."
                ),
            ),
            notes=(
                (
                    "Apply the policy consistently "
                    "regardless of the target's "
                    "gender."
                ),
            ),
        )
    ),

    ModerationCategory.INVASION_OF_PRIVACY: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .INVASION_OF_PRIVACY
            ),
            default_severity="High",
            default_action=(
                "Restrict and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Images, audio, or video show "
                    "private or intimate moments "
                    "without the consent of a person "
                    "depicted."
                ),
                (
                    "A depicted person credibly "
                    "alleges that private material "
                    "was recorded or distributed "
                    "without consent."
                ),
            ),
            allow_conditions=(
                (
                    "All depicted adults consented "
                    "to recording and distribution, "
                    "and no other privacy violation "
                    "is present."
                ),
            ),
            review_conditions=(
                (
                    "Identity and consent must be "
                    "authenticated before permanent "
                    "removal when practical."
                ),
            ),
        )
    ),

    ModerationCategory.ILLEGAL_ACTIVITIES: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .ILLEGAL_ACTIVITIES
            ),
            default_severity="High",
            default_action=(
                "Restrict and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Indian national emblems or "
                    "protected names are used "
                    "improperly."
                ),
                (
                    "Content sells or promotes "
                    "unapproved medicines, drugs, "
                    "health products, psychotropic "
                    "substances, or remedies."
                ),
                (
                    "Content facilitates prohibited "
                    "gambling, prostitution, sexual "
                    "services, or the sale of guns "
                    "or weapons."
                ),
                (
                    "Content meaningfully "
                    "facilitates another illegal "
                    "transaction or activity."
                ),
            ),
            allow_conditions=(
                (
                    "News, documentary, educational, "
                    "or prevention content that "
                    "does not facilitate an illegal "
                    "activity."
                ),
            ),
            review_conditions=(
                (
                    "Legality, jurisdiction, or "
                    "whether the content facilitates "
                    "an offense is uncertain."
                ),
            ),
            notes=(
                (
                    "Do not automatically determine "
                    "legal liability; uncertain "
                    "cases require qualified human "
                    "review."
                ),
            ),
        )
    ),

    ModerationCategory.PRIVATE_INFORMATION: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .PRIVATE_INFORMATION
            ),
            default_severity="High",
            default_action=(
                "Remove exposed information and "
                "send for human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content exposes Aadhaar, PAN, "
                    "voter, driving-license, or "
                    "other identity-document data."
                ),
                (
                    "Content exposes personal email "
                    "addresses, phone numbers, "
                    "credit or debit cards, bank "
                    "passbooks, or account "
                    "statements without permission."
                ),
                (
                    "A personal phone number or "
                    "email address is exposed in a "
                    "publicly visible comment and "
                    "reported by the affected user."
                ),
            ),
            allow_conditions=(
                (
                    "Contact details are intentionally "
                    "published for a genuine and "
                    "lawful commercial service."
                ),
                (
                    "Information is fictional, "
                    "redacted, or clearly presented "
                    "as a safe example."
                ),
            ),
            review_conditions=(
                (
                    "Ownership, consent, or whether "
                    "the information is genuinely "
                    "public cannot be determined."
                ),
            ),
            notes=(
                (
                    "Never place complete sensitive "
                    "identifiers in logs, previews, "
                    "RAG documents, or review data."
                ),
            ),
        )
    ),

    ModerationCategory.IDENTITY_THEFT: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .IDENTITY_THEFT
            ),
            default_severity="High",
            default_action=(
                "Flag and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content impersonates another "
                    "person or organization to "
                    "deceive users."
                ),
                (
                    "Content uses another person's "
                    "identity, credentials, or "
                    "likeness fraudulently."
                ),
            ),
            review_conditions=(
                (
                    "Identity ownership or parody "
                    "status must be verified."
                ),
            ),
        )
    ),

    ModerationCategory.MISINFORMATION: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .MISINFORMATION
            ),
            default_severity="Medium",
            default_action=(
                "Flag and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content presents a materially "
                    "false or misleading factual "
                    "claim as true."
                ),
                (
                    "Manipulated or fabricated "
                    "content is used to mislead "
                    "people about a factual matter."
                ),
            ),
            allow_conditions=(
                (
                    "Satire, opinion, correction, "
                    "or clearly labeled fiction "
                    "that is unlikely to mislead."
                ),
                (
                    "Content accurately corrects a "
                    "previously circulated false "
                    "claim."
                ),
            ),
            review_conditions=(
                (
                    "The truth of the claim cannot "
                    "be established automatically."
                ),
                (
                    "The claim concerns health, "
                    "public safety, elections, or "
                    "another high-impact topic."
                ),
            ),
        )
    ),

    ModerationCategory.SPAM_SCAM_PHISHING: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .SPAM_SCAM_PHISHING
            ),
            default_severity="High",
            default_action=(
                "Block, warn, or limit distribution"
            ),
            human_review_required=False,
            moderation_conditions=(
                (
                    "An unsolicited message or "
                    "comment has no meaningful "
                    "connection to the surrounding "
                    "content."
                ),
                (
                    "Content requests money "
                    "transfers, donations, OTPs, "
                    "passwords, banking credentials, "
                    "or other authentication data."
                ),
                (
                    "Content promotes multi-level "
                    "marketing, network marketing, "
                    "get-rich-quick schemes, or "
                    "deceptive investment offers."
                ),
                (
                    "Content promotes suspicious "
                    "pornography, dating, travel, "
                    "hotel, shopping, or extreme "
                    "discount offers."
                ),
                (
                    "Content contains meaningless "
                    "gibberish, random numbers, "
                    "repetition, deceptive links, "
                    "or manufactured urgency."
                ),
                (
                    "Multiple multilingual spam "
                    "signals occur together with "
                    "promotional, financial, link, "
                    "contact, or urgency indicators."
                ),
            ),
            allow_conditions=(
                (
                    "A legitimate transactional, "
                    "commercial, charity, or service "
                    "message is expected and does "
                    "not request sensitive data."
                ),
                (
                    "A single dictionary term "
                    "appears in an ordinary, "
                    "non-promotional context."
                ),
            ),
            review_conditions=(
                (
                    "The message may be legitimate "
                    "but identity, consent, or offer "
                    "authenticity cannot be verified."
                ),
            ),
            notes=(
                (
                    "Spam dictionary matches are "
                    "weighted supporting evidence, "
                    "not automatic proof of spam."
                ),
                (
                    "Terms in the spam exclusion "
                    "list must contribute no spam "
                    "score."
                ),
            ),
        )
    ),

    ModerationCategory.INTELLECTUAL_PROPERTY: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .INTELLECTUAL_PROPERTY
            ),
            default_severity="Medium",
            default_action=(
                "Flag and send for "
                "human review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content appears to distribute "
                    "or reproduce protected material "
                    "without authorization."
                ),
                (
                    "Content appears to misuse a "
                    "trademark, copyrighted work, "
                    "or other protected intellectual "
                    "property."
                ),
            ),
            allow_conditions=(
                (
                    "Authorized use, public-domain "
                    "material, licensed use, or "
                    "legitimate quotation and "
                    "commentary."
                ),
            ),
            review_conditions=(
                (
                    "Ownership, authorization, fair "
                    "dealing, or legal status must "
                    "be assessed by a qualified "
                    "reviewer."
                ),
            ),
        )
    ),

    ModerationCategory.MALICIOUS_PROGRAMS: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .MALICIOUS_PROGRAMS
            ),
            default_severity="Critical",
            default_action=(
                "Block and send for "
                "security review"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content distributes, promotes, "
                    "or provides access to malware, "
                    "ransomware, credential theft, "
                    "or other malicious software."
                ),
                (
                    "Content provides operational "
                    "instructions intended to "
                    "compromise devices, accounts, "
                    "or networks."
                ),
            ),
            allow_conditions=(
                (
                    "Defensive security education "
                    "that does not provide harmful "
                    "payloads or facilitate abuse."
                ),
            ),
            review_conditions=(
                (
                    "Code intent or security context "
                    "cannot be determined safely."
                ),
            ),
        )
    ),

    ModerationCategory.ABUSIVE_WORDS: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .ABUSIVE_WORDS
            ),
            default_severity="Medium",
            default_action=(
                "Remove or limit distribution"
            ),
            human_review_required=False,
            moderation_conditions=(
                (
                    "Swear words, abusive terms, "
                    "or denigrating language are "
                    "directed at a person."
                ),
                (
                    "Abusive words are intentionally "
                    "obfuscated using misspellings, "
                    "numbers, symbols, or special "
                    "characters."
                ),
            ),
            allow_conditions=(
                (
                    "Non-targeted quotation, "
                    "education, reporting, or "
                    "self-referential language "
                    "without harassment."
                ),
            ),
            review_conditions=(
                (
                    "Meaning, target, quotation, or "
                    "linguistic context is unclear."
                ),
            ),
        )
    ),

    ModerationCategory.CHILD_EXPLOITATION: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .CHILD_EXPLOITATION
            ),
            default_severity="Critical",
            default_action=(
                "Block and immediately escalate"
            ),
            human_review_required=True,
            moderation_conditions=(
                (
                    "Content sexually exploits, "
                    "sexualizes, solicits, grooms, "
                    "or endangers a child."
                ),
                (
                    "Content depicts or encourages "
                    "physical abuse, beating, or "
                    "harm involving a child."
                ),
                (
                    "Content requests secrecy, "
                    "private contact, sexual "
                    "material, or an unsafe meeting "
                    "with a child."
                ),
            ),
            allow_conditions=(
                (
                    "Child-safety education, "
                    "prevention, reporting, or "
                    "support material that contains "
                    "no exploitative media and does "
                    "not facilitate abuse."
                ),
            ),
            review_conditions=(
                (
                    "Age, intent, relationship, or "
                    "risk to a child is uncertain."
                ),
            ),
            notes=(
                (
                    "Never store, reproduce, or "
                    "display suspected child sexual "
                    "abuse material."
                ),
                (
                    "Store only a minimal safe text "
                    "description required for "
                    "authorized escalation."
                ),
            ),
        )
    ),

    ModerationCategory.NORMAL_IGNORE: (
        CategoryPolicy(
            category=(
                ModerationCategory
                .NORMAL_IGNORE
            ),
            default_severity="None",
            default_action="Allow",
            human_review_required=False,
            moderation_conditions=(
                (
                    "Content is safe, generic, "
                    "ordinary, or does not meet the "
                    "conditions of another category."
                ),
                (
                    "Available evidence is too weak "
                    "to justify a restrictive "
                    "automated decision."
                ),
            ),
            allow_conditions=(
                (
                    "Ordinary conversation, "
                    "educational material, personal "
                    "content, lawful advertising, "
                    "or other benign content."
                ),
            ),
        )
    ),
}


CATEGORY_ALIASES: dict[
    str,
    ModerationCategory,
] = {
    "Child Abuse": (
        ModerationCategory
        .CHILD_EXPLOITATION
    ),

    "Spam": (
        ModerationCategory
        .SPAM_SCAM_PHISHING
    ),

    "Scam": (
        ModerationCategory
        .SPAM_SCAM_PHISHING
    ),

    "Fake News": (
        ModerationCategory
        .MISINFORMATION
    ),

    "Violence": (
        ModerationCategory
        .VIOLENT_CONTENT
    ),

    "Nudity": (
        ModerationCategory
        .GRAPHIC_SEXUAL_CONTENT
    ),

    "Hate Speech": (
        ModerationCategory
        .HATE_SPEECH
    ),

    "Harassment/Cyberbullying": (
        ModerationCategory
        .CYBERBULLYING
    ),

    "Normal/Ignore": (
        ModerationCategory
        .NORMAL_IGNORE
    ),
}


CATEGORY_NAMES: tuple[
    str,
    ...,
] = tuple(
    category.value
    for category in ModerationCategory
)


def get_category_policy(
    category: (
        ModerationCategory
        | str
    ),
) -> CategoryPolicy:
    if isinstance(
        category,
        ModerationCategory,
    ):
        normalized_category = category

    else:
        cleaned_category = (
            category.strip()
        )

        if (
            cleaned_category
            in CATEGORY_ALIASES
        ):
            normalized_category = (
                CATEGORY_ALIASES[
                    cleaned_category
                ]
            )

        else:
            normalized_category = (
                ModerationCategory(
                    cleaned_category
                )
            )

    return CATEGORY_POLICIES[
        normalized_category
    ]


def normalize_category_name(
    category: str,
) -> str:
    return get_category_policy(
        category
    ).category.value


def validate_policy_configuration() -> None:
    configured_categories = set(
        CATEGORY_POLICIES
    )

    expected_categories = set(
        ModerationCategory
    )

    missing_categories = (
        expected_categories
        - configured_categories
    )

    unexpected_categories = (
        configured_categories
        - expected_categories
    )

    if missing_categories:
        raise ValueError(
            "Missing category policies: "
            + ", ".join(
                sorted(
                    category.value
                    for category
                    in missing_categories
                )
            )
        )

    if unexpected_categories:
        raise ValueError(
            "Unexpected category policies: "
            + ", ".join(
                sorted(
                    category.value
                    for category
                    in unexpected_categories
                )
            )
        )

    if (
        len(CATEGORY_NAMES)
        != len(set(CATEGORY_NAMES))
    ):
        raise ValueError(
            "Category names must be unique."
        )

    for category, policy in (
        CATEGORY_POLICIES.items()
    ):
        if (
            policy.category
            != category
        ):
            raise ValueError(
                "Policy category mismatch: "
                f"{category.value}"
            )

        if not (
            policy.default_severity
            .strip()
        ):
            raise ValueError(
                "Default severity is missing "
                f"for {category.value}."
            )

        if not (
            policy.default_action
            .strip()
        ):
            raise ValueError(
                "Default action is missing "
                f"for {category.value}."
            )

        if not (
            policy.moderation_conditions
        ):
            raise ValueError(
                "Moderation conditions are "
                f"missing for {category.value}."
            )


validate_policy_configuration()