from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable


DEVELOPMENT_VERSION = "2026.08-v3-development"
SCRIPT_DIRECTORY = Path(__file__).resolve().parent
BACKEND_DIRECTORY = SCRIPT_DIRECTORY.parent
PROJECT_DIRECTORY = BACKEND_DIRECTORY.parent
OUTPUT_DIRECTORY = (
    PROJECT_DIRECTORY
    / "datasets"
    / "development"
    / "stable_knowledge_v3"
)
DATASET_PATH = OUTPUT_DIRECTORY / "development.csv"
MANIFEST_PATH = OUTPUT_DIRECTORY / "manifest.json"


@dataclass(frozen=True)
class Fact:
    fact_id: str
    topic: str
    relation: str
    subject: str
    object: str
    source_hint: str


@dataclass(frozen=True)
class DevelopmentRecord:
    case_id: str
    split: str
    topic: str
    relation: str
    expected_status: str
    expected_routing: str
    claim: str
    source_hint: str
    template_type: str
    allowed_for_threshold_tuning: bool
    eligible_for_holdout: bool


FACTS: tuple[Fact, ...] = (
    Fact("CAP-01", "geography", "capital_of", "Ottawa", "Canada", "Wikidata P36"),
    Fact("CAP-02", "geography", "capital_of", "Canberra", "Australia", "Wikidata P36"),
    Fact("CAP-03", "geography", "capital_of", "Tokyo", "Japan", "Wikidata P36"),
    Fact("CAP-04", "geography", "capital_of", "Brasilia", "Brazil", "Wikidata P36"),
    Fact("CAP-05", "geography", "capital_of", "Nairobi", "Kenya", "Wikidata P36"),
    Fact("CAP-06", "geography", "capital_of", "Bangkok", "Thailand", "Wikidata P36"),
    Fact("CAP-07", "geography", "capital_of", "Lima", "Peru", "Wikidata P36"),
    Fact("CAP-08", "geography", "capital_of", "Ankara", "Turkey", "Wikidata P36"),
    Fact("COUNTRY-01", "geography", "country_of", "Taj Mahal", "India", "Wikidata P17"),
    Fact("COUNTRY-02", "geography", "country_of", "Colosseum", "Italy", "Wikidata P17"),
    Fact("COUNTRY-03", "geography", "country_of", "Machu Picchu", "Peru", "Wikidata P17"),
    Fact("COUNTRY-04", "geography", "country_of", "Great Pyramid of Giza", "Egypt", "Wikidata P17"),
    Fact("CONT-01", "geography", "continent_of", "India", "Asia", "Wikidata P30"),
    Fact("CONT-02", "geography", "continent_of", "Brazil", "South America", "Wikidata P30"),
    Fact("CONT-03", "geography", "continent_of", "Kenya", "Africa", "Wikidata P30"),
    Fact("CONT-04", "geography", "continent_of", "France", "Europe", "Wikidata P30"),
    Fact("BORDER-01", "geography", "borders", "India", "Pakistan", "Wikidata P47"),
    Fact("BORDER-02", "geography", "borders", "France", "Germany", "Wikidata P47"),
    Fact("BORDER-03", "geography", "borders", "Canada", "United States", "Wikidata P47"),
    Fact("BORDER-04", "geography", "borders", "Argentina", "Chile", "Wikidata P47"),
    Fact("ORBIT-01", "astronomy", "orbits", "Moon", "Earth", "Wikidata P397 and NASA"),
    Fact("ORBIT-02", "astronomy", "orbits", "Earth", "Sun", "Wikidata P397 and NASA"),
    Fact("ORBIT-03", "astronomy", "orbits", "Mars", "Sun", "Wikidata P397 and NASA"),
    Fact("ORBIT-04", "astronomy", "orbits", "Phobos", "Mars", "Wikidata P397 and NASA"),
    Fact("ORBIT-05", "astronomy", "orbits", "Europa", "Jupiter", "Wikidata P397 and NASA"),
    Fact("ORBIT-06", "astronomy", "orbits", "Titan", "Saturn", "Wikidata P397 and NASA"),
    Fact("TYPE-01", "astronomy", "instance_of", "Sun", "star", "Wikidata P31 and NASA"),
    Fact("TYPE-02", "astronomy", "instance_of", "Earth", "planet", "Wikidata P31 and NASA"),
    Fact("TYPE-03", "astronomy", "instance_of", "Mars", "planet", "Wikidata P31 and NASA"),
    Fact("SYMBOL-01", "basic_science", "chemical_symbol", "gold", "Au", "Wikidata P246"),
    Fact("SYMBOL-02", "basic_science", "chemical_symbol", "oxygen", "O", "Wikidata P246"),
    Fact("SYMBOL-03", "basic_science", "chemical_symbol", "sodium", "Na", "Wikidata P246"),
    Fact("SYMBOL-04", "basic_science", "chemical_symbol", "iron", "Fe", "Wikidata P246"),
    Fact("SYMBOL-05", "basic_science", "chemical_symbol", "silver", "Ag", "Wikidata P246"),
    Fact("SYMBOL-06", "basic_science", "chemical_symbol", "carbon", "C", "Wikidata P246"),
    Fact("ATOMIC-01", "basic_science", "atomic_number", "oxygen", "8", "Wikidata P1086"),
    Fact("ATOMIC-02", "basic_science", "atomic_number", "gold", "79", "Wikidata P1086"),
    Fact("ATOMIC-03", "basic_science", "atomic_number", "carbon", "6", "Wikidata P1086"),
    Fact("ATOMIC-04", "basic_science", "atomic_number", "iron", "26", "Wikidata P1086"),
    Fact("ATOMIC-05", "basic_science", "atomic_number", "silver", "47", "Wikidata P1086"),
    Fact("FREEZE-01", "basic_science", "freezes_at", "water", "0 degrees Celsius", "Wikidata P2101 and NIST"),
    Fact("BOIL-01", "basic_science", "boils_at", "water", "100 degrees Celsius", "Wikidata P2102 and NIST"),
    Fact("FOUND-01", "established_history", "founded_in", "United Nations", "1945", "Wikidata P571"),
    Fact("FOUND-02", "established_history", "founded_in", "NASA", "1958", "Wikidata P571 and NASA"),
    Fact("FOUND-03", "established_history", "founded_in", "Google", "1998", "Wikidata P571"),
    Fact("INVENT-01", "established_history", "invented_by", "telephone", "Alexander Graham Bell", "Wikidata P61 and Library of Congress"),
    Fact("INVENT-02", "established_history", "invented_by", "World Wide Web", "Tim Berners-Lee", "Wikidata P61"),
    Fact("DISCOVER-01", "established_history", "discovered_by", "penicillin", "Alexander Fleming", "Wikidata P61"),
    Fact("BIRTH-01", "established_history", "born_in", "Albert Einstein", "Ulm", "Wikidata P19"),
    Fact("BIRTH-02", "established_history", "born_in", "Mahatma Gandhi", "Porbandar", "Wikidata P19"),
    Fact("BIRTH-03", "established_history", "born_in", "William Shakespeare", "Stratford-upon-Avon", "Wikidata P19"),
    Fact("END-01", "established_history", "ended_in", "World War II", "1945", "Wikidata P582 and National Archives"),
)


