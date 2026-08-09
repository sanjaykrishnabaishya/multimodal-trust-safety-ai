from __future__ import annotations

import copy
import os
import re
from typing import Any


MISINFORMATION_CATEGORY = (
    "Misinformation & Fake News"
)

NORMAL_CATEGORY = "Normal/Ignore"
UNCERTAIN_CATEGORY = "Uncertain"


SOURCE_REGISTRY: dict[
    str,
    dict[str, Any],
] = {
    "pib_fact_check": {
        "source_id": "pib_fact_check",
        "name": "PIB Fact Check",
        "region": "India",
        "trust_tier": 1,
        "source_type": (
            "official_fact_check"
        ),
        "base_url": (
            "https://www.pib.gov.in/"
            "factcheck.aspx"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "Claims concerning the Government "
            "of India, Central Government "
            "ministries, departments, schemes, "
            "public-sector organizations and "
            "official Central Government actions."
        ),
        "scope_warning": (
            "PIB Fact Check must not be treated "
            "as authoritative for unrelated "
            "private, state-government, foreign "
            "or general scientific claims."
        ),
    },

    "eci_myth_reality": {
        "source_id": "eci_myth_reality",
        "name": (
            "Election Commission of India "
            "Myth vs Reality"
        ),
        "region": "India",
        "trust_tier": 1,
        "source_type": (
            "official_fact_check"
        ),
        "base_url": (
            "https://www.eci.gov.in/"
            "mythvsreality/details"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "Indian elections, EVMs, VVPATs, "
            "electoral rolls, voter services, "
            "polling and Election Commission "
            "procedures."
        ),
        "scope_warning": (
            "ECI evidence applies only to Indian "
            "election-related claims."
        ),
    },

    "rbi": {
        "source_id": "rbi",
        "name": "Reserve Bank of India",
        "region": "India",
        "trust_tier": 1,
        "source_type": (
            "official_authority"
        ),
        "base_url": (
            "https://www.rbi.org.in/"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "Indian banking regulation, currency, "
            "monetary policy, regulated banks, "
            "official RBI notices and financial "
            "warnings."
        ),
    },

    "npci": {
        "source_id": "npci",
        "name": (
            "National Payments Corporation "
            "of India"
        ),
        "region": "India",
        "trust_tier": 1,
        "source_type": (
            "official_authority"
        ),
        "base_url": (
            "https://www.npci.org.in/"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "UPI, IMPS, RuPay and payment "
            "systems operated by NPCI."
        ),
    },

    "uidai": {
        "source_id": "uidai",
        "name": (
            "Unique Identification Authority "
            "of India"
        ),
        "region": "India",
        "trust_tier": 1,
        "source_type": (
            "official_authority"
        ),
        "base_url": (
            "https://uidai.gov.in/"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "Aadhaar rules, official services, "
            "procedures, security guidance and "
            "UIDAI announcements."
        ),
    },

    "mohfw": {
        "source_id": "mohfw",
        "name": (
            "Ministry of Health and "
            "Family Welfare"
        ),
        "region": "India",
        "trust_tier": 1,
        "source_type": (
            "official_authority"
        ),
        "base_url": (
            "https://www.mohfw.gov.in/"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "Government of India public-health "
            "guidance, health programmes and "
            "ministry announcements."
        ),
    },

    "india_code": {
        "source_id": "india_code",
        "name": "India Code",
        "region": "India",
        "trust_tier": 1,
        "source_type": (
            "official_legal_source"
        ),
        "base_url": (
            "https://www.indiacode.nic.in/"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "Texts of Indian Central laws, Acts "
            "and statutory provisions."
        ),
        "scope_warning": (
            "Legal interpretation may still "
            "require a qualified legal reviewer."
        ),
    },

    "who_gho": {
        "source_id": "who_gho",
        "name": (
            "World Health Organization "
            "Global Health Observatory"
        ),
        "region": "World",
        "trust_tier": 1,
        "source_type": (
            "official_structured_data"
        ),
        "base_url": (
            "https://www.who.int/data/gho"
        ),
        "api_url": (
            "https://ghoapi.azureedge.net/api/"
        ),
        "requires_api_key": False,
        "automatic_retrieval_supported": True,
        "scope": (
            "International public-health "
            "indicators and WHO health data."
        ),
    },

    "world_bank": {
        "source_id": "world_bank",
        "name": (
            "World Bank Indicators API"
        ),
        "region": "World",
        "trust_tier": 1,
        "source_type": (
            "official_structured_data"
        ),
        "base_url": (
            "https://data.worldbank.org/"
        ),
        "api_url": (
            "https://api.worldbank.org/v2/"
        ),
        "requires_api_key": False,
        "automatic_retrieval_supported": True,
        "scope": (
            "Population, development, economic, "
            "education, health and international "
            "country-level indicators."
        ),
    },

    "imf": {
        "source_id": "imf",
        "name": (
            "International Monetary Fund Data"
        ),
        "region": "World",
        "trust_tier": 1,
        "source_type": (
            "official_structured_data"
        ),
        "base_url": (
            "https://data.imf.org/"
        ),
        "api_url": None,
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "International macroeconomic, "
            "financial, inflation, debt and "
            "economic-growth data."
        ),
    },

    "un_data": {
        "source_id": "un_data",
        "name": "United Nations Data",
        "region": "World",
        "trust_tier": 1,
        "source_type": (
            "official_structured_data"
        ),
        "base_url": (
            "https://data.un.org/"
        ),
        "api_url": (
            "https://data.un.org/Host.aspx"
            "?Content=API"
        ),
        "requires_api_key": False,
        "automatic_retrieval_supported": (
            False
        ),
        "scope": (
            "International demographic, social, "
            "economic, trade and development data."
        ),
    },

    "wikidata": {
        "source_id": "wikidata",
        "name": "Wikidata",
        "region": "World",
        "trust_tier": 2,
        "source_type": (
            "structured_knowledge_base"
        ),
        "base_url": (
            "https://www.wikidata.org/"
        ),
        "api_url": (
            "https://www.wikidata.org/"
            "w/api.php"
        ),
        "sparql_url": (
            "https://query.wikidata.org/"
            "sparql"
        ),
        "requires_api_key": False,
        "automatic_retrieval_supported": True,
        "scope": (
            "Structured general facts such as "
            "dates, locations, occupations, "
            "relationships and identifiers."
        ),
        "scope_warning": (
            "Wikidata is community maintained "
            "and should be corroborated for "
            "high-impact decisions."
        ),
    },

    "wikipedia": {
        "source_id": "wikipedia",
        "name": "English Wikipedia",
        "region": "World",
        "trust_tier": 3,
        "source_type": (
            "encyclopedic_context"
        ),
        "base_url": (
            "https://en.wikipedia.org/"
        ),
        "api_url": (
            "https://en.wikipedia.org/"
            "w/api.php"
        ),
        "requires_api_key": False,
        "automatic_retrieval_supported": True,
        "scope": (
            "General encyclopedic background "
            "and evidence discovery."
        ),
        "scope_warning": (
            "Wikipedia alone must not establish "
            "a high-impact enforcement decision."
        ),
    },

    "google_fact_check": {
        "source_id": "google_fact_check",
        "name": (
            "Google Fact Check Tools API"
        ),
        "region": "World",
        "trust_tier": 2,
        "source_type": (
            "fact_check_aggregator"
        ),
        "base_url": (
            "https://toolbox.google.com/"
            "factcheck/explorer"
        ),
        "api_url": (
            "https://factchecktools."
            "googleapis.com/v1alpha1/"
            "claims:search"
        ),
        "requires_api_key": True,
        "api_key_environment_variable": (
            "GOOGLE_FACT_CHECK_API_KEY"
        ),
        "automatic_retrieval_supported": True,
        "scope": (
            "Previously published ClaimReview "
            "fact checks from participating "
            "fact-checking organizations."
        ),
        "scope_warning": (
            "A matching fact check must concern "
            "the same claim, date, place and "
            "context. Similar wording alone is "
            "not sufficient."
        ),
    },
}


