"""Script preprocessing and asset extraction node."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prompts.asset_extraction import (
    ASSET_EXTRACTION_SYSTEM_PROMPT,
    build_asset_extraction_user_prompt,
)
from schemas.asset_registry import AssetRegistry
from pipeline.io import dump_model, extract_text_content, write_json
from pipeline.runtime import TextModelConfig, build_text_client


@dataclass(frozen=True, slots=True)
class AssetExtractionArtifacts:
    run_dir: Path
    input_dir: Path
    asset_dir: Path


def normalize_script_text(raw_text: str) -> str:
    unified = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = []
    for block in unified.split("\n\n"):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if lines:
            paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs).strip()


def resolve_next_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    existing_indexes = []
    for child in output_root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith("run"):
            continue
        suffix = name[3:]
        if suffix.isdigit():
            existing_indexes.append(int(suffix))
    next_index = max(existing_indexes, default=-1) + 1
    return output_root / f"run{next_index}"


def build_run_artifacts(output_root: Path) -> AssetExtractionArtifacts:
    run_dir = resolve_next_run_dir(output_root)
    input_dir = run_dir / "01_input"
    asset_dir = run_dir / "02_assets"
    input_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    return AssetExtractionArtifacts(run_dir=run_dir, input_dir=input_dir, asset_dir=asset_dir)


def build_existing_run_artifacts(run_dir: Path) -> AssetExtractionArtifacts:
    input_dir = run_dir / "01_input"
    asset_dir = run_dir / "02_assets"
    input_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    return AssetExtractionArtifacts(run_dir=run_dir, input_dir=input_dir, asset_dir=asset_dir)


def normalize_asset_registry_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("schema_version") == "1.0.0":
        normalized["schema_version"] = "1.0"

    genre = normalized.get("genre")
    if isinstance(genre, list):
        normalized["genre"] = " / ".join(str(item).strip() for item in genre if str(item).strip())

    story_meta = normalized.get("story_meta")
    if isinstance(story_meta, dict) and "era" not in story_meta and "era_background" in story_meta:
        story_meta = dict(story_meta)
        story_meta["era"] = story_meta.pop("era_background")
        normalized["story_meta"] = story_meta

    for character in normalized.get("characters", []):
        age = character.get("age")
        if isinstance(age, int | float):
            character["age"] = str(age)
        identity_markers = character.get("identity_markers")
        if isinstance(identity_markers, str):
            marker = identity_markers.strip()
            character["identity_markers"] = [marker] if marker else []
        relationships = character.get("relationship_targets")
        if not isinstance(relationships, list):
            relationships = []
            character["relationship_targets"] = relationships
        for relationship in relationships:
            if "character_id" not in relationship and "target_id" in relationship:
                relationship["character_id"] = relationship.pop("target_id")
            if "description" not in relationship:
                relationship["description"] = relationship.get("relation", "")

        visual_profile = character.get("visual_profile")
        if not isinstance(visual_profile, dict):
            visual_profile = {}
            character["visual_profile"] = visual_profile
        silhouette_keywords = visual_profile.get("silhouette_keywords")
        if isinstance(silhouette_keywords, str):
            keyword = silhouette_keywords.strip()
            visual_profile["silhouette_keywords"] = [keyword] if keyword else []

        costume_profile = character.get("costume_profile")
        if not isinstance(costume_profile, dict):
            costume_profile = {}
            character["costume_profile"] = costume_profile
        for list_key in ("secondary_colors", "trim_details", "accessories"):
            value = costume_profile.get(list_key)
            if isinstance(value, str):
                item = value.strip()
                costume_profile[list_key] = [item] if item else []

        visual_identity_lock = character.get("visual_identity_lock")
        if not isinstance(visual_identity_lock, dict):
            visual_identity_lock = {}
            character["visual_identity_lock"] = visual_identity_lock
        for list_key in ("required_features", "forbidden_drifts"):
            value = visual_identity_lock.get(list_key)
            if isinstance(value, str):
                item = value.strip()
                visual_identity_lock[list_key] = [item] if item else []

    return normalized


def create_script_clean_payload(script_path: Path, normalized_text: str) -> dict[str, Any]:
    paragraphs = normalized_text.split("\n\n") if normalized_text else []
    return {
        "source_path": str(script_path.resolve()),
        "source_script_name": script_path.stem,
        "character_count": len(normalized_text),
        "paragraph_count": len(paragraphs),
        "text": normalized_text,
    }


def extract_asset_registry(
    *,
    script_path: Path,
    model_config: TextModelConfig,
    output_root: Path,
    run_dir: Path | None = None,
    dry_run: bool = False,
) -> AssetExtractionArtifacts:
    raw_text = script_path.read_text(encoding="utf-8")
    normalized_text = normalize_script_text(raw_text)
    if not normalized_text:
        raise ValueError(f"Script file is empty after normalization: {script_path}")

    artifacts = build_existing_run_artifacts(run_dir) if run_dir is not None else build_run_artifacts(output_root)
    script_clean_payload = create_script_clean_payload(script_path, normalized_text)
    script_clean_text_path = artifacts.input_dir / "script_clean.txt"
    script_clean_json_path = artifacts.input_dir / "script_clean.json"
    script_clean_text_path.write_text(normalized_text, encoding="utf-8")
    write_json(script_clean_json_path, script_clean_payload)

    user_prompt = build_asset_extraction_user_prompt(script_path.stem, normalized_text)
    request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": ASSET_EXTRACTION_SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "source_script_name": script_path.stem,
    }
    request_path = artifacts.asset_dir / "asset_extraction_request.json"
    write_json(request_path, request_payload)

    if dry_run:
        return artifacts

    client = build_text_client(model_config)
    response = client.chat.completions.create(
        model=model_config.model_name,
        messages=[
            {"role": "system", "content": ASSET_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.0,
        max_tokens=8192,
        timeout=600.0,
    )
    response_path = artifacts.asset_dir / "asset_extraction_response.json"
    write_json(response_path, dump_model(response))

    content = extract_text_content(response.choices[0].message.content)
    parsed = normalize_asset_registry_payload(json.loads(content))
    registry = AssetRegistry.model_validate(parsed)
    registry_path = artifacts.asset_dir / "asset_registry.json"
    write_json(registry_path, registry.model_dump(mode="json"))

    return artifacts
