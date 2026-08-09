from __future__ import annotations

import re
import unicodedata
from typing import Any


VIOLENT_CATEGORY = "Violent Content"


def normalize_text(text: str) -> str:
    value = unicodedata.normalize("NFKC", str(text or ""))
    value = value.replace("’", "'").replace("‘", "'")
    value = value.replace("“", '"').replace("”", '"')
    value = value.casefold()
    value = re.sub(r"[^\w\s'\-;,.!?]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


HARM_VERB = (
    r"(?:kill|murder|shoot|stab|hurt|harm|attack|beat|strangle|"
    r"burn|dismember|torture|cut|smash|break)"
)

TARGET = (
    r"(?:you|him|her|them|that\s+(?:man|woman|person)|"
    r"your\s+(?:brother|sister|mother|father|family)|"
    r"your\s+(?:jaw|face|arms?|legs?)|"
    r"his\s+(?:jaw|face|legs?)|her\s+(?:jaw|face|legs?))"
)


DIRECT_THREAT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "first_person_future_harm",
        re.compile(
            rf"\b(?:i|we)\s+(?:will|shall|am\s+going\s+to|are\s+going\s+to|"
            rf"plan\s+to|intend\s+to|want\s+to|swear\s+i\s+will)\s+"
            rf"{HARM_VERB}\s+{TARGET}\b"
        ),
    ),
    (
        "approaching_to_harm",
        re.compile(
            rf"\b(?:i\s+am|we\s+are)\s+(?:coming|waiting)\b[^.!?]{{0,45}}"
            rf"\bto\s+{HARM_VERB}\s+{TARGET}\b"
        ),
    ),
    (
        "incitement_to_harm",
        re.compile(
            rf"\b(?:someone\s+should|go|let\s+us|let's|everyone\s+should)\s+"
            rf"{HARM_VERB}\s+{TARGET}\b"
        ),
    ),
    (
        "deserves_lethal_harm",
        re.compile(
            rf"\b(?:he|she|they|that\s+(?:man|woman|person))\s+"
            rf"deserves\s+to\s+be\s+"
            rf"(?:{HARM_VERB}(?:ed)?|beaten)\b"
        ),
    ),
    (
        "weapon_approach_threat",
        re.compile(
            r"\b(?:i|we)\s+have\s+(?:a\s+)?(?:gun|knife|weapon)\b"
            r"[^.!?]{0,55}\b(?:coming\s+for|waiting\s+for)\s+you\b"
        ),
    ),
    (
        "conditional_family_harm",
        re.compile(
            r"\b(?:your|his|her)\s+family\s+(?:will|is\s+going\s+to)\s+"
            r"be\s+(?:hurt|harmed|killed|attacked)\b"
        ),
    ),
    (
        "dead_when_found",
        re.compile(
            r"\byou(?:'re|\s+are)\s+dead\s+when\s+(?:i|we)\s+find\s+you\b"
        ),
    ),
    (
        "watch_your_back",
        re.compile(
            r"\bwatch\s+your\s+back\b[^.!?]{0,80}\b"
            r"(?:break|smash|hurt|kill|shoot|stab|attack)\b"
        ),
    ),
    (
        "weapon_plan",
        re.compile(
            rf"\b(?:bringing|taking|carrying)\s+(?:a\s+)?"
            rf"(?:gun|knife|weapon)\b[^.!?]{{0,45}}\bto\s+{HARM_VERB}\s+{TARGET}\b"
        ),
    ),
    (
        "burn_occupied_property",
        re.compile(
            r"\b(?:i|we)\s+(?:will|are\s+going\s+to)\s+burn\s+"
            r"(?:your|his|her|their)\s+(?:house|home)\b"
            r"[^.!?]{0,55}\b(?:inside|in\s+it)\b"
        ),
    ),
)