BOUNDARY_CLAIMS: tuple[tuple[str, str, str], ...] = (
    ("BOUNDARY-01", "current_high_impact_boundary", "The election result was announced today."),
    ("BOUNDARY-02", "current_high_impact_boundary", "The central bank changed interest rates this week."),
    ("BOUNDARY-03", "current_high_impact_boundary", "A new vaccine was approved today."),
    ("BOUNDARY-04", "current_high_impact_boundary", "The Supreme Court issued a new order today."),
    ("BOUNDARY-05", "current_high_impact_boundary", "The stock price reached a new record this morning."),
    ("BOUNDARY-06", "current_high_impact_boundary", "A disease outbreak was reported this month."),
    ("BOUNDARY-07", "question_boundary", "Is Ottawa the capital of Canada?"),
    ("BOUNDARY-08", "question_boundary", "Does the Moon orbit Earth?"),
    ("BOUNDARY-09", "opinion_boundary", "Paris is the most beautiful capital."),
    ("BOUNDARY-10", "opinion_boundary", "Mars is the best planet."),
    ("BOUNDARY-11", "empty_boundary", ""),
    ("BOUNDARY-12", "unsupported_relation_boundary", "Water tastes pleasant."),
)


def capital_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} is the capital of {fact.object}."),
        ("SUPPORTS", "reverse_support", f"The capital city of {fact.object} is {fact.subject}."),
        ("REFUTES", "wrong_object", f"{fact.subject} is the capital of {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} is not the capital of {fact.object}."),
    ]


