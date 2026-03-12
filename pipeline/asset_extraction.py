"""Script preprocessing and asset extraction node."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from prompts.asset_extraction import (
    ASSET_EXTRACTION_SYSTEM_PROMPT,
    build_asset_extraction_user_prompt,
)
from schemas.asset_registry import AssetRegistry
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


def build_run_artifacts(output_root: Path) -> AssetExtractionArtifacts:
    run_dir = output_root / time.strftime("%Y%m%d-%H%M%S")
    input_dir = run_dir / "01_input"
    asset_dir = run_dir / "02_assets"
    input_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    return AssetExtractionArtifacts(run_dir=run_dir, input_dir=input_dir, asset_dir=asset_dir)


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def dump_model(model: Any) -> Any:
    if hasattr(model, "model_dump"):
        return model.model_dump(mode="json", exclude_none=True)
    return model


def extract_text_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif hasattr(item, "type") and getattr(item, "type", None) == "text":
                parts.append(str(getattr(item, "text", "")))
        return "\n".join(part for part in parts if part)
    return str(content)


def normalize_asset_registry_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    genre = normalized.get("genre")
    if isinstance(genre, list):
        normalized["genre"] = " / ".join(str(item).strip() for item in genre if str(item).strip())

    story_meta = normalized.get("story_meta")
    if isinstance(story_meta, dict) and "era" not in story_meta and "era_background" in story_meta:
        story_meta = dict(story_meta)
        story_meta["era"] = story_meta.pop("era_background")
        normalized["story_meta"] = story_meta

    for character in normalized.get("characters", []):
        relationships = character.get("relationship_targets")
        if not isinstance(relationships, list):
            continue
        for relationship in relationships:
            if "character_id" not in relationship and "target_id" in relationship:
                relationship["character_id"] = relationship.pop("target_id")
            if "description" not in relationship:
                relationship["description"] = relationship.get("relation", "")

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
    dry_run: bool = False,
) -> AssetExtractionArtifacts:
    raw_text = script_path.read_text(encoding="utf-8")
    normalized_text = normalize_script_text(raw_text)
    if not normalized_text:
        raise ValueError(f"Script file is empty after normalization: {script_path}")

    artifacts = build_run_artifacts(output_root)
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