GRAPHIC_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("decapitation", re.compile(r"\b(?:decapitated|beheaded)\s+(?:body|person|victim)\b")),
    ("severed_parts", re.compile(r"\bsevered\s+(?:body\s+parts?|limbs?|head)\b")),
    ("visible_organs", re.compile(r"\b(?:visible|exposed)\s+(?:internal\s+)?organs?\b")),
    ("bloody_mutilation", re.compile(r"\bbloody\s+mutilation\b")),
    ("torture_depiction", re.compile(r"\b(?:person|victim|animal)\s+(?:is\s+)?being\s+tortured\b")),
    ("burned_body", re.compile(r"\bburned\s+(?:body|corpse)\b")),
    ("bloated_corpse", re.compile(r"\bbloated\s+(?:body|corpse)\b")),
    ("dismemberment", re.compile(r"\b(?:dismembered|dismemberment)\b")),
    ("exposed_bone_flesh", re.compile(r"\bexposed\s+bone\b[^.!?]{0,45}\b(?:torn\s+)?flesh\b")),
)


DEPICTION_PATTERN = re.compile(
    r"\b(?:image|picture|photo(?:graph)?|video|clip|recording|footage|"
    r"frame|scene|camera|animation|generated\s+image|uploaded\s+(?:image|"
    r"picture|video|recording)|visibly|visible|shows?|depicts?|displays?|"
    r"focuses?\s+on|captures?|portrays?)\b"
)


GRAPHIC_EVENT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("mutilation_event", re.compile(r"\b(?:mutilat(?:e|ed|ion)|maim(?:ed|ing)?)\b")),
    ("dismemberment_event", re.compile(r"\b(?:dismember(?:ed|ing|ment)?)\b")),
    ("decapitation_event", re.compile(r"\b(?:decapitat(?:e|ed|ion)|behead(?:ed|ing)?)\b")),
    ("torture_event", re.compile(r"\b(?:tortur(?:e|ed|ing)|skinned\s+alive)\b")),
    ("body_torn_apart", re.compile(r"\b(?:body|corpse|victim|person|animal)\b[^.!?]{0,45}\b(?:torn|cut)\s+(?:apart|into\s+pieces)\b")),
    ("body_part_removal", re.compile(r"\b(?:remov(?:e|ed|ing)|cut(?:ting)?\s+off)\b[^.!?]{0,40}\b(?:head|eye|finger|hand|arm|leg|limb|body\s+part)s?\b")),
    ("severe_burning", re.compile(r"\b(?:burned|burnt|charred)\b[^.!?]{0,40}\b(?:body|corpse|remains|victim|person|recognition)\b")),
)


ANATOMY_PATTERN = re.compile(
    r"\b(?:body|corpse|remains|head|brain|skull|eye|organ|intestine|"
    r"limb|arm|leg|hand|finger|bone|flesh|torso|abdomen|skin|wound)s?\b"
)


GRAPHIC_STATE_PATTERN = re.compile(
    r"\b(?:severed|detached|exposed|protruding|crushed|shattered|"
    r"splattered|scattered|bloody|blood-covered|torn|open|removed|"
    r"mutilated|deformed|burned|burnt|charred|bloated)\b"
)


VICTIM_HARM_PATTERN = re.compile(
    r"\b(?:victim|captive|prisoner|person|human|animal)\b"
    r"[^.!?]{0,70}\b(?:beaten|tortured|mutilated|dismembered|"
    r"burned|cut|crushed|skinned|decapitated)\b"
)


CONTEXT_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("news", re.compile(r"\b(?:non-graphic\s+)?news\s+(?:report|segment|coverage)\b")),
    ("crime_report", re.compile(r"\bcrime\s+report\b")),
    ("documentary", re.compile(r"\bdocumentary\b")),
    ("history", re.compile(r"\b(?:historical|history\s+(?:class|lesson)|museum\s+lesson)\b")),
    ("fiction", re.compile(r"\b(?:fictional|novel|screenplay|story)\b")),
    ("gaming", re.compile(r"\b(?:gaming\s+footage|video\s+game|animated\s+characters?)\b")),
    ("education", re.compile(r"\b(?:teacher|classroom|media-literacy|media\s+literacy)\b")),
    ("prevention", re.compile(r"\b(?:violence|threat)\s+prevention\b")),
    ("safety_course", re.compile(r"\b(?:safety\s+course|safety\s+training)\b")),
    ("police_report", re.compile(r"\b(?:reported|quotes?|quoted)\b[^.!?]{0,75}\b(?:police|report)\b")),
)


