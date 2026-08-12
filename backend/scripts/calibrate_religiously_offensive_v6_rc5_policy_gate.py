from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import unicodedata
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
from sentence_transformers import SentenceTransformer


ROOT = Path(__file__).resolve().parents[2]
BASE_CANDIDATE_NAME = "religiously-offensive-v5-rc4"
BASE_CANDIDATE = ROOT / "backend" / "storage" / "candidates" / BASE_CANDIDATE_NAME
BASE_MANIFEST = BASE_CANDIDATE / "manifest.json"
BASE_VERDICT = BASE_CANDIDATE / "independent_evaluation_verdict.json"
BASE_MODEL = BASE_CANDIDATE / "model" / "classifier.joblib"
BASE_CONFIG = BASE_CANDIDATE / "model" / "config.json"
VALIDATION_DATASET = (
    ROOT
    / "datasets"
    / "development"
    / "religiously_offensive_v4_rc3"
    / "validation.csv"
)

CANDIDATE = "religiously-offensive-v6-rc5-development"
MODEL_DIRECTORY = (
    ROOT / "backend" / "storage" / "models" / "religiously_offensive_v6_rc5"
)
MODEL_ARTIFACT = MODEL_DIRECTORY / "classifier.joblib"
MODEL_CONFIG = MODEL_DIRECTORY / "config.json"
REPORT_DIRECTORY = (
    ROOT
    / "reports"
    / "evaluation"
    / "religiously_offensive"
    / "v6_rc5_policy_gate_development"
)
REPORT_PATH = REPORT_DIRECTORY / "validation_report.json"

RELIGIOUS_LABEL = "religiously_offensive"
NO_OVERRIDE = "no_religious_override"
POLICY_GATE_VERSION = "religious-policy-gate-2026.08-v1"