def country_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} is part of the country of {fact.object}."),
        ("SUPPORTS", "article_support", f"The {fact.subject} is part of the country of {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} is part of the country of {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} is not part of the country of {fact.object}."),
    ]


def continent_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} is on the continent of {fact.object}."),
        ("SUPPORTS", "located_support", f"{fact.subject} is located on the continent of {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} is on the continent of {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} is not on the continent of {fact.object}."),
    ]


def borders_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} borders {fact.object}."),
        ("SUPPORTS", "phrase_support", f"{fact.subject} shares a border with {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} borders {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} does not border {fact.object}."),
    ]


def orbits_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} orbits {fact.object}."),
        ("SUPPORTS", "paraphrase_support", f"{fact.subject} revolves around {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} orbits {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} does not orbit {fact.object}."),
    ]


def instance_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} is a {fact.object}."),
        ("SUPPORTS", "article_support", f"The {fact.subject} is a {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} is a {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} is not a {fact.object}."),
    ]


def symbol_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"The chemical symbol for {fact.subject} is {fact.object}."),
        ("SUPPORTS", "of_support", f"The chemical symbol of {fact.subject} is {fact.object}."),
        ("REFUTES", "wrong_object", f"The chemical symbol for {fact.subject} is {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"The chemical symbol for {fact.subject} is not {fact.object}."),
    ]


def atomic_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"The atomic number of {fact.subject} is {fact.object}."),
        ("SUPPORTS", "for_support", f"The atomic number for {fact.subject} is {fact.object}."),
        ("REFUTES", "wrong_object", f"The atomic number of {fact.subject} is {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"The atomic number of {fact.subject} is not {fact.object}."),
    ]


def founded_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} was founded in {fact.object}."),
        ("SUPPORTS", "established_support", f"{fact.subject} was established in {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} was founded in {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} was not founded in {fact.object}."),
    ]


def invented_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"The {fact.subject} was invented by {fact.object}."),
        ("SUPPORTS", "developed_support", f"The {fact.subject} was developed by {fact.object}."),
        ("REFUTES", "wrong_object", f"The {fact.subject} was invented by {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"The {fact.subject} was not invented by {fact.object}."),
    ]


def discovered_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} was discovered by {fact.object}."),
        ("SUPPORTS", "article_support", f"The {fact.subject} was discovered by {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} was discovered by {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} was not discovered by {fact.object}."),
    ]


def born_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} was born in {fact.object}."),
        ("SUPPORTS", "present_support", f"{fact.subject} is born in {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} was born in {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} was not born in {fact.object}."),
    ]


def ended_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} ended in {fact.object}."),
        ("SUPPORTS", "concluded_support", f"{fact.subject} concluded in {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} ended in {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} did not end in {fact.object}."),
    ]


def temperature_templates(fact: Fact, wrong_object: str) -> list[tuple[str, str, str]]:
    verb = "freezes" if fact.relation == "freezes_at" else "boils"
    base_verb = "freeze" if fact.relation == "freezes_at" else "boil"
    return [
        ("SUPPORTS", "canonical_support", f"{fact.subject} {verb} at {fact.object}."),
        ("SUPPORTS", "article_support", f"The {fact.subject} {verb} at {fact.object}."),
        ("REFUTES", "wrong_object", f"{fact.subject} {verb} at {wrong_object}."),
        ("REFUTES", "negated_true_relation", f"{fact.subject} does not {base_verb} at {fact.object}."),
    ]


TEMPLATE_BUILDERS: dict[
    str,
    Callable[[Fact, str], list[tuple[str, str, str]]],
] = {
    "capital_of": capital_templates,
    "country_of": country_templates,
    "continent_of": continent_templates,
    "borders": borders_templates,
    "orbits": orbits_templates,
    "instance_of": instance_templates,
    "chemical_symbol": symbol_templates,
    "atomic_number": atomic_templates,
    "founded_in": founded_templates,
    "invented_by": invented_templates,
    "discovered_by": discovered_templates,
    "born_in": born_templates,
    "ended_in": ended_templates,
    "freezes_at": temperature_templates,
    "boils_at": temperature_templates,
}