METAPHOR_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("performance_killed_it", re.compile(r"\bkilled\s+it\b")),
    ("competition_metaphor", re.compile(r"\b(?:murdered|killed|destroyed)\s+the\s+competition\b")),
    ("software_killing", re.compile(r"\b(?:bug|process|software|application)\b[^.!?]{0,40}\bkilling\b")),
    ("problem_attack", re.compile(r"\battacked\s+the\s+(?:problem|question|task)\b")),
    ("killer_flavour", re.compile(r"\bkiller\s+(?:flavou?r|taste|performance|feature)\b")),
    ("slayed_audience", re.compile(r"\bslayed\s+the\s+(?:audience|crowd)\b")),
    ("sports_shot", re.compile(r"\b(?:shot|attack)\b[^.!?]{0,35}\b(?:goal|defen[cs]e|match|game|second\s+half)\b")),
    ("photography", re.compile(r"\b(?:photographer|camera)\b[^.!?]{0,35}\bshot\b|\bshot\s+the\s+(?:wedding|portrait|ceremony)\b")),
    ("kill_process", re.compile(r"\bkill\s+the\s+(?:running\s+)?(?:computer\s+)?process\b")),
    ("pesticide", re.compile(r"\b(?:pesticide|herbicide)\b[^.!?]{0,45}\bkills?\s+(?:weeds|pests|insects)\b")),
)


NEGATED_PREVENTION_PATTERN = re.compile(
    r"\b(?:do\s+not|don't|never|must\s+not|should\s+not)\b"
    r"[^.!?]{0,70}\b(?:threaten|attack|hurt|harm|kill|shoot|stab)\b"
)


DOCUMENTED_THREAT_REPORT_PATTERN = re.compile(
    r"\b(?:reported|forwarded)\s+the\s+(?:message|threat)\b"
    r"[^.!?]{0,90}\b(?:to\s+)?(?:the\s+)?police\b"
)


PREVENTED_HARM_PATTERN = re.compile(
    r"\b(?:police|security|authorities|staff|bystanders?)\b"
    r"[^.!?]{0,60}\b(?:prevented|stopped|interrupted|avoided)\b"
    r"[^.!?]{0,70}\b(?:attack|assault|violence|harm|injury|injured|hurt)\b"
)


VIOLENCE_MATERIAL_PATTERN = re.compile(
    r"\b(?:armed\s+attack|violent\s+attack|graphic\s+violence|"
    r"historical\s+battle|person\s+being\s+attacked|"
    r"i\s+will\s+(?:kill|hurt)\s+you|"
    r"threats?\s+must\s+be\s+reported)\b"
)


def matching_names(
    text: str,
    patterns: tuple[tuple[str, re.Pattern[str]], ...],
) -> list[str]:
    return [name for name, pattern in patterns if pattern.search(text)]


