from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from app.services.stable_knowledge_service import (
    WIKIDATA_API_URL,
    live_request_json,
)
from app.services.structured_claim_service import parse_structured_claim


MAXIMUM_SEARCH_RESULTS = 10
MAXIMUM_RECORDED_VALUES = 25


@dataclass(frozen=True)
class PropertyRoute:
    relation: str
    anchor: str
    target: str
    properties: tuple[str, ...]
    value_kind: str
    closed_world: bool
    symmetric: bool = False


PROPERTY_ROUTES: dict[str, PropertyRoute] = {
    "capital_of": PropertyRoute(
        "capital_of", "object", "subject", ("P36",), "entity", True
    ),
    "located_in": PropertyRoute(
        "located_in", "subject", "object", ("P131",), "entity", False
    ),
    "country_of": PropertyRoute(
        "country_of", "subject", "object", ("P17",), "entity", True
    ),
    "continent_of": PropertyRoute(
        "continent_of", "subject", "object", ("P30",), "entity", True
    ),
    "borders": PropertyRoute(
        "borders", "subject", "object", ("P47",), "entity", False, True
    ),
    "orbits": PropertyRoute(
        "orbits", "subject", "object", ("P397",), "entity", True
    ),
    "instance_of": PropertyRoute(
        "instance_of", "subject", "object", ("P31",), "entity", False
    ),
    "chemical_symbol": PropertyRoute(
        "chemical_symbol", "subject", "object", ("P246",), "string", True
    ),
    "atomic_number": PropertyRoute(
        "atomic_number", "subject", "object", ("P1086",), "quantity", True
    ),
    "founded_by": PropertyRoute(
        "founded_by", "subject", "object", ("P112",), "entity", False
    ),
    "founded_in": PropertyRoute(
        "founded_in", "subject", "object", ("P571",), "time", True
    ),
    "invented_by": PropertyRoute(
        "invented_by", "subject", "object", ("P61",), "entity", False
    ),
    "discovered_by": PropertyRoute(
        "discovered_by", "subject", "object", ("P61",), "entity", False
    ),
    "born_in": PropertyRoute(
        "born_in", "subject", "object", ("P19",), "entity", True
    ),
    "born_on": PropertyRoute(
        "born_on", "subject", "object", ("P569",), "time", True
    ),
    "ended_in": PropertyRoute(
        "ended_in", "subject", "object", ("P582", "P576"), "time", True
    ),
    "freezes_at": PropertyRoute(
        "freezes_at", "subject", "object", ("P2101",), "quantity", True
    ),
    "boils_at": PropertyRoute(
        "boils_at", "subject", "object", ("P2102",), "quantity", True
    ),
}


UNIT_ENTITY_NAMES = {
    "Q25267": "degrees Celsius",
    "Q11579": "kelvin",
    "Q42289": "degrees Fahrenheit",
    "Q828224": "kilometre",
    "Q11573": "metre",
    "Q174728": "centimetre",
    "Q174789": "millimetre",
    "Q100995": "kilogram",
    "Q41803": "gram",
    "Q11574": "second",
    "Q7727": "minute",
    "Q25235": "hour",
    "Q573": "day",
    "Q577": "year",
}


def normalize_text(value: Any) -> str:
    return " ".join(str(value or "").split())


def comparable_text(value: Any) -> str:
    normalized = unicodedata.normalize("NFKD", normalize_text(value))
    without_marks = "".join(
        character
        for character in normalized
        if not unicodedata.combining(character)
    )
    return re.sub(r"[^a-z0-9]+", " ", without_marks.casefold()).strip()


def content_tokens(value: Any) -> set[str]:
    return {
        token
        for token in comparable_text(value).split()
        if len(token) >= 2 and token not in {"a", "an", "the", "of"}
    }


def name_similarity(left: Any, right: Any) -> float:
    left_key = comparable_text(left)
    right_key = comparable_text(right)

    if not left_key or not right_key:
        return 0.0
    if left_key == right_key:
        return 1.0

    left_tokens = content_tokens(left_key)
    right_tokens = content_tokens(right_key)

    if not left_tokens or not right_tokens:
        return 0.0

    intersection = len(left_tokens & right_tokens)
    union = len(left_tokens | right_tokens)
    return intersection / union if union else 0.0


