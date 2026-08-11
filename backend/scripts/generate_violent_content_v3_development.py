from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path


VERSION = "2026.08-v3-development-r2"
ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = ROOT / "datasets" / "development" / "violent_content_v3"


@dataclass(frozen=True)
class Record:
    record_id: str
    split: str
    family_id: str
    semantic_class: str
    expected_category: str
    expected_action: str
    human_review_required: bool
    text: str


def add_family(
    records: list[Record],
    *,
    family_id: str,
    semantic_class: str,
    expected_category: str,
    expected_action: str,
    human_review_required: bool,
    templates: tuple[str, ...],
    values: tuple[str, ...],
    split: str,
) -> None:
    for template in templates:
        for value in values:
            text = template.format(value=value).strip()
            digest = hashlib.sha256(
                f"{family_id}|{text}".encode("utf-8")
            ).hexdigest()[:12]
            records.append(
                Record(
                    record_id=f"VC3-{digest}",
                    split=split,
                    family_id=family_id,
                    semantic_class=semantic_class,
                    expected_category=expected_category,
                    expected_action=expected_action,
                    human_review_required=human_review_required,
                    text=text,
                )
            )


def build_records() -> list[Record]:
    records: list[Record] = []

    graphic_train_values = (
        "a mutilated body with exposed tissue",
        "a severed limb beside the victim",
        "exposed internal organs",
        "a dismembered body",
        "a victim undergoing torture",
        "charred human remains",
        "a crushed skull with visible injuries",
        "a decapitated body",
    )
    graphic_validation_values = (
        "a deep open wound with exposed bone",
        "blood-covered human remains",
        "a corpse torn apart by an explosion",
        "a victim with severe visible burns",
        "a body missing multiple parts",
        "a prisoner being physically tortured",
        "a detached hand lying beside a body",
        "a fatal injury with visible tissue",
    )
    graphic_train = (
        "The uploaded image visibly shows {value}.",
        "The video contains a close view of {value}.",
        "The camera records {value} without censorship.",
        "The scene graphically depicts {value}.",
    )
    graphic_validation = (
        "Viewers can clearly see {value} in the footage.",
        "An uncensored frame presents {value}.",
    )
    add_family(
        records,
        family_id="graphic_train_depiction",
        semantic_class="graphic_violence",
        expected_category="Violent Content",
        expected_action="Refer to human review",
        human_review_required=True,
        templates=graphic_train,
        values=graphic_train_values,
        split="train",
    )
    add_family(
        records,
        family_id="graphic_validation_visibility",
        semantic_class="graphic_violence",
        expected_category="Violent Content",
        expected_action="Refer to human review",
        human_review_required=True,
        templates=graphic_validation,
        values=graphic_validation_values,
        split="validation",
    )

    context_train_values = (
        "the aftermath of an armed conflict",
        "a historical battle",
        "a reported assault",
        "violence-prevention procedures",
        "a fictional fight scene",
        "a criminal investigation",
        "the effects of war",
        "a censored injury",
    )
    context_validation_values = (
        "peacekeeping work following violent civil unrest",
        "a court case involving a fatal assault",
        "an emergency response after a violent attack",
        "the casualties of a historical military campaign",
        "a censored reconstruction of a murder investigation",
        "training about responding to armed violence",
        "public-health measures for preventing violent injury",
        "a fictional battle sequence",
    )
    context_train = (
        "A non-graphic news report discusses {value} without showing injuries.",
        "A documentary explains {value} using blurred archival material.",
        "An educational lesson examines {value} with a content warning.",
        "The article describes {value} in a factual and non-graphic way.",
    )
    context_validation = (
        "A museum presentation covers {value}, but no graphic detail is visible.",
        "A safety course refers to {value} for prevention and awareness.",
    )
    add_family(
        records,
        family_id="context_train_reporting",
        semantic_class="allowed_context",
        expected_category="Violent Content",
        expected_action="Allow with sensitive-content warning",
        human_review_required=False,
        templates=context_train,
        values=context_train_values,
        split="train",
    )
    add_family(
        records,
        family_id="context_validation_education",
        semantic_class="allowed_context",
        expected_category="Violent Content",
        expected_action="Allow with sensitive-content warning",
        human_review_required=False,
        templates=context_validation,
        values=context_validation_values,
        split="validation",
    )

    threat_train_values = (
        "break your arms when you arrive",
        "smash your face outside",
        "hurt you after work",
        "attack your family tonight",
        "stab you when I find you",
        "beat you in the parking area",
        "shoot you if you return",
        "burn your home while you are inside",
    )
    threat_validation_values = (
        "crush your jaw near the station",
        "break your legs after the meeting",
        "come after you at your house",
        "make you suffer for refusing",
        "harm your brother tomorrow",
        "leave you badly injured",
        "bring a weapon and attack you",
        "set fire to your room while you sleep",
    )
    threat_train = (
        "I will {value}.",
        "Watch your back because I am going to {value}.",
        "I swear that I will {value}.",
        "Meet me there and I will {value}.",
    )
    threat_validation = (
        "You cannot hide; I plan to {value}.",
        "This is your warning: I intend to {value}.",
    )
    add_family(
        records,
        family_id="threat_train_direct",
        semantic_class="targeted_threat",
        expected_category="Cyberbullying & Harassment",
        expected_action="Refer to human review",
        human_review_required=True,
        templates=threat_train,
        values=threat_train_values,
        split="train",
    )
    add_family(
        records,
        family_id="threat_validation_intimidation",
        semantic_class="targeted_threat",
        expected_category="Cyberbullying & Harassment",
        expected_action="Refer to human review",
        human_review_required=True,
        templates=threat_validation,
        values=threat_validation_values,
        split="validation",
    )

    safe_train_values = (
        "the singer killed it on stage",
        "the photographer shot a wedding portrait",
        "the software terminated a frozen process",
        "the team destroyed the competition in sales",
        "the striker took a shot at goal",
        "the pesticide kills weeds",
        "the doctor treated a routine fracture",
        "the students studied a diagram of organs",
    )
    safe_validation_values = (
        "the audience exploded with applause",
        "the editor cut a paragraph from the article",
        "the camera captured a family celebration",
        "the chess player attacked the opponent's queen",
        "the battery died during the journey",
        "the spicy sauce has a powerful kick",
        "the surgeon discussed an anatomical model",
        "the coach reviewed a contact-free practice drill",
    )
    safe_train = (
        "{value}.",
        "Yesterday, {value}.",
        "The report notes that {value}.",
        "People observed that {value}.",
    )
    safe_validation = (
        "According to the summary, {value}.",
        "During the day, {value}.",
    )
    add_family(
        records,
        family_id="safe_train_boundary",
        semantic_class="safe_or_other",
        expected_category="Normal/Ignore",
        expected_action="Allow",
        human_review_required=False,
        templates=safe_train,
        values=safe_train_values,
        split="train",
    )
    add_family(
        records,
        family_id="safe_validation_boundary",
        semantic_class="safe_or_other",
        expected_category="Normal/Ignore",
        expected_action="Allow",
        human_review_required=False,
        templates=safe_validation,
        values=safe_validation_values,
        split="validation",
    )

    unique: dict[str, Record] = {}
    for record in records:
        normalized = " ".join(record.text.casefold().split())
        if normalized in unique:
            raise RuntimeError(f"Duplicate text generated: {record.text}")
        unique[normalized] = record
    return sorted(records, key=lambda item: item.record_id)


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    records = build_records()
    dataset_path = OUTPUT_DIR / "development.csv"
    manifest_path = OUTPUT_DIR / "manifest.json"

    fields = list(asdict(records[0]).keys())
    with dataset_path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow(asdict(record))

    split_counts = Counter(record.split for record in records)
    class_counts = Counter(record.semantic_class for record in records)
    split_class_counts = Counter(
        f"{record.split}:{record.semantic_class}" for record in records
    )
    train_families = {
        record.family_id for record in records if record.split == "train"
    }
    validation_families = {
        record.family_id for record in records if record.split == "validation"
    }
    overlap = sorted(train_families & validation_families)
    if overlap:
        raise RuntimeError(f"Family leakage detected: {overlap}")

    manifest = {
        "version": VERSION,
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "record_count": len(records),
        "dataset_sha256": file_sha256(dataset_path),
        "split_counts": dict(sorted(split_counts.items())),
        "class_counts": dict(sorted(class_counts.items())),
        "split_class_counts": dict(sorted(split_class_counts.items())),
        "family_overlap": overlap,
        "policy_boundary": {
            "graphic_violence": "Violent Content",
            "allowed_context": "Violent Content with warning",
            "targeted_threat": "Cyberbullying & Harassment",
            "safe_or_other": "Normal/Ignore or no specialist override",
        },
        "prohibited_sources": [
            "violent-content-v1-rc1 holdout",
            "violent-content-v2-rc1 holdout",
        ],
        "notice": (
            "Synthetic development data only. This is not independent "
            "accuracy evidence and must not be added to a holdout."
        ),
    }
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    print("VIOLENT CONTENT V3 DEVELOPMENT DATASET")
    print("=" * 60)
    print(f"Version: {VERSION}")
    print(f"Records: {len(records)}")
    print(f"Train: {split_counts['train']}")
    print(f"Validation: {split_counts['validation']}")
    print(f"Family overlap: {len(overlap)}")
    print("\nCLASS COUNTS")
    print("-" * 60)
    for label, count in sorted(class_counts.items()):
        print(f"{label}: {count}")
    print(f"\nDataset: {dataset_path}")
    print(f"Manifest: {manifest_path}")
    print("\nThis is development data, not independent accuracy.")
    print("The retired RC1 holdouts were not read or modified.")


if __name__ == "__main__":
    main()