def analyze_violent_content(text: str) -> dict[str, Any]:
    normalized = normalize_text(text)

    result: dict[str, Any] = {
        "available": True,
        "detected": False,
        "category": "",
        "confidence": 0.0,
        "severity": "None",
        "action": "",
        "human_review_required": False,
        "automatic_enforcement_allowed": False,
        "safe_override_allowed": False,
        "decision_type": "none",
        "direct_threat_signals": [],
        "graphic_harm_signals": [],
        "compositional_graphic_signals": [],
        "context_signals": [],
        "metaphor_signals": [],
        "reason": "No sufficiently supported violent-content signal was detected.",
    }

    if not normalized:
        return result

    metaphors = matching_names(normalized, METAPHOR_PATTERNS)
    contexts = matching_names(normalized, CONTEXT_PATTERNS)
    direct_threats = matching_names(normalized, DIRECT_THREAT_PATTERNS)
    graphic_harm = matching_names(normalized, GRAPHIC_PATTERNS)
    graphic_events = matching_names(normalized, GRAPHIC_EVENT_PATTERNS)
    depiction_detected = bool(DEPICTION_PATTERN.search(normalized))
    anatomy_detected = bool(ANATOMY_PATTERN.search(normalized))
    graphic_state_detected = bool(GRAPHIC_STATE_PATTERN.search(normalized))
    victim_harm_detected = bool(VICTIM_HARM_PATTERN.search(normalized))

    compositional_graphic: list[str] = []
    if depiction_detected and graphic_events:
        compositional_graphic.extend(graphic_events)
        compositional_graphic.append("depiction_plus_graphic_event")
    if depiction_detected and anatomy_detected and graphic_state_detected:
        compositional_graphic.append("depiction_plus_anatomy_plus_graphic_state")
    if depiction_detected and victim_harm_detected:
        compositional_graphic.append("depiction_plus_victim_harm")
    negated_prevention = bool(NEGATED_PREVENTION_PATTERN.search(normalized))

    result["metaphor_signals"] = metaphors
    result["context_signals"] = contexts
    result["direct_threat_signals"] = direct_threats
    result["graphic_harm_signals"] = graphic_harm
    result["compositional_graphic_signals"] = list(
        dict.fromkeys(compositional_graphic)
    )

    if metaphors and not direct_threats and not graphic_harm and not compositional_graphic:
        result["decision_type"] = "metaphor"
        result["safe_override_allowed"] = True
        result["reason"] = "Violence-related wording appears to be figurative or domain-specific."
        return result

    if negated_prevention and not graphic_harm and not compositional_graphic:
        result["decision_type"] = "prevention"
        result["safe_override_allowed"] = True
        result["reason"] = "The text discourages violence and does not contain an independent threat."
        return result

    if (
        DOCUMENTED_THREAT_REPORT_PATTERN.search(normalized)
        and not graphic_harm
        and not compositional_graphic
    ):
        result["decision_type"] = "documented_threat_report"
        result["safe_override_allowed"] = True
        result["reason"] = (
            "A threat is quoted as evidence in a police report; the author is not "
            "expressing the threat."
        )
        return result

    if (
        PREVENTED_HARM_PATTERN.search(normalized)
        and not graphic_harm
        and not compositional_graphic
    ):
        result["decision_type"] = "prevented_harm"
        result["safe_override_allowed"] = True
        result["reason"] = (
            "The statement reports that harm was prevented and does not depict "
            "graphic bodily harm."
        )
        return result

    quoted_or_contextual = bool(contexts)

    if quoted_or_contextual:
        contextual_graphic_state = bool(
            anatomy_detected and graphic_state_detected
        )
        material_described = bool(
            direct_threats
            or graphic_harm
            or compositional_graphic
            or contextual_graphic_state
            or VIOLENCE_MATERIAL_PATTERN.search(normalized)
        )

        if not material_described:
            result["decision_type"] = "context_without_violent_material"
            result["reason"] = "Context is present, but no specific violent material was detected."
            return result

        result.update(
            {
                "detected": True,
                "category": VIOLENT_CATEGORY,
                "confidence": 0.82 if (graphic_harm or compositional_graphic) else 0.78,
                "severity": "Low",
                "action": "Allow with sensitive-content warning",
                "human_review_required": False,
                "decision_type": "allowed_context",
                "reason": (
                    "Violence-related material appears in reporting, education, history, "
                    "fiction, gaming, prevention, or documented quotation context."
                ),
            }
        )
        return result

    if graphic_harm or compositional_graphic:
        evidence_count = len(
            set(graphic_harm + compositional_graphic)
        )
        result.update(
            {
                "detected": True,
                "category": VIOLENT_CATEGORY,
                "confidence": min(0.94, 0.86 + (0.02 * max(0, evidence_count - 1))),
                "severity": "High",
                "action": "Block or apply a sensitive-content warning and refer to human review",
                "human_review_required": True,
                "decision_type": "graphic_harm",
                "reason": "The text describes graphic bodily harm or torture.",
            }
        )

    return result