SAFE_CONTEXT_PATTERN = re.compile(
    r"\b(?:"
    r"news|journalist|journalism|article|report|reported|reporting|"
    r"documentary|historian|history|historical|archive|museum|catalogue|"
    r"court|legal|police|research|researcher|study|academic|scholar|"
    r"lesson|classroom|educational|workshop|seminar|"
    r"public[- ]service|safety campaign|prevention|restoration|restored|"
    r"repair|repaired|conservator|interfaith|cultural context|"
    r"good[- ]faith criticism|respectful criticism|respectfully critiques?|"
    r"condemn(?:s|ed|ing)?|oppose(?:s|d|ing)?|warn(?:s|ed|ing)? against|"
    r"does not endorse|without endorsing|as evidence|provides? context"
    r")\b",
    re.IGNORECASE,
)
NEGATED_HARM_PATTERN = re.compile(
    r"\b(?:do not|don't|never|must not|should not|shouldn't|stop|avoid|prevent)\b"
    r".{0,120}\b(?:burn|destroy|damage|desecrate|deface|smash|mock|insult|"
    r"ridicule|vandalize|vandalise|demolish|profane|humiliate)\b",
    re.IGNORECASE,
)
HARM_ADVOCACY_PATTERN = re.compile(
    r"\b(?:calls? (?:on|for)|urges?|asks? (?:people|listeners|participants|"
    r"followers|viewers|users)|encourages?|orders?|demands?|commands?|"
    r"promotes?|(?<!not )endorse(?:s|d|ing)?|praises?|celebrates?|plans?|"
    r"vows?|threatens?|"
    r"wants?|should|must|need to|let us|join us)\b",
    re.IGNORECASE,
)
FOLLOWER_REFERENCE_PATTERN = re.compile(
    r"\b(?:followers?|adherents?|devotees?|believers?|worshippers?|"
    r"congregants?|members?|families|workers|students|people|community|group)\b"
    r".{0,80}\b(?:religion|religious|faith|sect|denomination)\b|"
    r"\b(?:religion|religious|faith|sect|denomination)\b"
    r".{0,80}\b(?:followers?|adherents?|devotees?|believers?|worshippers?|"
    r"congregants?|members?|families|workers|students|people|community|group)\b",
    re.IGNORECASE,
)
FOLLOWER_HARM_PATTERN = re.compile(
    r"\b(?:inferior|parasites?|subhuman|not human|less than human|criminals?|"
    r"dangerous|exclude|expel|segregate|deny|refuse|remove|ban|boycott|"
    r"attack|harm|evict|strip|lose .*?rights?|forced? to leave|driven away|"
    r"should not exist|unfit for citizenship)\b",
    re.IGNORECASE,
)
OBJECT_OR_PLACE_PATTERN = re.compile(
    r"\b(?:holy|sacred|religious|devotional|consecrated|ceremonial|revered)\s+"
    r"(?:book|text|scripture|manuscript|scroll|emblem|symbol|icon|image|"
    r"portrait|painting|statue|sculpture|relic|object|artefact|artifact|"
    r"prayer beads|worship artefact|worship artifact|"
    r"vessel|banner|flag|monument|carving|artwork|site|sanctuary|centre|center|"
    r"hall|building)|"
    r"\b(?:temple|church|mosque|gurudwara|gurdwara|shrine|chapel|monastery|"
    r"sanctuary|prayer beads|worship artefact|worship artifact|"
    r"altar|prayer hall|prayer space|place of worship|worship building|"
    r"worship centre|worship center|religious building|religious centre|"
    r"religious center)\b",
    re.IGNORECASE,
)
FIGURE_PATTERN = re.compile(
    r"\b(?:deity|deities|god|gods|prophet|prophets|faith founder|"
    r"religious founder|religious figure|religious figurehead|spiritual leader|"
    r"religious leader|faith leader|sacred figure|divine figure|holy person|"
    r"revered teacher|religious teacher|spiritual guide)\b",
    re.IGNORECASE,
)
PHYSICAL_ATTACK_PATTERN = re.compile(
    r"\b(?:burn|burned|burning|incinerate|scorch|torch|set .*?ablaze|"
    r"set .*?fire|destroy|damage|desecrate|profane|deface|disfigure|smash|"
    r"shatter|break|crush|tear|rip|shred|cut|slash|hack|trample|stomp|kick|"
    r"drag|spit|soil|smear|coat .*?filth|throw .*?(?:fire|sewer|garbage)|"
    r"vandalize|vandalise|mutilate|dismantle|demolish|bulldoze|raze|level|"
    r"wreck|ransack|obliterate|spray .*?(?:obscene|degrading)|"
    r"paint .*?(?:obscene|degrading)|cover .*?(?:obscene|degrading))\b",
    re.IGNORECASE,
)
FIGURE_ATTACK_PATTERN = re.compile(
    r"\b(?:mock|ridicule|vilify|demean|humiliate|insult|degrade|revile|deride|"
    r"slander|lampoon|denigrate|abuse|obscene|vile|degrading|abusive|"
    r"repulsive|morphed|caricature|parody|contemptuous)\b",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def normalize(text: str) -> str:
    return " ".join(
        unicodedata.normalize("NFKC", str(text or "")).casefold().split()
    )


def require_file(path: Path) -> None:
    if not path.is_file():
        raise FileNotFoundError(f"Required RC5 development file is missing: {path}")


def verify_base() -> tuple[dict[str, Any], dict[str, Any]]:
    for path in (
        BASE_MANIFEST,
        BASE_VERDICT,
        BASE_MODEL,
        BASE_CONFIG,
        VALIDATION_DATASET,
    ):
        require_file(path)
    manifest = json.loads(BASE_MANIFEST.read_text(encoding="utf-8"))
    verdict = json.loads(BASE_VERDICT.read_text(encoding="utf-8"))
    config = json.loads(BASE_CONFIG.read_text(encoding="utf-8"))
    if manifest.get("candidate") != BASE_CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC4 base manifest.")
    if verdict.get("candidate") != BASE_CANDIDATE_NAME:
        raise RuntimeError("Unexpected RC4 base verdict.")
    if verdict.get("passed_independent_readiness_gate") is not False:
        raise RuntimeError("RC5 development is only permitted after RC4 failure.")
    if verdict.get("holdout_may_modify_rc4") is not False:
        raise RuntimeError("The RC4 holdout contract is invalid.")
    if config.get("candidate") != "religiously-offensive-v5-rc4-development":
        raise RuntimeError("Unexpected RC4 model configuration.")
    for artifact in manifest.get("artifacts", []):
        path = BASE_CANDIDATE / str(artifact["relative_path"])
        require_file(path)
        if sha256_file(path) != str(artifact["sha256"]):
            raise RuntimeError(f"Frozen RC4 artifact hash mismatch: {path.name}")
    return manifest, config


def load_validation() -> list[dict[str, str]]:
    with VALIDATION_DATASET.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise RuntimeError("RC5 validation input is empty.")
    return rows


def safe_or_boundary_veto(text: str) -> tuple[bool, str]:
    value = normalize(text)
    if NEGATED_HARM_PATTERN.search(value):
        return True, "safe_reporting_education_condemnation_or_negation"
    if SAFE_CONTEXT_PATTERN.search(value) and not HARM_ADVOCACY_PATTERN.search(value):
        return True, "safe_reporting_education_condemnation_or_negation"
    if FOLLOWER_REFERENCE_PATTERN.search(value) and FOLLOWER_HARM_PATTERN.search(value):
        return True, "protected_follower_hate_boundary"
    return False, ""


def sacred_attack_anchor(text: str) -> bool:
    value = normalize(text)
    object_or_place = bool(OBJECT_OR_PLACE_PATTERN.search(value))
    figure = bool(FIGURE_PATTERN.search(value))
    physical = bool(PHYSICAL_ATTACK_PATTERN.search(value))
    figure_attack = bool(FIGURE_ATTACK_PATTERN.search(value))
    return bool((object_or_place and physical) or (figure and (physical or figure_attack)))


def semantic_religious_signal(
    classifier: Any,
    probabilities: np.ndarray,
    config: dict[str, Any],
) -> np.ndarray:
    classes = np.asarray(classifier.classes_)
    religious_index = int(np.where(classes == RELIGIOUS_LABEL)[0][0])
    policy = config["religious_only_guard_policy"]
    threshold = float(policy["religious_probability_threshold"])
    minimum_margin = float(policy["minimum_religious_margin"])
    output: list[bool] = []
    for scores in probabilities:
        religious_score = float(scores[religious_index])
        competing_score = float(np.max(np.delete(scores, religious_index)))
        output.append(
            religious_score >= threshold
            and religious_score - competing_score >= minimum_margin
        )
    return np.array(output)


def safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def main() -> None:
    manifest, base_config = verify_base()
    rows = load_validation()
    classifier = joblib.load(BASE_MODEL)
    encoder = SentenceTransformer(
        str(base_config["embedding_model"]),
        revision=str(base_config["embedding_model_revision"]),
        device="cpu",
    )
    texts = [row["text"] for row in rows]
    truth = np.array([row["label"] == RELIGIOUS_LABEL for row in rows])
    embeddings = encoder.encode(
        texts,
        batch_size=32,
        normalize_embeddings=True,
        show_progress_bar=True,
    )
    probabilities = classifier.predict_proba(embeddings)
    semantic = semantic_religious_signal(classifier, probabilities, base_config)
    vetoes = [safe_or_boundary_veto(text) for text in texts]
    anchors = np.array([sacred_attack_anchor(text) for text in texts])
    predicted = np.array(
        [
            bool(semantic[index] and anchors[index] and not vetoes[index][0])
            for index in range(len(rows))
        ]
    )

    tp = int(np.sum(truth & predicted))
    tn = int(np.sum(~truth & ~predicted))
    fp = int(np.sum(~truth & predicted))
    fn = int(np.sum(truth & ~predicted))
    precision = safe_divide(tp, tp + fp)
    recall = safe_divide(tp, tp + fn)
    specificity = safe_divide(tn, tn + fp)
    f1 = safe_divide(2 * precision * recall, precision + recall)
    accuracy = safe_divide(tp + tn, len(rows))

    grouped_indices: dict[str, list[int]] = defaultdict(list)
    for index, row in enumerate(rows):
        grouped_indices[row["family"]].append(index)
    family_results: dict[str, dict[str, Any]] = {}
    for family, indices in sorted(grouped_indices.items()):
        correct = sum(bool(predicted[index]) == bool(truth[index]) for index in indices)
        family_results[family] = {
            "records": len(indices),
            "correct": int(correct),
            "accuracy": round(correct / len(indices), 4),
        }
    minimum_family_accuracy = min(item["accuracy"] for item in family_results.values())
    neutral_indices = [
        index
        for index, row in enumerate(rows)
        if row["family"] == "neutral_religious_validation"
    ]
    neutral_safe_rate = safe_divide(
        sum(not predicted[index] for index in neutral_indices),
        len(neutral_indices),
    )
    safe_veto_count = sum(reason.startswith("safe_") for _, reason in vetoes)
    follower_veto_count = sum(reason == "protected_follower_hate_boundary" for _, reason in vetoes)
    anchor_count = int(np.sum(anchors))
    category_mix_failures = fp
    passed = bool(
        accuracy >= 0.95
        and precision >= 0.95
        and recall >= 0.90
        and specificity >= 0.98
        and f1 >= 0.92
        and minimum_family_accuracy >= 0.80
        and neutral_safe_rate == 1.0
        and category_mix_failures == 0
    )

    MODEL_DIRECTORY.mkdir(parents=True, exist_ok=True)
    REPORT_DIRECTORY.mkdir(parents=True, exist_ok=True)
    shutil.copy2(BASE_MODEL, MODEL_ARTIFACT)
    config = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE_NAME,
        "base_classifier_sha256": sha256_file(BASE_MODEL),
        "embedding_model": base_config["embedding_model"],
        "embedding_model_revision": base_config["embedding_model_revision"],
        "semantic_guard_policy": base_config["religious_only_guard_policy"],
        "policy_gate_version": POLICY_GATE_VERSION,
        "policy_gate_source_sha256": sha256_file(Path(__file__).resolve()),
        "requires_semantic_signal": True,
        "requires_sacred_attack_anchor": True,
        "safe_context_veto_enabled": True,
        "protected_follower_veto_enabled": True,
        "follower_boundary_output_enabled": False,
        "follower_boundary_owner": "Hate Speech & Discrimination V7",
        "permitted_active_output": "Religiously Offensive Content only",
        "development_metrics": {
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "specificity": round(specificity, 4),
            "f1": round(f1, 4),
            "minimum_family_accuracy": minimum_family_accuracy,
            "neutral_religious_safe_rate": round(neutral_safe_rate, 4),
            "category_mix_failures": category_mix_failures,
        },
        "passed_development_gate": passed,
        "automatic_enforcement_allowed": False,
        "independently_validated": False,
        "connected_to_live_moderation": False,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    MODEL_CONFIG.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
    report = {
        "candidate": CANDIDATE,
        "base_candidate": BASE_CANDIDATE_NAME,
        "validation_records": len(rows),
        "validation_dataset_sha256": manifest["datasets"]["validation"]["sha256"],
        "accuracy": round(accuracy, 4),
        "religious_precision": round(precision, 4),
        "religious_recall": round(recall, 4),
        "religious_f1": round(f1, 4),
        "nonreligious_specificity": round(specificity, 4),
        "true_positives": tp,
        "true_negatives": tn,
        "false_positives": fp,
        "false_negatives": fn,
        "minimum_family_accuracy": minimum_family_accuracy,
        "neutral_religious_safe_rate": round(neutral_safe_rate, 4),
        "category_mix_failures": category_mix_failures,
        "safe_context_vetoes": safe_veto_count,
        "protected_follower_vetoes": follower_veto_count,
        "sacred_attack_anchors": anchor_count,
        "family_results": family_results,
        "passed_development_gate": passed,
        "rc4_holdout_report_predictions_or_cases_used": False,
        "rc4_verdict_status_read_only": True,
        "classifier_retrained": False,
        "connected_to_live_moderation": False,
        "automatic_enforcement_allowed": False,
        "evidence_limit": "Development policy-gate evidence, not independent accuracy.",
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print("RELIGIOUSLY OFFENSIVE CONTENT V6 RC5 POLICY-GATE DEVELOPMENT")
    print("=" * 60)
    print(f"Validation records: {len(rows)}")
    print(f"Accuracy: {accuracy * 100:.2f}%")
    print(f"Religious precision: {precision * 100:.2f}%")
    print(f"Religious recall: {recall * 100:.2f}%")
    print(f"Religious F1: {f1 * 100:.2f}%")
    print(f"Nonreligious specificity: {specificity * 100:.2f}%")
    print(f"Minimum family accuracy: {minimum_family_accuracy * 100:.2f}%")
    print(f"Neutral-religious safe routing: {neutral_safe_rate * 100:.2f}%")
    print(f"Category-mix failures: {category_mix_failures}")
    print(f"Safe-context vetoes: {safe_veto_count}")
    print(f"Protected-follower vetoes: {follower_veto_count}")
    print(f"Sacred-attack anchors: {anchor_count}")
    print("Follower-boundary output enabled: False")
    print("Follower-boundary owner: Hate Speech & Discrimination V7")
    print()
    print(f"Passed development gate: {passed}")
    print(f"Artifact: {MODEL_ARTIFACT}")
    print(f"Configuration: {MODEL_CONFIG}")
    print(f"Report: {REPORT_PATH}")
    print("RC4 holdout report, predictions, and cases used: False")
    print("Classifier retrained: False")
    print("Live moderation changed: False")
    print("This is development policy-gate evidence, not independent accuracy.")


if __name__ == "__main__":
    main()
