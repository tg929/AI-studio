"""Asset image prompt generation node."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.io import dump_model, extract_text_content, read_json, write_json
from pipeline.runtime import TextModelConfig, build_text_client
from prompts.asset_prompts import ASSET_PROMPTS_SYSTEM_PROMPT, build_asset_prompts_user_prompt
from schemas.asset_prompts import AssetPrompts
from schemas.asset_registry import AssetRegistry, CharacterAsset, PropAsset, SceneAsset
from schemas.style_bible import StyleBible


@dataclass(frozen=True, slots=True)
class AssetPromptArtifacts:
    run_dir: Path
    prompt_dir: Path


def resolve_run_dir(style_bible_path: Path) -> Path:
    if style_bible_path.name != "style_bible.json":
        raise ValueError(f"Expected a style_bible.json file: {style_bible_path}")
    if style_bible_path.parent.name != "03_style":
        raise ValueError(f"Expected style_bible.json under a 03_style directory: {style_bible_path}")
    return style_bible_path.parent.parent


def resolve_asset_registry_path(run_dir: Path) -> Path:
    asset_registry_path = run_dir / "02_assets" / "asset_registry.json"
    if not asset_registry_path.exists():
        raise FileNotFoundError(f"Asset registry file not found for run directory: {asset_registry_path}")
    return asset_registry_path


def build_prompt_artifacts(run_dir: Path) -> AssetPromptArtifacts:
    prompt_dir = run_dir / "04_asset_prompts"
    prompt_dir.mkdir(parents=True, exist_ok=True)
    return AssetPromptArtifacts(run_dir=run_dir, prompt_dir=prompt_dir)


def build_prompt_context(asset_registry: AssetRegistry, style_bible: StyleBible) -> dict[str, Any]:
    return {
        "source_script_name": asset_registry.source_script_name,
        "title": asset_registry.title,
        "genre": asset_registry.genre,
        "style_bible": {
            "story_tone": style_bible.story_tone,
            "visual_style": style_bible.visual_style,
            "era": style_bible.era,
            "world_setting": style_bible.world_setting,
            "color_palette": style_bible.color_palette.model_dump(mode="json"),
            "character_design_rules": style_bible.character_design_rules.model_dump(mode="json"),
            "scene_design_rules": style_bible.scene_design_rules.model_dump(mode="json"),
            "lighting_style": style_bible.lighting_style,
            "texture_style": style_bible.texture_style,
            "composition_rules": style_bible.composition_rules,
            "asset_card_rules": style_bible.asset_card_rules.model_dump(mode="json"),
            "mood_keywords": style_bible.mood_keywords,
            "negative_keywords": style_bible.negative_keywords,
            "consistency_anchors": style_bible.consistency_anchors,
        },
        "assets": {
            "characters": [
                {
                    "id": item.id,
                    "name": item.name,
                    "role_type": item.role_type,
                    "gender": item.gender,
                    "age": item.age,
                    "occupation_identity": item.occupation_identity,
                    "personality_traits": item.personality_traits,
                    "appearance_summary": item.appearance_summary,
                    "costume_summary": item.costume_summary,
                    "identity_markers": item.identity_markers,
                    "must_keep_features": item.must_keep_features,
                }
                for item in asset_registry.characters
            ],
            "scenes": [
                {
                    "id": item.id,
                    "name": item.name,
                    "location": item.location,
                    "scene_type": item.scene_type,
                    "time_of_day": item.time_of_day,
                    "weather": item.weather,
                    "atmosphere": item.atmosphere,
                    "environment_summary": item.environment_summary,
                    "key_visual_elements": item.key_visual_elements,
                    "must_keep_features": item.must_keep_features,
                }
                for item in asset_registry.scenes
            ],
            "props": [
                {
                    "id": item.id,
                    "name": item.name,
                    "category": item.category,
                    "significance": item.significance,
                    "visual_summary": item.visual_summary,
                    "material_texture": item.material_texture,
                    "condition_state": item.condition_state,
                    "must_keep_features": item.must_keep_features,
                }
                for item in asset_registry.props
            ],
        },
    }


def normalize_asset_prompts_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "character_prompts": "characters",
        "scene_prompts": "scenes",
        "prop_prompts": "props",
        "characterPrompts": "characters",
        "scenePrompts": "scenes",
        "propPrompts": "props",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    for key in ("characters", "scenes", "props"):
        items = normalized.get(key)
        if not isinstance(items, list):
            continue
        normalized_items = []
        for item in items:
            normalized_item = dict(item)
            if "prompt" not in normalized_item and "visualPrompt" in normalized_item:
                normalized_item["prompt"] = normalized_item.pop("visualPrompt")
            if "prompt" not in normalized_item and "visual_prompt" in normalized_item:
                normalized_item["prompt"] = normalized_item.pop("visual_prompt")
            normalized_items.append(normalized_item)
        normalized[key] = normalized_items

    return normalized


def read_json_string(value: str) -> dict[str, Any]:
    from json import loads

    parsed = loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object for asset_prompts.json")
    return parsed


def build_item_prompt_map(items: list[dict[str, Any]], group_name: str) -> dict[str, str]:
    prompt_map: dict[str, str] = {}
    for item in items:
        asset_id = str(item.get("id", "")).strip()
        prompt = item.get("prompt")
        if not asset_id:
            raise ValueError(f"{group_name} item is missing id")
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError(f"{group_name} item {asset_id} is missing a non-empty prompt")
        if asset_id in prompt_map:
            raise ValueError(f"{group_name} contains duplicate id: {asset_id}")
        prompt_map[asset_id] = prompt.strip()
    return prompt_map


def ensure_exact_ids(prompt_map: dict[str, str], expected_ids: list[str], group_name: str) -> None:
    actual_ids = sorted(prompt_map)
    if actual_ids != sorted(expected_ids):
        raise ValueError(f"{group_name} IDs do not match expected assets: expected {expected_ids}, got {actual_ids}")


def build_negative_prompt(style_bible: StyleBible, asset_type: str) -> str:
    shared = list(style_bible.negative_keywords)
    if asset_type == "character":
        shared.extend(["多人同框", "遮挡面部", "额外文字", "水印"])
    elif asset_type == "scene":
        shared.extend(["人物特写", "可辨识主角", "额外文字", "水印"])
    else:
        shared.extend(["人物手持", "人体肢体", "重复道具", "额外文字", "水印"])
    return "，".join(shared)


def build_card_layout_notes(style_bible: StyleBible) -> str:
    return (
        f"标注语言使用 {style_bible.asset_card_rules.label_language}，"
        f"标注位置为 {style_bible.asset_card_rules.label_position}，"
        f"标注样式为 {style_bible.asset_card_rules.label_style}，"
        f"整体版式遵循 {style_bible.asset_card_rules.layout_style}"
    )


def build_character_prompt_entry(
    character: CharacterAsset,
    prompt_text: str,
    style_bible: StyleBible,
) -> dict[str, Any]:
    return {
        "id": character.id,
        "name": character.name,
        "label_text": f"[{character.name} 人物参考]",
        "prompt": prompt_text,
        "negative_prompt": build_negative_prompt(style_bible, "character"),
        "aspect_ratio": "3:4",
        "framing": "单人半身至大半身参考卡",
        "background_treatment": "纯净浅色背景，主体居中，底部保留标注区",
        "generation_intent": "用于后续分镜与视频生成的人物一致性参考资产图",
        "card_layout_notes": build_card_layout_notes(style_bible),
    }


def build_scene_prompt_entry(
    scene: SceneAsset,
    prompt_text: str,
    style_bible: StyleBible,
) -> dict[str, Any]:
    return {
        "id": scene.id,
        "name": scene.name,
        "label_text": f"[{scene.name} 场景参考]",
        "prompt": prompt_text,
        "negative_prompt": build_negative_prompt(style_bible, "scene"),
        "aspect_ratio": "16:9",
        "framing": "宽景环境参考卡",
        "figure_policy": "no_identifiable_characters",
        "generation_intent": "用于后续分镜与视频生成的环境一致性参考资产图",
        "card_layout_notes": build_card_layout_notes(style_bible),
    }


def build_prop_prompt_entry(
    prop: PropAsset,
    prompt_text: str,
    style_bible: StyleBible,
) -> dict[str, Any]:
    return {
        "id": prop.id,
        "name": prop.name,
        "label_text": f"[{prop.name} 道具参考]",
        "prompt": prompt_text,
        "negative_prompt": build_negative_prompt(style_bible, "prop"),
        "aspect_ratio": "1:1",
        "framing": "单一道具居中参考卡",
        "isolation_rules": "仅展示单一道具主体，不出现人物、手部、佩戴者或额外同类物件",
        "generation_intent": "用于后续分镜与视频生成的道具一致性参考资产图",
        "card_layout_notes": build_card_layout_notes(style_bible),
    }


def assemble_asset_prompts(
    asset_registry: AssetRegistry,
    style_bible: StyleBible,
    payload: dict[str, Any],
) -> dict[str, Any]:
    character_map = build_item_prompt_map(payload.get("characters", []), "characters")
    scene_map = build_item_prompt_map(payload.get("scenes", []), "scenes")
    prop_map = build_item_prompt_map(payload.get("props", []), "props")

    ensure_exact_ids(character_map, [item.id for item in asset_registry.characters], "characters")
    ensure_exact_ids(scene_map, [item.id for item in asset_registry.scenes], "scenes")
    ensure_exact_ids(prop_map, [item.id for item in asset_registry.props], "props")

    return {
        "schema_version": "1.0",
        "source_script_name": asset_registry.source_script_name,
        "title": asset_registry.title,
        "visual_style": style_bible.visual_style,
        "consistency_anchors": style_bible.consistency_anchors,
        "characters": [
            build_character_prompt_entry(item, character_map[item.id], style_bible)
            for item in asset_registry.characters
        ],
        "scenes": [
            build_scene_prompt_entry(item, scene_map[item.id], style_bible)
            for item in asset_registry.scenes
        ],
        "props": [
            build_prop_prompt_entry(item, prop_map[item.id], style_bible)
            for item in asset_registry.props
        ],
    }


def generate_asset_prompts(
    *,
    style_bible_path: Path,
    model_config: TextModelConfig,
    dry_run: bool = False,
) -> AssetPromptArtifacts:
    style_bible = StyleBible.model_validate(read_json(style_bible_path))
    run_dir = resolve_run_dir(style_bible_path)
    asset_registry_path = resolve_asset_registry_path(run_dir)
    asset_registry = AssetRegistry.model_validate(read_json(asset_registry_path))
    artifacts = build_prompt_artifacts(run_dir)

    if asset_registry.source_script_name != style_bible.source_script_name:
        raise ValueError("asset_registry.json and style_bible.json do not belong to the same source script")

    prompt_context = build_prompt_context(asset_registry, style_bible)
    request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": ASSET_PROMPTS_SYSTEM_PROMPT,
        "user_prompt": build_asset_prompts_user_prompt(prompt_context),
        "source_script_name": asset_registry.source_script_name,
        "title": asset_registry.title,
    }
    request_path = artifacts.prompt_dir / "asset_prompts_request.json"
    write_json(request_path, request_payload)

    if dry_run:
        return artifacts

    client = build_text_client(model_config)
    response = client.chat.completions.create(
        model=model_config.model_name,
        messages=[
            {"role": "system", "content": ASSET_PROMPTS_SYSTEM_PROMPT},
            {"role": "user", "content": request_payload["user_prompt"]},
        ],
        temperature=0.3,
        max_tokens=8192,
        timeout=600.0,
    )
    response_path = artifacts.prompt_dir / "asset_prompts_response.json"
    write_json(response_path, dump_model(response))

    content = extract_text_content(response.choices[0].message.content)
    parsed = normalize_asset_prompts_payload(read_json_string(content))
    assembled = assemble_asset_prompts(asset_registry, style_bible, parsed)
    asset_prompts = AssetPrompts.model_validate(assembled)
    output_path = artifacts.prompt_dir / "asset_prompts.json"
    write_json(output_path, asset_prompts.model_dump(mode="json"))

    return artifacts