def _entity_search_candidates(name: str) -> list[dict[str, Any]]:
    payload = live_request_json(
        WIKIDATA_API_URL,
        {
            "action": "wbsearchentities",
            "search": name,
            "language": "en",
            "uselang": "en",
            "type": "item",
            "limit": MAXIMUM_SEARCH_RESULTS,
            "format": "json",
        },
    )
    return [
        item
        for item in payload.get("search", [])
        if isinstance(item, dict) and item.get("id")
    ]


def ranked_wikidata_entities(name: str) -> list[dict[str, Any]]:
    cleaned_name = normalize_text(name).strip(" .?!,;:\"'")
    if not cleaned_name:
        return []

    candidates = _entity_search_candidates(cleaned_name)
    ranked: list[tuple[float, int, dict[str, Any]]] = []

    for index, item in enumerate(candidates):
        label = normalize_text(item.get("label", ""))
        match_text = normalize_text(item.get("match", {}).get("text", ""))
        aliases = [normalize_text(value) for value in item.get("aliases", [])]
        scores = [
            name_similarity(cleaned_name, label),
            name_similarity(cleaned_name, match_text),
            *(name_similarity(cleaned_name, alias) for alias in aliases),
        ]
        best_score = max(scores or [0.0])

        if best_score >= 0.82:
            ranked.append((best_score, -index, item))

    ranked.sort(key=lambda entry: (entry[0], entry[1]), reverse=True)
    return [
        {
            "id": str(selected["id"]),
            "label": normalize_text(selected.get("label", cleaned_name)),
            "description": normalize_text(selected.get("description", "")),
            "resolution_score": round(score, 4),
            "source_url": f"https://www.wikidata.org/wiki/{selected['id']}",
        }
        for score, _, selected in ranked
    ]


def resolve_wikidata_entity(name: str) -> dict[str, Any] | None:
    ranked = ranked_wikidata_entities(name)
    return ranked[0] if ranked else None


def _load_entity(entity_id: str, properties: tuple[str, ...]) -> dict[str, Any]:
    payload = live_request_json(
        WIKIDATA_API_URL,
        {
            "action": "wbgetentities",
            "ids": entity_id,
            "props": "claims|labels|descriptions",
            "languages": "en",
            "languagefallback": 1,
            "format": "json",
        },
    )
    entity = payload.get("entities", {}).get(entity_id, {})
    if not isinstance(entity, dict):
        return {}

    claims = entity.get("claims", {})
    entity["claims"] = {
        property_id: claims.get(property_id, [])
        for property_id in properties
    }
    return entity


def resolve_wikidata_anchor(
    name: str,
    properties: tuple[str, ...],
) -> tuple[dict[str, Any] | None, dict[str, Any]]:
    candidates = ranked_wikidata_entities(name)
    if not candidates:
        return None, {}

    first_entity: dict[str, Any] = {}
    maximum_candidates = min(len(candidates), MAXIMUM_SEARCH_RESULTS)

    for index, candidate in enumerate(candidates[:maximum_candidates]):
        entity = _load_entity(str(candidate["id"]), properties)
        if index == 0:
            first_entity = entity

        has_routed_property = any(
            _usable_statements(entity, property_id)
            for property_id in properties
        )
        if has_routed_property:
            selected = dict(candidate)
            selected["property_aware_resolution"] = True
            selected["candidate_rank"] = index + 1
            return selected, entity

    selected = dict(candidates[0])
    selected["property_aware_resolution"] = False
    selected["candidate_rank"] = 1
    return selected, first_entity


def _usable_statements(entity: dict[str, Any], property_id: str) -> list[dict[str, Any]]:
    statements = [
        statement
        for statement in entity.get("claims", {}).get(property_id, [])
        if isinstance(statement, dict)
        and str(statement.get("rank", "normal")).casefold() != "deprecated"
        and statement.get("mainsnak", {}).get("snaktype", "value") == "value"
    ]
    preferred = [
        statement
        for statement in statements
        if str(statement.get("rank", "")).casefold() == "preferred"
    ]
    return preferred or statements