INDIA_CONTEXT_PATTERN = re.compile(
    r"""
    \b
    (?:
        india
        |
        indian
        |
        bharat
        |
        government\s+of\s+india
        |
        central\s+government
        |
        union\s+government
        |
        prime\s+minister\s+of\s+india
        |
        parliament\s+of\s+india
        |
        supreme\s+court\s+of\s+india
        |
        rbi
        |
        reserve\s+bank\s+of\s+india
        |
        npci
        |
        uidai
        |
        aadhaar
        |
        aadhar
        |
        upi
        |
        rupee
        |
        lok\s+sabha
        |
        rajya\s+sabha
        |
        election\s+commission\s+of\s+india
    )
    \b
    """,
    re.IGNORECASE | re.VERBOSE,
)


TOPIC_PATTERNS = {
    "central_government": re.compile(
        r"""
        \b
        (?:
            government\s+of\s+india
            |
            central\s+government
            |
            union\s+government
            |
            central\s+ministry
            |
            government\s+scheme
            |
            government\s+yojana
            |
            cabinet
            |
            lok\s+sabha
            |
            rajya\s+sabha
            |
            parliament\s+of\s+india
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "elections": re.compile(
        r"""
        \b
        (?:
            election
            |
            elections
            |
            electoral
            |
            voter
            |
            voting
            |
            ballot
            |
            polling
            |
            evm
            |
            vvpat
            |
            election\s+commission
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "banking": re.compile(
        r"""
        \b
        (?:
            bank
            |
            banking
            |
            rbi
            |
            reserve\s+bank
            |
            repo\s+rate
            |
            interest\s+rate
            |
            currency
            |
            rupee
            |
            loan
            |
            monetary\s+policy
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "payments": re.compile(
        r"""
        \b
        (?:
            upi
            |
            npci
            |
            rupay
            |
            imps
            |
            digital\s+payment
            |
            payment\s+system
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "aadhaar": re.compile(
        r"""
        \b
        (?:
            aadhaar
            |
            aadhar
            |
            uidai
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "health": re.compile(
        r"""
        \b
        (?:
            health
            |
            disease
            |
            medicine
            |
            medical
            |
            vaccine
            |
            vaccination
            |
            virus
            |
            infection
            |
            treatment
            |
            hospital
            |
            pandemic
            |
            epidemic
            |
            mortality
            |
            life\s+expectancy
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "law": re.compile(
        r"""
        \b
        (?:
            law
            |
            legal
            |
            illegal
            |
            act\s+of\s+parliament
            |
            section\s+\d+
            |
            constitution
            |
            supreme\s+court
            |
            high\s+court
            |
            criminal\s+code
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "economy": re.compile(
        r"""
        \b
        (?:
            economy
            |
            economic
            |
            gdp
            |
            inflation
            |
            unemployment
            |
            national\s+income
            |
            debt
            |
            deficit
            |
            exchange\s+rate
            |
            poverty
            |
            trade
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "population": re.compile(
        r"""
        \b
        (?:
            population
            |
            birth\s+rate
            |
            death\s+rate
            |
            demographic
            |
            census
            |
            literacy
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "geography": re.compile(
        r"""
        \b
        (?:
            country
            |
            capital
            |
            city
            |
            continent
            |
            river
            |
            mountain
            |
            ocean
            |
            located
            |
            border
            |
            area
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "science": re.compile(
        r"""
        \b
        (?:
            science
            |
            scientific
            |
            planet
            |
            space
            |
            chemical
            |
            physics
            |
            biology
            |
            species
            |
            discovered
            |
            invented
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "climate": re.compile(
        r"""
        \b
        (?:
            climate
            |
            climate\s+change
            |
            global\s+warming
            |
            temperature
            |
            carbon\s+emission
            |
            greenhouse\s+gas
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),

    "current_events": re.compile(
        r"""
        \b
        (?:
            today
            |
            yesterday
            |
            latest
            |
            currently
            |
            this\s+week
            |
            this\s+month
            |
            this\s+year
            |
            just\s+announced
            |
            breaking
        )
        \b
        """,
        re.IGNORECASE | re.VERBOSE,
    ),
}


HIGH_IMPACT_TOPICS = {
    "central_government",
    "elections",
    "banking",
    "payments",
    "aadhaar",
    "health",
    "law",
    "economy",
    "climate",
}


def normalize_text(
    text: str,
) -> str:
    return " ".join(
        str(text or "").split()
    )


def detect_topics(
    text: str,
) -> list[str]:
    cleaned_text = normalize_text(text)

    return [
        topic
        for topic, pattern
        in TOPIC_PATTERNS.items()
        if pattern.search(cleaned_text)
    ]


def source_is_available(
    source: dict[str, Any],
) -> bool:
    if not source.get(
        "requires_api_key",
        False,
    ):
        return True

    environment_variable = str(
        source.get(
            "api_key_environment_variable",
            "",
        )
    )

    return bool(
        environment_variable
        and os.getenv(
            environment_variable
        )
    )


def add_source(
    source_ids: list[str],
    source_id: str,
) -> None:
    if source_id not in source_ids:
        source_ids.append(source_id)


def select_source_ids(
    india_context: bool,
    topics: list[str],
) -> list[str]:
    selected_source_ids: list[str] = []

    if india_context:
        if "central_government" in topics:
            add_source(
                selected_source_ids,
                "pib_fact_check",
            )

        if "elections" in topics:
            add_source(
                selected_source_ids,
                "eci_myth_reality",
            )

            add_source(
                selected_source_ids,
                "pib_fact_check",
            )

        if "banking" in topics:
            add_source(
                selected_source_ids,
                "rbi",
            )

        if "payments" in topics:
            add_source(
                selected_source_ids,
                "npci",
            )

            add_source(
                selected_source_ids,
                "rbi",
            )

        if "aadhaar" in topics:
            add_source(
                selected_source_ids,
                "uidai",
            )

        if "health" in topics:
            add_source(
                selected_source_ids,
                "mohfw",
            )

        if "law" in topics:
            add_source(
                selected_source_ids,
                "india_code",
            )

    if "health" in topics:
        add_source(
            selected_source_ids,
            "who_gho",
        )

    if (
        "economy" in topics
        or "population" in topics
    ):
        add_source(
            selected_source_ids,
            "world_bank",
        )

        add_source(
            selected_source_ids,
            "imf",
        )

        add_source(
            selected_source_ids,
            "un_data",
        )

    add_source(
        selected_source_ids,
        "wikidata",
    )

    add_source(
        selected_source_ids,
        "wikipedia",
    )

    add_source(
        selected_source_ids,
        "google_fact_check",
    )

    return selected_source_ids


def build_fact_check_source_plan(
    text: str,
) -> dict[str, Any]:
    claim = normalize_text(text)

    india_context = bool(
        INDIA_CONTEXT_PATTERN.search(
            claim
        )
    )

    topics = detect_topics(claim)

    high_impact_claim = bool(
        set(topics)
        & HIGH_IMPACT_TOPICS
    )

    selected_source_ids = (
        select_source_ids(
            india_context,
            topics,
        )
    )

    available_sources = []
    unavailable_optional_sources = []

    for source_id in selected_source_ids:
        source = copy.deepcopy(
            SOURCE_REGISTRY[source_id]
        )

        source["available"] = (
            source_is_available(
                source
            )
        )

        if source["available"]:
            available_sources.append(
                source
            )
        else:
            unavailable_optional_sources.append(
                source
            )

    available_sources.sort(
        key=lambda source: (
            int(
                source.get(
                    "trust_tier",
                    99,
                )
            ),
            source.get(
                "name",
                "",
            ),
        )
    )

    warnings = []

    if not claim:
        warnings.append(
            "No claim text was supplied."
        )

    if (
        "current_events" in topics
    ):
        warnings.append(
            "Current-event claims require "
            "fresh evidence. Cached or historical "
            "sources may be outdated."
        )

    if high_impact_claim:
        warnings.append(
            "This is a high-impact claim. "
            "No automatic enforcement is allowed."
        )

    if (
        not india_context
        and "elections" in topics
    ):
        warnings.append(
            "A non-Indian election claim requires "
            "the relevant country's official "
            "election authority. No universal "
            "global election authority exists."
        )

    return {
        "available": True,
        "claim": claim,
        "language": "English",
        "multilingual_processing_enabled": (
            False
        ),
        "india_context_detected": (
            india_context
        ),
        "world_context_enabled": True,
        "topics": topics,
        "high_impact_claim": (
            high_impact_claim
        ),
        "recommended_sources": (
            available_sources
        ),
        "optional_unavailable_sources": (
            unavailable_optional_sources
        ),
        "automatic_sources": [
            source
            for source
            in available_sources
            if source.get(
                "automatic_retrieval_supported",
                False,
            )
        ],
        "manual_official_sources": [
            source
            for source
            in available_sources
            if not source.get(
                "automatic_retrieval_supported",
                False,
            )
        ],
        "official_sources_consulted": False,
        "automatic_enforcement_allowed": (
            False
        ),
        "human_review_required_if_refuted": (
            True
        ),
        "human_review_required_if_uncertain": (
            True
        ),
        "refuted_action": (
            "Refer to human review"
        ),
        "uncertain_action": (
            "Refer to human review"
        ),
        "confidence_cap": (
            0.75
            if high_impact_claim
            else 0.80
        ),
        "warnings": warnings,
        "limitations": [
            (
                "Source routing selects relevant "
                "evidence sources but does not "
                "prove a claim true or false."
            ),
            (
                "Official sources are authoritative "
                "only inside their defined scope."
            ),
            (
                "Wikipedia and Wikidata must be "
                "corroborated for high-impact claims."
            ),
            (
                "Absence of evidence is not evidence "
                "that a claim is false."
            ),
        ],
    }