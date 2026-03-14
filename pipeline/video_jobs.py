"""Video job assembly node."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from pipeline.io import read_json, write_json
from pipeline.runtime import VideoModelConfig
from schemas.asset_registry import AssetRegistry
from schemas.shot_reference_manifest import ShotReferenceManifest
from schemas.storyboard import Storyboard
from schemas.style_bible import StyleBible
from schemas.video_jobs import VideoJobsManifest


SHOT_SIZE_LABELS = {
    "wide": "远景",
    "full": "全景",
    "medium_full": "中全景",
    "medium": "中景",
    "medium_close": "中近景",
    "close": "近景",
    "extreme_close": "特写",
}

CAMERA_ANGLE_LABELS = {
    "eye_level": "平视",
    "low_angle": "仰视",
    "high_angle": "俯视",
    "over_shoulder": "越肩",
    "profile": "侧面视角",
    "top_down": "顶视",
    "dutch": "倾斜机位",
}

CAMERA_MOVEMENT_LABELS = {
    "static": "固定机位",
    "slow_push_in": "缓慢推近",
    "slow_pull_out": "缓慢拉远",
    "pan_left": "缓慢左摇",
    "pan_right": "缓慢右摇",
    "track_left": "向左平移跟拍",
    "track_right": "向右平移跟拍",
    "follow": "跟随主体移动",
    "arc": "弧线环绕",
    "tilt_up": "缓慢上摇",
    "tilt_down": "缓慢下摇",
}

MAX_PROMPT_LENGTH = 650
NON_PUBLIC_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


@dataclass(frozen=True, slots=True)
class VideoJobArtifacts:
    run_dir: Path
    jobs_dir: Path


def resolve_run_dir(storyboard_path: Path) -> Path:
    if storyboard_path.name != "storyboard.json":
        raise ValueError(f"Expected a storyboard.json file: {storyboard_path}")
    if storyboard_path.parent.name != "06_storyboard":
        raise ValueError(f"Expected storyboard.json under a 06_storyboard directory: {storyboard_path}")
    return storyboard_path.parent.parent


def resolve_asset_registry_path(run_dir: Path) -> Path:
    path = run_dir / "02_assets" / "asset_registry.json"
    if not path.exists():
        raise FileNotFoundError(f"Asset registry file not found for run directory: {path}")
    return path


def resolve_style_bible_path(run_dir: Path) -> Path:
    path = run_dir / "03_style" / "style_bible.json"
    if not path.exists():
        raise FileNotFoundError(f"Style bible file not found for run directory: {path}")
    return path


def resolve_shot_reference_manifest_path(run_dir: Path) -> Path:
    path = run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json"
    if not path.exists():
        raise FileNotFoundError(f"Shot reference manifest not found for run directory: {path}")
    return path


def build_video_job_artifacts(run_dir: Path) -> VideoJobArtifacts:
    jobs_dir = run_dir / "08_video_jobs"
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return VideoJobArtifacts(run_dir=run_dir, jobs_dir=jobs_dir)


def compress_text(text: str, max_length: int) -> str:
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip("，；。 ") + "…"


def dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item and item not in seen:
            seen.add(item)
            result.append(item)
    return result


def choose_main_character_ids(shot) -> list[str]:
    primary = [
        asset_id
        for asset_id in shot.primary_subject_ids
        if asset_id.startswith("char_") and asset_id in shot.visible_character_ids
    ]
    remaining = [asset_id for asset_id in shot.visible_character_ids if asset_id not in primary]
    return (primary + remaining)[:2]


def choose_main_prop_id(shot) -> str:
    primary = [
        asset_id
        for asset_id in shot.primary_subject_ids
        if asset_id.startswith("prop_") and asset_id in shot.visible_prop_ids
    ]
    if primary:
        return primary[0]
    return shot.visible_prop_ids[0] if shot.visible_prop_ids else ""


def build_character_anchor(character) -> str:
    features = dedupe_preserve_order(
        character.visual_identity_lock.required_features[:2]
        + character.must_keep_features[:2]
        + [character.costume_profile.costume_type, character.costume_profile.primary_color]
    )
    short_features = "、".join(feature for feature in features if feature) or character.appearance_summary
    return f"{character.name}保持{short_features}"


def build_scene_anchor(scene) -> str:
    features = dedupe_preserve_order(
        scene.must_keep_features[:2] + scene.key_visual_elements[:2] + [scene.environment_summary]
    )
    short_features = "、".join(feature for feature in features if feature)
    return f"{scene.name}保持{short_features}" if short_features else f"{scene.name}保持原有空间结构"


def build_prop_anchor(prop) -> str:
    features = dedupe_preserve_order(prop.must_keep_features[:2] + [prop.visual_summary])
    short_features = "、".join(feature for feature in features if feature)
    return f"{prop.name}保持{short_features}" if short_features else f"{prop.name}保持原有道具特征"


def build_primary_subject_summary(shot, asset_registry: AssetRegistry) -> str:
    name_map = {
        **{item.id: item.name for item in asset_registry.characters},
        **{item.id: item.name for item in asset_registry.scenes},
        **{item.id: item.name for item in asset_registry.props},
    }
    names = [name_map[asset_id] for asset_id in shot.primary_subject_ids if asset_id in name_map]
    return "、".join(names)


def build_prompt_blocks(shot, board, asset_registry: AssetRegistry, style_bible: StyleBible) -> dict[str, str]:
    character_map = {item.id: item for item in asset_registry.characters}
    scene_map = {item.id: item for item in asset_registry.scenes}
    prop_map = {item.id: item for item in asset_registry.props}

    transition_block = (
        "以提供的拼接图作为视频第1帧。开场前1秒内，从拼接首帧快速自然融入正常电影画面，"
        "去除白底、拼贴分栏、标签文字和设定板版式，只保留其中已绑定的人物、场景和道具，并把它们整合进真实空间。"
    )
    single_take_block = "这是一个连续10秒的单镜头，不要切镜，不要分屏，不要让拼接板持续停留在视频里。"

    content_parts = [
        f"镜头内容：{shot.prompt_core}",
        f"镜头用途：{shot.shot_purpose}",
        f"景别为{SHOT_SIZE_LABELS[shot.shot_size]}",
        f"机位为{CAMERA_ANGLE_LABELS[shot.camera_angle]}",
        f"运镜为{CAMERA_MOVEMENT_LABELS[shot.camera_movement]}",
        f"主要主体：{build_primary_subject_summary(shot, asset_registry)}",
        f"主体动作：{shot.subject_action}",
        f"背景动作：{shot.background_action}",
        f"情绪基调：{shot.emotion_tone}",
    ]
    content_block = "，".join(part for part in content_parts if part).rstrip("，") + "。"

    scene_anchor = build_scene_anchor(scene_map[shot.primary_scene_id])
    character_anchors = [build_character_anchor(character_map[character_id]) for character_id in choose_main_character_ids(shot)]
    prop_id = choose_main_prop_id(shot)
    prop_anchor = build_prop_anchor(prop_map[prop_id]) if prop_id else ""
    continuity_notes = "；".join(shot.continuity_notes[:2])
    style_anchor = compress_text(style_bible.visual_style, 80)

    anchor_parts = [f"必须保持{scene_anchor}"]
    if character_anchors:
        anchor_parts.append("；".join(character_anchors))
    if prop_anchor:
        anchor_parts.append(prop_anchor)
    if continuity_notes:
        anchor_parts.append(continuity_notes)
    anchor_parts.append(f"整体风格保持{style_anchor}")
    anchor_block = "。".join(part for part in anchor_parts if part).rstrip("。") + "。"

    negative_block = (
        "禁止出现拼接板持续存在、白底、标签文字、分栏边框、UI感、额外未绑定角色、角色服装和年龄漂移、"
        "场景结构漂移、道具替换、多镜头切换。"
    )

    return {
        "transition_block": transition_block,
        "single_take_block": single_take_block,
        "content_block": content_block,
        "anchor_block": anchor_block,
        "negative_block": negative_block,
    }


def assemble_prompt(blocks: dict[str, str]) -> str:
    return " ".join(
        blocks[key]
        for key in (
            "transition_block",
            "single_take_block",
            "content_block",
            "anchor_block",
            "negative_block",
        )
        if blocks[key]
    )


def compress_prompt_blocks(blocks: dict[str, str], shot, asset_registry: AssetRegistry, style_bible: StyleBible) -> dict[str, str]:
    prompt = assemble_prompt(blocks)
    if len(prompt) <= MAX_PROMPT_LENGTH:
        return blocks

    simplified_blocks = dict(blocks)
    simplified_content = (
        f"镜头内容：{shot.prompt_core}，景别为{SHOT_SIZE_LABELS[shot.shot_size]}，机位为"
        f"{CAMERA_ANGLE_LABELS[shot.camera_angle]}，运镜为{CAMERA_MOVEMENT_LABELS[shot.camera_movement]}，"
        f"主体动作：{compress_text(shot.subject_action, 40)}，背景动作：{compress_text(shot.background_action, 28)}，"
        f"情绪基调：{compress_text(shot.emotion_tone, 16)}。"
    )
    simplified_blocks["content_block"] = simplified_content

    scene_map = {item.id: item for item in asset_registry.scenes}
    character_map = {item.id: item for item in asset_registry.characters}
    prop_map = {item.id: item for item in asset_registry.props}

    scene_anchor = build_scene_anchor(scene_map[shot.primary_scene_id])
    main_character_ids = choose_main_character_ids(shot)[:1]
    character_anchors = [build_character_anchor(character_map[character_id]) for character_id in main_character_ids]
    prop_id = choose_main_prop_id(shot)
    prop_anchor = build_prop_anchor(prop_map[prop_id]) if prop_id else ""
    continuity_notes = "；".join(shot.continuity_notes[:1])
    style_anchor = compress_text(style_bible.visual_style, 60)

    anchor_parts = [f"必须保持{compress_text(scene_anchor, 50)}"]
    if character_anchors:
        anchor_parts.append(compress_text("；".join(character_anchors), 50))
    if prop_anchor:
        anchor_parts.append(compress_text(prop_anchor, 40))
    if continuity_notes:
        anchor_parts.append(compress_text(continuity_notes, 40))
    anchor_parts.append(f"整体风格保持{style_anchor}")
    simplified_blocks["anchor_block"] = "。".join(part for part in anchor_parts if part).rstrip("。") + "。"

    return simplified_blocks


def build_job_status(board, prompt: str) -> str:
    if len(prompt) > MAX_PROMPT_LENGTH:
        return "blocked_prompt_validation_failed"
    if not is_usable_first_frame_url(board.board_public_url):
        return "blocked_missing_first_frame_url"
    return "ready"


def is_usable_first_frame_url(url: str) -> bool:
    if not url.strip():
        return False
    parsed = urlsplit(url.strip())
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return False
    host = parsed.hostname or ""
    if host in NON_PUBLIC_HOSTS or host.endswith(".local"):
        return False
    return True


def generate_video_jobs(*, storyboard_path: Path, model_config: VideoModelConfig) -> VideoJobArtifacts:
    storyboard = Storyboard.model_validate(read_json(storyboard_path))
    run_dir = resolve_run_dir(storyboard_path)
    asset_registry = AssetRegistry.model_validate(read_json(resolve_asset_registry_path(run_dir)))
    style_bible = StyleBible.model_validate(read_json(resolve_style_bible_path(run_dir)))
    board_manifest = ShotReferenceManifest.model_validate(read_json(resolve_shot_reference_manifest_path(run_dir)))
    artifacts = build_video_job_artifacts(run_dir)

    board_map = {item.shot_id: item for item in board_manifest.boards}
    jobs_payload: list[dict[str, object]] = []

    for shot in storyboard.shots:
        board = board_map.get(shot.id)
        if board is None:
            raise ValueError(f"Missing shot reference board for {shot.id}")

        prompt_blocks = build_prompt_blocks(shot, board, asset_registry, style_bible)
        prompt_blocks = compress_prompt_blocks(prompt_blocks, shot, asset_registry, style_bible)
        prompt = assemble_prompt(prompt_blocks)
        status = build_job_status(board, prompt)
        first_frame_url = board.board_public_url if status == "ready" else ""

        jobs_payload.append(
            {
                "shot_id": shot.id,
                "order": shot.order,
                "segment_ids": shot.segment_ids,
                "video_name": f"{shot.id}.mp4",
                "first_frame_local_path": board.board_local_path,
                "first_frame_url": first_frame_url,
                "input_mode": "first_frame_only",
                "duration_sec": 10,
                "aspect_ratio": "16:9",
                "watermark": False,
                "prompt": prompt,
                "prompt_blocks": prompt_blocks,
                "status": status,
            }
        )

    manifest_payload = {
        "schema_version": "1.0",
        "source_run": run_dir.name,
        "source_script_name": storyboard.source_script_name,
        "title": storyboard.title,
        "video_model": model_config.model_name,
        "job_defaults": {
            "input_mode": "first_frame_only",
            "shot_duration_sec": 10,
            "aspect_ratio": "16:9",
            "watermark": False,
            "prompt_language": "zh-CN",
            "first_frame_transition": "fast_transform_into_cinematic_scene",
        },
        "jobs": jobs_payload,
    }
    manifest = VideoJobsManifest.model_validate(manifest_payload)
    manifest_path = artifacts.jobs_dir / "video_jobs.json"
    write_json(manifest_path, manifest.model_dump(mode="json"))

    return artifacts