def _statement_value(statement: dict[str, Any]) -> Any:
    return (
        statement.get("mainsnak", {})
        .get("datavalue", {})
        .get("value")
    )


def _entity_values(statements: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for statement in statements:
        value = _statement_value(statement)
        if isinstance(value, dict) and value.get("id"):
            values.append(str(value["id"]))
    return values


def load_entity_label_map(entity_ids: list[str]) -> dict[str, str]:
    unique_ids = list(dict.fromkeys(entity_ids))[:MAXIMUM_RECORDED_VALUES]
    if not unique_ids:
        return {}

    payload = live_request_json(
        WIKIDATA_API_URL,
        {
            "action": "wbgetentities",
            "ids": "|".join(unique_ids),
            "props": "labels|descriptions",
            "languages": "en",
            "languagefallback": 1,
            "format": "json",
        },
    )
    entities = payload.get("entities", {})
    labels: dict[str, str] = {}

    for entity_id in unique_ids:
        entity = entities.get(entity_id, {})
        label = normalize_text(
            entity.get("labels", {}).get("en", {}).get("value", "")
        )
        if label:
            labels[entity_id] = label

    return labels


def _string_values(statements: list[dict[str, Any]]) -> list[str]:
    values: list[str] = []
    for statement in statements:
        value = _statement_value(statement)
        if isinstance(value, str):
            values.append(normalize_text(value))
        elif isinstance(value, dict) and value.get("text"):
            values.append(normalize_text(value["text"]))
    return values


def _time_values(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for statement in statements:
        value = _statement_value(statement)
        if not isinstance(value, dict) or not value.get("time"):
            continue

        raw_time = str(value["time"])
        match = re.match(
            r"^[+-](?P<year>\d{4,})-(?P<month>\d{2})-(?P<day>\d{2})T",
            raw_time,
        )
        if match is None:
            continue

        values.append(
            {
                "year": int(match.group("year")),
                "month": int(match.group("month")),
                "day": int(match.group("day")),
                "precision": int(value.get("precision", 0)),
                "raw": raw_time,
            }
        )
    return values


def _quantity_values(statements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    values: list[dict[str, Any]] = []
    for statement in statements:
        value = _statement_value(statement)
        if not isinstance(value, dict) or value.get("amount") is None:
            continue

        try:
            amount = float(str(value["amount"]).replace("+", "", 1))
        except ValueError:
            continue

        unit_url = str(value.get("unit", ""))
        unit_id = unit_url.rstrip("/").rsplit("/", 1)[-1] if unit_url else ""
        values.append(
            {
                "amount": amount,
                "unit_id": unit_id,
                "unit_name": UNIT_ENTITY_NAMES.get(unit_id, unit_id),
            }
        )
    return values


def _claim_number(value: str) -> float | None:
    match = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", value)
    if match is None:
        return None
    try:
        return float(match.group(0).replace(",", ""))
    except ValueError:
        return None


def _claim_year(value: str) -> int | None:
    match = re.search(r"\b(?:1[0-9]{3}|20[0-9]{2}|2100)\b", value)
    return int(match.group(0)) if match else None


def _quantity_unit_matches(claim_object: str, unit_name: str) -> bool:
    claim_key = comparable_text(claim_object)
    unit_key = comparable_text(unit_name)
    if not unit_key or unit_key in {"1", "unitless", "dimensionless"}:
        return True

    aliases = {
        "degrees celsius": {"degree celsius", "degrees celsius", "celsius", "c"},
        "degrees fahrenheit": {
            "degree fahrenheit",
            "degrees fahrenheit",
            "fahrenheit",
            "f",
        },
        "kelvin": {"kelvin", "k"},
        "kilometre": {"kilometre", "kilometer", "km"},
        "metre": {"metre", "meter", "m"},
        "kilogram": {"kilogram", "kg"},
        "gram": {"gram", "g"},
    }
    accepted = aliases.get(unit_key, {unit_key})
    return any(
        re.search(rf"(?:^|\s){re.escape(alias)}(?:$|\s)", claim_key)
        for alias in accepted
    )


def _compare_values(
    route: PropertyRoute,
    claim_object: str,
    statements: list[dict[str, Any]],
    target_entity: dict[str, Any] | None,
    entity_value_labels: dict[str, str] | None = None,
    allow_closed_refutation: bool = False,
) -> tuple[str, list[Any], str]:
    if not statements:
        return "NOT_DETERMINED", [], "The structured property has no usable value."

    if route.value_kind == "entity":
        values = _entity_values(statements)
        target_id = str((target_entity or {}).get("id", ""))
        label_map = entity_value_labels or {}
        target_matches_value_label = any(
            name_similarity(claim_object, label_map.get(entity_id, ""))
            >= 0.82
            for entity_id in values
        )
        if target_id in values or target_matches_value_label:
            return "SUPPORTS", values, "The structured property contains the claimed entity."
        if not target_id and not label_map:
            return "NOT_DETERMINED", values, "The target entity could not be resolved exactly."
        if (route.closed_world or allow_closed_refutation) and values:
            return "REFUTES", values, "A functional structured property contains a different entity."
        return "NOT_DETERMINED", values, "Absence from an open-world property is not treated as refutation."

    if route.value_kind == "string":
        values = _string_values(statements)
        target_key = comparable_text(claim_object)
        if any(comparable_text(value) == target_key for value in values):
            return "SUPPORTS", values, "The structured string equals the claimed value."
        if route.closed_world and values:
            return "REFUTES", values, "The structured string contains a different value."
        return "NOT_DETERMINED", values, "No conclusive structured string match was found."

    if route.value_kind == "time":
        values = _time_values(statements)
        target_year = _claim_year(claim_object)
        if target_year is None:
            return "NOT_DETERMINED", values, "The claim does not contain a supported four-digit year."
        if any(value["year"] == target_year for value in values):
            return "SUPPORTS", values, "The structured time contains the claimed year."
        if route.closed_world and values:
            return "REFUTES", values, "The structured time contains a different year."
        return "NOT_DETERMINED", values, "No conclusive structured time match was found."

    if route.value_kind == "quantity":
        values = _quantity_values(statements)
        target_amount = _claim_number(claim_object)
        if target_amount is None:
            return "NOT_DETERMINED", values, "The claimed numeric value could not be parsed."

        comparable_values = [
            value
            for value in values
            if _quantity_unit_matches(claim_object, str(value.get("unit_name", "")))
        ]
        matches = [
            value
            for value in comparable_values
            if math.isclose(
                float(value["amount"]),
                target_amount,
                rel_tol=0.001,
                abs_tol=0.01,
            )
        ]
        if matches:
            return "SUPPORTS", values, "The structured quantity equals the claimed value and unit."
        if route.closed_world and comparable_values:
            return "REFUTES", values, "The structured quantity contains a different value."
        return "NOT_DETERMINED", values, "No value with a safely comparable unit was found."

    return "NOT_DETERMINED", [], "The value type is not supported."


def resolve_country_via_administrative_hierarchy(
    anchor_entity: dict[str, Any],
    target_entity: dict[str, Any] | None,
    maximum_depth: int = 4,
) -> tuple[str, list[dict[str, Any]], str]:
    target_id = str((target_entity or {}).get("id", ""))
    if not target_id:
        return (
            "NOT_DETERMINED",
            [],
            "The target country could not be resolved exactly.",
        )

    pending = [str(anchor_entity.get("id", ""))]
    visited: set[str] = set()
    path: list[dict[str, Any]] = []

    for depth in range(maximum_depth + 1):
        next_pending: list[str] = []

        for entity_id in pending:
            if not entity_id or entity_id in visited:
                continue
            visited.add(entity_id)
            entity = _load_entity(entity_id, ("P17", "P131"))
            country_ids = _entity_values(_usable_statements(entity, "P17"))
            parent_ids = _entity_values(_usable_statements(entity, "P131"))
            path.append(
                {
                    "depth": depth,
                    "entity_id": entity_id,
                    "country_ids": country_ids,
                    "administrative_parent_ids": parent_ids,
                }
            )

            if target_id in country_ids:
                return (
                    "SUPPORTS",
                    path,
                    "The target country was found through live Wikidata "
                    "country or administrative-location properties.",
                )

            if country_ids:
                return (
                    "REFUTES",
                    path,
                    "The live Wikidata administrative hierarchy resolves "
                    "the subject to a different country.",
                )

            next_pending.extend(parent_ids[:5])

        pending = [
            entity_id for entity_id in next_pending if entity_id not in visited
        ]
        if not pending:
            break

    return (
        "NOT_DETERMINED",
        path,
        "No country value was found within the bounded live Wikidata "
        "administrative hierarchy.",
    )


def _apply_claim_polarity(verdict: str, is_negated: bool) -> str:
    if not is_negated:
        return verdict
    if verdict == "SUPPORTS":
        return "REFUTES"
    if verdict == "REFUTES":
        return "SUPPORTS"
    return verdict


def retrieve_structured_evidence(claim: str) -> dict[str, Any]:
    parsed = parse_structured_claim(claim)
    relation = str(parsed.get("relation", "unknown"))
    route = PROPERTY_ROUTES.get(relation)
    warnings = list(parsed.get("warnings", []))

    base_result: dict[str, Any] = {
        "available": True,
        "version": "2026.08-v3",
        "claim": normalize_text(claim),
        "parsed_claim": parsed,
        "eligible": False,
        "verdict": "NOT_DETERMINED",
        "confidence": 0.0,
        "evidence": [],
        "warnings": warnings,
        "retrieval_mode": "live_only",
        "cache_allowed": False,
        "persistent_cache_used": False,
        "automatic_enforcement_allowed": False,
    }

    if not parsed.get("suitable_for_stable_knowledge", False):
        warnings.append("The claim is not eligible for stable-knowledge structured retrieval.")
        return base_result

    if route is None:
        warnings.append("The parsed relationship has no structured property route yet.")
        return base_result

    base_result["eligible"] = True

    anchor_name = normalize_text(parsed.get(route.anchor, ""))
    target_name = normalize_text(parsed.get(route.target, ""))

    try:
        anchor_resolution_properties = (
            (*route.properties, "P131")
            if route.relation == "country_of"
            else route.properties
        )
        anchor_entity, entity = resolve_wikidata_anchor(
            anchor_name,
            anchor_resolution_properties,
        )
        if anchor_entity is None:
            warnings.append(f"Wikidata could not resolve the anchor entity exactly: {anchor_name}")
            return base_result

        target_entity = None
        if route.value_kind == "entity":
            target_entity = resolve_wikidata_entity(target_name)
            if target_entity is None:
                warnings.append(f"Wikidata could not resolve the target entity exactly: {target_name}")

        all_statements: list[dict[str, Any]] = []
        property_statement_counts: dict[str, int] = {}

        for property_id in route.properties:
            property_statements = _usable_statements(entity, property_id)
            property_statement_counts[property_id] = len(property_statements)
            all_statements.extend(property_statements)

        entity_value_labels = (
            load_entity_label_map(_entity_values(all_statements))
            if route.value_kind == "entity"
            else {}
        )

        allow_closed_refutation = bool(
            route.relation == "borders"
            and "country" in comparable_text(
                anchor_entity.get("description", "")
            )
            and bool(all_statements)
        )
        verdict, recorded_values, reason = _compare_values(
            route,
            target_name,
            all_statements,
            target_entity,
            entity_value_labels=entity_value_labels,
            allow_closed_refutation=allow_closed_refutation,
        )

        if route.relation == "country_of" and verdict == "NOT_DETERMINED":
            hierarchy_verdict, hierarchy_path, hierarchy_reason = (
                resolve_country_via_administrative_hierarchy(
                    anchor_entity,
                    target_entity,
                )
            )
            if hierarchy_verdict in {"SUPPORTS", "REFUTES"}:
                verdict = hierarchy_verdict
                recorded_values = hierarchy_path
                reason = hierarchy_reason
        verdict = _apply_claim_polarity(
            verdict,
            bool(parsed.get("is_negated", False)),
        )
        retrieved_at = datetime.now(timezone.utc).isoformat()
        confidence = 0.0
        if verdict == "SUPPORTS":
            confidence = 0.92
        elif verdict == "REFUTES":
            confidence = 0.86

        claim_subject = normalize_text(parsed.get("subject", ""))
        claim_object = normalize_text(parsed.get("object", ""))
        recorded_value_summary = normalize_text(
            str(recorded_values[:5])
        )
        evidence_excerpt = (
            f"Live Wikidata structured relationship check for subject "
            f"{claim_subject}, relationship {route.relation}, and claimed "
            f"object or value {claim_object}. Anchor entity "
            f"{anchor_entity.get('label', anchor_name)} "
            f"({anchor_entity['id']}) has Wikidata property "
            f"{', '.join(route.properties)}. Recorded values: "
            f"{recorded_value_summary or 'none'}. Result: {verdict}. "
            f"{reason}"
        )

        evidence_item = {
            "source_id": (
                f"wikidata_structured_v3:{anchor_entity['id']}:"
                f"{'+'.join(route.properties)}"
            ),
            "source_name": "Wikidata",
            "source_type": "live_structured_relationship",
            "trust_tier": 2,
            "official_source": False,
            "retrieved_live": True,
            "retrieved_at": retrieved_at,
            "cache_allowed": False,
            "title": (
                f"Wikidata structured check: {claim_subject} "
                f"{route.relation} {claim_object}"
            ),
            "excerpt": evidence_excerpt,
            "source_url": anchor_entity["source_url"],
            "anchor_entity": anchor_entity,
            "target_entity": target_entity,
            "relation": route.relation,
            "properties": list(route.properties),
            "property_statement_counts": property_statement_counts,
            "recorded_values": recorded_values[:MAXIMUM_RECORDED_VALUES],
            "recorded_entity_labels": entity_value_labels,
            "structured_relation_verdict": verdict,
            "stable_relation_verdict": verdict,
            "verified_relation": (
                route.relation if verdict in {"SUPPORTS", "REFUTES"} else "none"
            ),
            "relevance_score": 1.0,
            "reason": reason,
            "attribution": (
                f"Source: Wikidata. Original: {anchor_entity['source_url']}. "
                f"Accessed live at {retrieved_at}."
            ),
        }

        base_result.update(
            {
                "verdict": verdict,
                "confidence": confidence,
                "anchor_entity": anchor_entity,
                "target_entity": target_entity,
                "route": {
                    "relation": route.relation,
                    "anchor": route.anchor,
                    "target": route.target,
                    "properties": list(route.properties),
                    "value_kind": route.value_kind,
                    "closed_world": route.closed_world,
                },
                "evidence": [evidence_item],
                "reason": reason,
            }
        )

    except requests.RequestException as error:
        warnings.append(
            "Wikidata live retrieval failed without bypassing the source: "
            f"{type(error).__name__}: {error}"
        )
    except (ValueError, TypeError, KeyError) as error:
        warnings.append(
            "Wikidata returned unusable structured data: "
            f"{type(error).__name__}: {error}"
        )

    return base_result


def get_structured_evidence_service_status() -> dict[str, Any]:
    return {
        "available": True,
        "version": "2026.08-v3",
        "route_count": len(PROPERTY_ROUTES),
        "relations": sorted(PROPERTY_ROUTES),
        "retrieval_mode": "live_only",
        "cache_allowed": False,
        "persistent_cache_used": False,
        "uses_holdout_records": False,
        "automatic_enforcement_allowed": False,
    }


__all__ = [
    "get_structured_evidence_service_status",
    "resolve_wikidata_entity",
    "retrieve_structured_evidence",
]
