"""Style bible generation node."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.io import dump_model, extract_text_content, read_json, write_json
from pipeline.runtime import TextModelConfig, build_text_client
from prompts.style_bible import STYLE_BIBLE_SYSTEM_PROMPT, build_style_bible_user_prompt
from schemas.asset_registry import AssetRegistry
from schemas.style_bible import StyleBible


@dataclass(frozen=True, slots=True)
class StyleBibleArtifacts:
    run_dir: Path
    style_dir: Path


def resolve_run_dir(asset_registry_path: Path) -> Path:
    if asset_registry_path.name != "asset_registry.json":
        raise ValueError(f"Expected an asset_registry.json file: {asset_registry_path}")
    if asset_registry_path.parent.name != "02_assets":
        raise ValueError(f"Expected asset_registry.json under a 02_assets directory: {asset_registry_path}")
    return asset_registry_path.parent.parent


def build_style_artifacts(run_dir: Path) -> StyleBibleArtifacts:
    style_dir = run_dir / "03_style"
    style_dir.mkdir(parents=True, exist_ok=True)
    return StyleBibleArtifacts(run_dir=run_dir, style_dir=style_dir)


def normalize_style_bible_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "colorPalette": "color_palette",
        "characterDesignRules": "character_design_rules",
        "sceneDesignRules": "scene_design_rules",
        "lightingStyle": "lighting_style",
        "textureStyle": "texture_style",
        "compositionRules": "composition_rules",
        "assetCardRules": "asset_card_rules",
        "moodKeywords": "mood_keywords",
        "negativeKeywords": "negative_keywords",
        "consistencyAnchors": "consistency_anchors",
        "storyTone": "story_tone",
        "visualStyle": "visual_style",
        "worldSetting": "world_setting",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    color_palette = normalized.get("color_palette")
    if isinstance(color_palette, dict):
        color_palette = dict(color_palette)
        if "skin_tones" not in color_palette and "skinTones" in color_palette:
            color_palette["skin_tones"] = color_palette.pop("skinTones")
        for key in ("primary", "secondary", "accent", "skin_tones"):
            value = color_palette.get(key)
            if isinstance(value, list):
                color_palette[key] = " / ".join(str(item).strip() for item in value if str(item).strip())
        normalized["color_palette"] = color_palette

    character_rules = normalized.get("character_design_rules")
    if isinstance(character_rules, dict):
        character_rules = dict(character_rules)
        if "face_rendering" not in character_rules and "eyeStyle" in character_rules:
            character_rules["face_rendering"] = character_rules.pop("eyeStyle")
        if "detail_level" not in character_rules and "detailLevel" in character_rules:
            character_rules["detail_level"] = character_rules.pop("detailLevel")
        if "hair_rendering" not in character_rules:
            character_rules["hair_rendering"] = ""
        if "costume_rendering" not in character_rules:
            character_rules["costume_rendering"] = ""
        normalized["character_design_rules"] = character_rules

    scene_rules = normalized.get("scene_design_rules")
    if isinstance(scene_rules, dict):
        scene_rules = dict(scene_rules)
        if "spatial_composition" not in scene_rules and "composition" in scene_rules:
            scene_rules["spatial_composition"] = scene_rules.pop("composition")
        normalized["scene_design_rules"] = scene_rules

    asset_card_rules = normalized.get("asset_card_rules")
    if isinstance(asset_card_rules, dict):
        asset_card_rules = dict(asset_card_rules)
        label_language = asset_card_rules.get("label_language", "")
        if label_language in {"中文", "zh", "zh_CN", "zh-CN"}:
            asset_card_rules["label_language"] = "zh-CN"
        normalized["asset_card_rules"] = asset_card_rules

    for key in ("composition_rules", "mood_keywords", "negative_keywords"):
        value = normalized.get(key)
        if isinstance(value, str):
            parts = [
                part.strip()
                for part in value.replace("；", "，").replace("、", "，").replace(",", "，").split("，")
                if part.strip()
            ]
            normalized[key] = parts

    return normalized


def generate_style_bible(
    *,
    asset_registry_path: Path,
    model_config: TextModelConfig,
    dry_run: bool = False,
) -> StyleBibleArtifacts:
    asset_registry = AssetRegistry.model_validate(read_json(asset_registry_path))
    run_dir = resolve_run_dir(asset_registry_path)
    artifacts = build_style_artifacts(run_dir)

    request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": STYLE_BIBLE_SYSTEM_PROMPT,
        "user_prompt": build_style_bible_user_prompt(asset_registry.model_dump(mode="json")),
        "source_script_name": asset_registry.source_script_name,
        "title": asset_registry.title,
        "genre": asset_registry.genre,
    }
    request_path = artifacts.style_dir / "style_bible_request.json"
    write_json(request_path, request_payload)

    if dry_run:
        return artifacts

    client = build_text_client(model_config)
    response = client.chat.completions.create(
        model=model_config.model_name,
        messages=[
            {"role": "system", "content": STYLE_BIBLE_SYSTEM_PROMPT},
            {"role": "user", "content": request_payload["user_prompt"]},
        ],
        temperature=0.2,
        max_tokens=4096,
        timeout=600.0,
    )
    response_path = artifacts.style_dir / "style_bible_response.json"
    write_json(response_path, dump_model(response))

    content = extract_text_content(response.choices[0].message.content)
    parsed = normalize_style_bible_payload(read_json_string(content))
    style_bible = StyleBible.model_validate(parsed)
    style_bible_path = artifacts.style_dir / "style_bible.json"
    write_json(style_bible_path, style_bible.model_dump(mode="json"))

    return artifacts


def read_json_string(value: str) -> dict[str, Any]:
    from json import loads

    parsed = loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object for style_bible.json")
    return parsed
