"""Storyboard generation node."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.io import dump_model, extract_text_content, read_json, write_json
from pipeline.runtime import TextModelConfig, build_text_client
from prompts.storyboard import STORYBOARD_SYSTEM_PROMPT, build_storyboard_user_prompt
from schemas.asset_registry import AssetRegistry
from schemas.storyboard import Storyboard
from schemas.style_bible import StyleBible


@dataclass(frozen=True, slots=True)
class StoryboardArtifacts:
    run_dir: Path
    storyboard_dir: Path


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


def resolve_script_clean_path(run_dir: Path) -> Path:
    script_clean_path = run_dir / "01_input" / "script_clean.txt"
    if not script_clean_path.exists():
        raise FileNotFoundError(f"script_clean.txt not found for run directory: {script_clean_path}")
    return script_clean_path


def build_storyboard_artifacts(run_dir: Path) -> StoryboardArtifacts:
    storyboard_dir = run_dir / "06_storyboard"
    storyboard_dir.mkdir(parents=True, exist_ok=True)
    return StoryboardArtifacts(run_dir=run_dir, storyboard_dir=storyboard_dir)


def build_storyboard_context(
    run_name: str,
    asset_registry: AssetRegistry,
    style_bible: StyleBible,
) -> dict[str, Any]:
    return {
        "source_run": run_name,
        "source_script_name": asset_registry.source_script_name,
        "title": asset_registry.title,
        "genre": asset_registry.genre,
        "logline": asset_registry.logline,
        "story_meta": asset_registry.story_meta.model_dump(mode="json"),
        "global_constraints": {
            "shot_duration_sec": 10,
            "aspect_ratio": "16:9",
            "first_frame_mode": "stitched_asset_board",
            "first_frame_transition": "fast_transform_into_cinematic_scene",
            "prompt_language": "zh-CN",
            "max_visible_character_ids": 4,
            "max_visible_prop_ids": 1,
        },
        "consistency_notes": asset_registry.consistency_notes,
        "style_bible": {
            "story_tone": style_bible.story_tone,
            "visual_style": style_bible.visual_style,
            "lighting_style": style_bible.lighting_style,
            "texture_style": style_bible.texture_style,
            "composition_rules": style_bible.composition_rules,
            "mood_keywords": style_bible.mood_keywords,
            "consistency_anchors": style_bible.consistency_anchors,
        },
        "assets": {
            "characters": [
                {
                    "id": item.id,
                    "name": item.name,
                    "aliases": item.aliases,
                    "role_type": item.role_type,
                    "occupation_identity": item.occupation_identity,
                    "appearance_summary": item.appearance_summary,
                    "costume_summary": item.costume_summary,
                    "must_keep_features": item.must_keep_features,
                    "required_features": item.visual_identity_lock.required_features,
                }
                for item in asset_registry.characters
            ],
            "scenes": [
                {
                    "id": item.id,
                    "name": item.name,
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
                    "visual_summary": item.visual_summary,
                    "must_keep_features": item.must_keep_features,
                }
                for item in asset_registry.props
            ],
        },
        "story_segments": [
            {
                "id": item.id,
                "order": item.order,
                "summary": item.summary,
                "scene_ids": item.scene_ids,
                "character_ids": item.character_ids,
                "prop_ids": item.prop_ids,
            }
            for item in asset_registry.story_segments
        ],
    }


def _normalize_id_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        item = value.strip()
        return [item] if item else []
    if not isinstance(value, list):
        return []
    normalized: list[str] = []
    for item in value:
        if isinstance(item, str):
            stripped = item.strip()
            if stripped:
                normalized.append(stripped)
    return normalized


def _normalize_enum_token(value: str) -> str:
    return value.strip().lower().replace("-", "_").replace(" ", "_")


def normalize_storyboard_payload(
    payload: dict[str, Any],
    *,
    run_name: str,
    asset_registry: AssetRegistry,
) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "sourceRun": "source_run",
        "sourceScriptName": "source_script_name",
        "globalVideoSpec": "global_video_spec",
        "shot_list": "shots",
        "shotList": "shots",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    normalized["schema_version"] = "1.0"
    normalized["source_run"] = run_name
    normalized["source_script_name"] = asset_registry.source_script_name
    normalized["title"] = asset_registry.title
    normalized["global_video_spec"] = {
        "shot_duration_sec": 10,
        "aspect_ratio": "16:9",
        "first_frame_mode": "stitched_asset_board",
        "first_frame_transition": "fast_transform_into_cinematic_scene",
        "prompt_language": "zh-CN",
    }

    shots = normalized.get("shots")
    if not isinstance(shots, list):
        shots = []

    enum_aliases = {
        "shot_type": {
            "character_reaction": "reaction",
            "conversation": "dialogue",
        },
        "board_layout_hint": {
            "scene_focused": "scene_dominant",
            "character_focused": "single_character",
            "two_character": "multi_character",
            "prop_focus": "prop_insert",
        },
        "shot_size": {
            "wide_shot": "wide",
            "full_shot": "full",
            "medium_shot": "medium",
            "medium_full_shot": "medium_full",
            "medium_close_shot": "medium_close",
            "close_up": "close",
            "extreme_close_up": "extreme_close",
        },
        "camera_angle": {
            "eye_level_shot": "eye_level",
            "low_angle_shot": "low_angle",
            "high_angle_shot": "high_angle",
            "over_the_shoulder": "over_shoulder",
            "top_view": "top_down",
        },
        "camera_movement": {
            "slow_pan_left": "pan_left",
            "slow_pan_right": "pan_right",
            "slow_track_left": "track_left",
            "slow_track_right": "track_right",
            "push_in": "slow_push_in",
            "slow_push": "slow_push_in",
            "dolly_in": "slow_push_in",
            "pull_out": "slow_pull_out",
            "slow_pull": "slow_pull_out",
            "dolly_out": "slow_pull_out",
            "tracking": "follow",
            "tracking_shot": "follow",
            "arc_shot": "arc",
        },
    }

    normalized_shots: list[dict[str, Any]] = []
    for item in shots:
        if not isinstance(item, dict):
            continue
        shot = dict(item)

        shot_alias_map = {
            "segmentIds": "segment_ids",
            "sceneId": "primary_scene_id",
            "primarySceneId": "primary_scene_id",
            "characterIds": "character_ids",
            "visibleCharacters": "visible_character_ids",
            "visibleCharacterIds": "visible_character_ids",
            "propIds": "prop_ids",
            "visibleProps": "visible_prop_ids",
            "visiblePropIds": "visible_prop_ids",
            "primarySubjectIds": "primary_subject_ids",
            "mainSubjectIds": "primary_subject_ids",
            "shotType": "shot_type",
            "boardLayoutHint": "board_layout_hint",
            "shotSize": "shot_size",
            "cameraAngle": "camera_angle",
            "cameraMovement": "camera_movement",
            "shotPurpose": "shot_purpose",
            "subjectAction": "subject_action",
            "backgroundAction": "background_action",
            "emotionTone": "emotion_tone",
            "continuityNotes": "continuity_notes",
            "promptCore": "prompt_core",
        }
        for alias, target in shot_alias_map.items():
            if target not in shot and alias in shot:
                shot[target] = shot.pop(alias)

        if "primary_scene_id" not in shot:
            scene_ids = shot.get("scene_ids")
            if isinstance(scene_ids, list) and scene_ids:
                shot["primary_scene_id"] = scene_ids[0]
            elif isinstance(scene_ids, str) and scene_ids.strip():
                shot["primary_scene_id"] = scene_ids.strip()

        if "duration_sec" not in shot and "duration" in shot:
            shot["duration_sec"] = shot.pop("duration")
        shot.setdefault("duration_sec", 10)

        for list_key in (
            "segment_ids",
            "character_ids",
            "visible_character_ids",
            "prop_ids",
            "visible_prop_ids",
            "primary_subject_ids",
            "continuity_notes",
        ):
            shot[list_key] = _normalize_id_list(shot.get(list_key))

        for enum_key, alias_map in enum_aliases.items():
            value = shot.get(enum_key)
            if isinstance(value, str):
                token = _normalize_enum_token(value)
                shot[enum_key] = alias_map.get(token, token)

        normalized_shots.append(shot)

    normalized["shots"] = normalized_shots
    return normalized


def read_json_string(value: str) -> dict[str, Any]:
    from json import loads

    parsed = loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object for storyboard.json")
    return parsed


def validate_storyboard_against_registry(storyboard: Storyboard, asset_registry: AssetRegistry) -> None:
    segment_id_order = [item.id for item in asset_registry.story_segments]
    segment_index_map = {segment_id: index for index, segment_id in enumerate(segment_id_order)}
    segment_map = {item.id: item for item in asset_registry.story_segments}

    covered_segments: list[str] = []
    for shot in storyboard.shots:
        segment_indexes = [segment_index_map[segment_id] for segment_id in shot.segment_ids]
        expected_indexes = list(range(segment_indexes[0], segment_indexes[-1] + 1))
        if segment_indexes != expected_indexes:
            raise ValueError(
                f"{shot.id} segment_ids must be contiguous and in order: got {shot.segment_ids}"
            )
        covered_segments.extend(shot.segment_ids)

        segment_scene_ids = {
            scene_id
            for segment_id in shot.segment_ids
            for scene_id in segment_map[segment_id].scene_ids
        }
        segment_character_ids = {
            character_id
            for segment_id in shot.segment_ids
            for character_id in segment_map[segment_id].character_ids
        }
        segment_prop_ids = {
            prop_id for segment_id in shot.segment_ids for prop_id in segment_map[segment_id].prop_ids
        }

        if shot.primary_scene_id not in segment_scene_ids:
            raise ValueError(
                f"{shot.id} primary_scene_id must belong to covered segments: {shot.primary_scene_id}"
            )

        unknown_characters = sorted(set(shot.character_ids) - segment_character_ids)
        if unknown_characters:
            raise ValueError(f"{shot.id} character_ids exceed covered segments: {unknown_characters}")

        unknown_props = sorted(set(shot.prop_ids) - segment_prop_ids)
        if unknown_props:
            raise ValueError(f"{shot.id} prop_ids exceed covered segments: {unknown_props}")

        unknown_visible_characters = sorted(set(shot.visible_character_ids) - set(shot.character_ids))
        if unknown_visible_characters:
            raise ValueError(
                f"{shot.id} visible_character_ids must be a subset of character_ids: "
                f"{unknown_visible_characters}"
            )

        unknown_visible_props = sorted(set(shot.visible_prop_ids) - set(shot.prop_ids))
        if unknown_visible_props:
            raise ValueError(
                f"{shot.id} visible_prop_ids must be a subset of prop_ids: {unknown_visible_props}"
            )

        allowed_primary_subjects = {shot.primary_scene_id, *shot.visible_character_ids, *shot.visible_prop_ids}
        unknown_primary_subjects = sorted(set(shot.primary_subject_ids) - allowed_primary_subjects)
        if unknown_primary_subjects:
            raise ValueError(
                f"{shot.id} primary_subject_ids must come from primary_scene_id + visible assets: "
                f"{unknown_primary_subjects}"
            )

    if covered_segments != segment_id_order:
        raise ValueError(
            f"Storyboard must cover each story segment exactly once in order: expected {segment_id_order}, "
            f"got {covered_segments}"
        )


def generate_storyboard(
    *,
    style_bible_path: Path,
    model_config: TextModelConfig,
    dry_run: bool = False,
) -> StoryboardArtifacts:
    style_bible = StyleBible.model_validate(read_json(style_bible_path))
    run_dir = resolve_run_dir(style_bible_path)
    asset_registry = AssetRegistry.model_validate(read_json(resolve_asset_registry_path(run_dir)))
    script_clean_text = resolve_script_clean_path(run_dir).read_text(encoding="utf-8")
    artifacts = build_storyboard_artifacts(run_dir)

    prompt_context = build_storyboard_context(run_dir.name, asset_registry, style_bible)
    digest_path = artifacts.storyboard_dir / "storyboard_input_digest.json"
    write_json(digest_path, prompt_context)

    request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": STORYBOARD_SYSTEM_PROMPT,
        "user_prompt": build_storyboard_user_prompt(prompt_context, script_clean_text),
        "source_run": run_dir.name,
        "source_script_name": asset_registry.source_script_name,
        "title": asset_registry.title,
    }
    request_path = artifacts.storyboard_dir / "storyboard_request.json"
    write_json(request_path, request_payload)

    if dry_run:
        return artifacts

    client = build_text_client(model_config)
    response = client.chat.completions.create(
        model=model_config.model_name,
        messages=[
            {"role": "system", "content": STORYBOARD_SYSTEM_PROMPT},
            {"role": "user", "content": request_payload["user_prompt"]},
        ],
        temperature=0.2,
        max_tokens=8192,
        timeout=600.0,
    )
    response_path = artifacts.storyboard_dir / "storyboard_response.json"
    write_json(response_path, dump_model(response))

    content = extract_text_content(response.choices[0].message.content)
    parsed = normalize_storyboard_payload(
        read_json_string(content),
        run_name=run_dir.name,
        asset_registry=asset_registry,
    )
    storyboard = Storyboard.model_validate(parsed)
    validate_storyboard_against_registry(storyboard, asset_registry)
    storyboard_path = artifacts.storyboard_dir / "storyboard.json"
    write_json(storyboard_path, storyboard.model_dump(mode="json"))

    return artifacts