def relation_facts(relation: str) -> list[Fact]:
    return [fact for fact in FACTS if fact.relation == relation]


def distractor_for(fact: Fact, fact_index: int) -> str:
    candidates = [
        item.object
        for item in relation_facts(fact.relation)
        if item.object != fact.object
    ]

    if candidates:
        return candidates[fact_index % len(candidates)]

    fallback = {
        "freezes_at": "25 degrees Celsius",
        "boils_at": "50 degrees Celsius",
        "invented_by": "Isaac Newton",
        "discovered_by": "Galileo Galilei",
        "ended_in": "1939",
    }
    return fallback.get(fact.relation, "an unrelated value")


def build_records() -> list[DevelopmentRecord]:
    records: list[DevelopmentRecord] = []

    for fact_index, fact in enumerate(FACTS):
        builder = TEMPLATE_BUILDERS[fact.relation]
        wrong_object = distractor_for(fact, fact_index)

        for template_index, (status, template_type, claim) in enumerate(
            builder(fact, wrong_object),
            start=1,
        ):
            records.append(
                DevelopmentRecord(
                    case_id=f"DEV-{fact.fact_id}-{template_index:02d}",
                    split="development",
                    topic=fact.topic,
                    relation=fact.relation,
                    expected_status=status,
                    expected_routing="stable_knowledge",
                    claim=claim,
                    source_hint=fact.source_hint,
                    template_type=template_type,
                    allowed_for_threshold_tuning=True,
                    eligible_for_holdout=False,
                )
            )

    for case_id, topic, claim in BOUNDARY_CLAIMS:
        records.append(
            DevelopmentRecord(
                case_id=case_id,
                split="development",
                topic=topic,
                relation="boundary",
                expected_status="NOT_ROUTED",
                expected_routing="other_policy_path",
                claim=claim,
                source_hint="Policy routing test; no factual verdict expected",
                template_type="boundary",
                allowed_for_threshold_tuning=True,
                eligible_for_holdout=False,
            )
        )

    return records


def write_dataset(records: list[DevelopmentRecord]) -> None:
    OUTPUT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    fieldnames = list(asdict(records[0]).keys())

    with DATASET_PATH.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(asdict(record) for record in records)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_manifest(records: list[DevelopmentRecord]) -> dict[str, object]:
    status_counts = Counter(record.expected_status for record in records)
    topic_counts = Counter(record.topic for record in records)
    relation_counts = Counter(record.relation for record in records)
    manifest: dict[str, object] = {
        "version": DEVELOPMENT_VERSION,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset_path": str(DATASET_PATH),
        "dataset_sha256": sha256_file(DATASET_PATH),
        "record_count": len(records),
        "status_counts": dict(sorted(status_counts.items())),
        "topic_counts": dict(sorted(topic_counts.items())),
        "relation_counts": dict(sorted(relation_counts.items())),
        "split": "development",
        "allowed_for_threshold_tuning": True,
        "eligible_for_holdout": False,
        "contains_copied_webpage_text": False,
        "contains_personal_information": False,
        "uses_v2_holdout_records": False,
        "uses_v2_mismatch_report": False,
        "persistent_cache_required": False,
        "instructions": [
            "This dataset is for development and threshold tuning only.",
            "Never report performance on this dataset as independent accuracy.",
            "Never add this dataset to a future independent holdout.",
            "Do not inspect or tune from the V2 holdout mismatch file.",
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    records = build_records()
    write_dataset(records)
    manifest = write_manifest(records)

    print("=" * 60)
    print("STABLE KNOWLEDGE V3 DEVELOPMENT DATASET")
    print("=" * 60)
    print(f"Version: {DEVELOPMENT_VERSION}")
    print(f"Records: {manifest['record_count']}")
    print(f"SHA-256: {manifest['dataset_sha256']}")
    print(f"Dataset: {DATASET_PATH}")
    print(f"Manifest: {MANIFEST_PATH}")
    print("\nEXPECTED STATUS COUNTS")
    print("-" * 60)
    for name, count in manifest["status_counts"].items():
        print(f"{name}: {count}")
    print("\nRELATION COUNTS")
    print("-" * 60)
    for name, count in manifest["relation_counts"].items():
        print(f"{name}: {count}")
    print("\nThis is development data, not an independent accuracy test.")
    print("The V2 holdout and its mismatch report were not read.")


if __name__ == "__main__":
    main()
