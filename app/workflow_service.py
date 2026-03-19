from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Callable, Iterable, Literal

import httpx
from pydantic import BaseModel, Field, model_validator
from tos import TosClientV2
from tos.enum import HttpMethodType

from pipeline.asset_extraction import extract_asset_registry_from_text, extract_first_json_object
from pipeline.asset_images import generate_asset_images
from pipeline.asset_prompts import generate_asset_prompts
from pipeline.final_video import (
    DEFAULT_BLACKOUT_LEADING_SECONDS,
    DEFAULT_TRIM_LEADING_SECONDS,
    generate_final_video,
)
from pipeline.intent_to_script import AUTO_INPUT_MODE, generate_script_from_intent
from pipeline.io import dump_model, extract_text_content, read_json, write_json
from pipeline.runtime import (
    build_text_client,
    load_image_model_config,
    load_text_model_config,
    load_video_model_config,
)
from pipeline.shot_reference_boards import generate_shot_reference_boards
from pipeline.shot_reference_publish import publish_shot_reference_boards
from pipeline.shot_videos import generate_shot_videos
from pipeline.storyboard import generate_storyboard
from pipeline.style_bible import generate_style_bible
from pipeline.video_jobs import generate_video_jobs
from schemas.shot_reference_manifest import ShotReferenceManifest

from .run_state import (
    CORE_STAGE_ORDER,
    OPTIONAL_STAGE_ORDER,
    RunState,
    append_run_event,
    ensure_run_state,
    load_run_state,
    run_state_path,
    utc_now_iso,
    update_stage_state,
    write_run_state,
)
from .review_state import (
    REVIEW_STAGE_ORDER,
    ReviewStage,
    ensure_reviews,
    update_review,
    write_reviews,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "agentkit.local.yaml"
DEFAULT_ENV_PATH = PROJECT_ROOT / "ai_studio_flow" / ".env"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "runs"
DEFAULT_SOURCE_PATH = PROJECT_ROOT / "01-陨落的天才.txt"

WorkflowStage = Literal[
    "upstream",
    "asset_extraction",
    "style_bible",
    "asset_prompts",
    "asset_images",
    "storyboard_seed",
    "storyboard",
    "shot_reference_boards",
    "board_publish",
    "video_jobs",
    "shot_videos",
    "final_video",
]

ProgressCallback = Callable[[dict[str, Any]], None]

REVIEW_CHECKPOINT_STAGE: dict[ReviewStage, WorkflowStage] = {
    "upstream": "upstream",
    "asset_images": "asset_images",
    "storyboard": "storyboard",
}

CHECKPOINT_REVIEW_STAGE: dict[WorkflowStage, ReviewStage] = {
    checkpoint_stage: review_stage for review_stage, checkpoint_stage in REVIEW_CHECKPOINT_STAGE.items()
}

PREREQUISITE_REVIEWS_BY_STAGE: dict[WorkflowStage, tuple[ReviewStage, ...]] = {
    "upstream": (),
    "asset_extraction": ("upstream",),
    "style_bible": ("upstream",),
    "asset_prompts": ("upstream",),
    "asset_images": ("upstream",),
    "storyboard_seed": ("upstream",),
    "storyboard": ("upstream", "asset_images"),
    "shot_reference_boards": ("upstream", "asset_images", "storyboard"),
    "board_publish": ("upstream", "asset_images", "storyboard"),
    "video_jobs": ("upstream", "asset_images", "storyboard"),
    "shot_videos": ("upstream", "asset_images", "storyboard"),
    "final_video": ("upstream", "asset_images", "storyboard"),
}


class WorkflowBlockedError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


class StoryboardSeedShot(BaseModel):
    id: str = Field(pattern=r"^shot_\d{3}$")
    order: int = Field(ge=1)
    shot_purpose: str
    prompt_core: str
    emotion_tone: str


class StoryboardSeed(BaseModel):
    schema_version: Literal["1.0"]
    source_run: str
    source_script_name: str
    title: str
    shots: list[StoryboardSeedShot] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_seed(self) -> "StoryboardSeed":
        expected_ids = [f"shot_{index:03d}" for index in range(1, len(self.shots) + 1)]
        actual_ids = [shot.id for shot in self.shots]
        if actual_ids != expected_ids:
            raise ValueError(f"storyboard seed shot ids must be sequential: {actual_ids}")
        expected_orders = list(range(1, len(self.shots) + 1))
        actual_orders = [shot.order for shot in self.shots]
        if actual_orders != expected_orders:
            raise ValueError(f"storyboard seed orders must be sequential: {actual_orders}")
        return self


STORYBOARD_SEED_SYSTEM_PROMPT = """你是一名 AI 漫剧分镜前期规划助理。

请基于已经规范化的剧本文本，先输出一个用于后续正式分镜生成的 `storyboard_seed.json`。

你现在不需要绑定资产 ID，也不要输出最终 storyboard 全字段。你的职责只有：
- 把剧情拆成适合 10 秒单镜头的 shots
- 给每个 shot 一个简短的镜头用途
- 给每个 shot 一个单镜头 `prompt_core`
- 给每个 shot 一个情绪基调

硬约束：
- 每个 shot 的时长默认视为 10 秒
- `prompt_core` 必须是单镜头表达，不能写切镜、分屏、多镜头串联
- 只输出 JSON

输出格式：
{
  "schema_version": "1.0",
  "source_run": "...",
  "source_script_name": "...",
  "title": "...",
  "shots": [
    {
      "id": "shot_001",
      "order": 1,
      "shot_purpose": "...",
      "prompt_core": "...",
      "emotion_tone": "..."
    }
  ]
}
"""


def _preview_url(run_dir: Path, artifact_path: Path) -> str:
    try:
        relative = artifact_path.resolve().relative_to(run_dir.resolve())
    except ValueError:
        return ""
    return f"/media/{run_dir.name}/{relative.as_posix()}"


def _normalize_preview_text(value: Any) -> str:
    text = str(value or "").replace("\r", "\n")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return " ".join(lines).strip()


def _truncate_preview_text(value: Any, *, limit: int = 180) -> tuple[str, bool]:
    text = _normalize_preview_text(value)
    if len(text) <= limit:
        return text, False
    return text[: max(0, limit - 3)].rstrip() + "...", True


def _humanize_source_kind(source_kind: str) -> str:
    labels = {
        "keywords": "关键词",
        "brief": "简述",
        "full_script": "完整剧本",
        "script": "完整剧本",
        "mixed": "混合输入",
        "unknown": "待判断",
    }
    return labels.get(source_kind, source_kind or "待判断")


def _humanize_chosen_path(chosen_path: str) -> str:
    labels = {
        "direct_extract": "直接进入资产链路",
        "compress_then_extract": "先压缩再进入资产链路",
        "rewrite_then_extract": "先重写再进入资产链路",
        "expand_then_extract": "先扩写再进入资产链路",
        "confirm_then_continue": "先停下等待确认",
        "pending": "待判断",
    }
    return labels.get(chosen_path, chosen_path or "待判断")


def _humanize_prompt_group(group_name: str) -> str:
    labels = {
        "characters": "人物",
        "scenes": "场景",
        "props": "道具",
    }
    return labels.get(group_name, group_name or "资产")


def _humanize_concat_mode(concat_mode: str) -> str:
    labels = {
        "ffmpeg_concat_demuxer_reencode": "逐段重编码拼接",
    }
    return labels.get(concat_mode, concat_mode)


class WorkflowService:
    def __init__(
        self,
        *,
        config_path: Path = DEFAULT_CONFIG_PATH,
        output_root: Path = DEFAULT_OUTPUT_ROOT,
        target_repo_root: Path = PROJECT_ROOT,
        env_file: Path | None = DEFAULT_ENV_PATH,
    ):
        self.config_path = config_path.resolve()
        self.output_root = output_root.resolve()
        self.target_repo_root = target_repo_root.resolve()
        self.output_root.mkdir(parents=True, exist_ok=True)
        if env_file is not None:
            self.load_env_file(env_file.resolve())
        self.text_config = load_text_model_config(self.config_path)
        self.image_config = load_image_model_config(self.config_path)
        self.video_config = load_video_model_config(self.config_path)

    @staticmethod
    def load_env_file(path: Path) -> None:
        if not path.exists():
            return
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            if not key or key in os.environ:
                continue
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
                value = value[1:-1]
            os.environ[key] = value

    def artifact_snapshot(self, run_dir: Path) -> dict[str, str]:
        board_publish_result_path = self.board_publish_result_path(run_dir)
        paths = {
            "source_input_path": run_dir / "00_source" / "source_input.txt",
            "source_context_path": run_dir / "00_source" / "source_context.json",
            "intake_router_path": run_dir / "00_source" / "intake_router.json",
            "storyboard_seed_path": run_dir / "00_source" / "storyboard_seed.json",
            "script_clean_path": run_dir / "01_input" / "script_clean.txt",
            "asset_registry_path": run_dir / "02_assets" / "asset_registry.json",
            "style_bible_path": run_dir / "03_style" / "style_bible.json",
            "asset_prompts_path": run_dir / "04_asset_prompts" / "asset_prompts.json",
            "asset_images_manifest_path": run_dir / "05_asset_images" / "asset_images_manifest.json",
            "storyboard_path": run_dir / "06_storyboard" / "storyboard.json",
            "shot_reference_manifest_path": run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json",
            "board_publish_result_path": board_publish_result_path,
            "video_jobs_path": run_dir / "08_video_jobs" / "video_jobs.json",
            "shot_videos_manifest_path": run_dir / "09_shot_videos" / "shot_videos_manifest.json",
            "final_video_manifest_path": run_dir / "10_final" / "final_video_manifest.json",
            "final_video_path": run_dir / "10_final" / "final_video.mp4",
            "run_state_path": run_state_path(run_dir),
            "events_path": run_dir / "_meta" / "events.jsonl",
            "reviews_path": run_dir / "_meta" / "reviews.json",
        }
        return {key: str(path.resolve()) if path.exists() else "" for key, path in paths.items()}

    @staticmethod
    def board_publish_result_path(run_dir: Path) -> Path:
        tos_path = run_dir / "07_shot_reference_boards" / "board_publish_tos_result.json"
        if tos_path.exists():
            return tos_path
        return run_dir / "07_shot_reference_boards" / "board_publish_result.json"

    @staticmethod
    def canonical_stage_artifact_path(run_dir: Path, stage: str) -> Path:
        mapping = {
            "upstream": run_dir / "01_input" / "script_clean.txt",
            "asset_extraction": run_dir / "02_assets" / "asset_registry.json",
            "style_bible": run_dir / "03_style" / "style_bible.json",
            "asset_prompts": run_dir / "04_asset_prompts" / "asset_prompts.json",
            "asset_images": run_dir / "05_asset_images" / "asset_images_manifest.json",
            "storyboard_seed": run_dir / "00_source" / "storyboard_seed.json",
            "storyboard": run_dir / "06_storyboard" / "storyboard.json",
            "shot_reference_boards": run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json",
            "board_publish": WorkflowService.board_publish_result_path(run_dir),
            "video_jobs": run_dir / "08_video_jobs" / "video_jobs.json",
            "shot_videos": run_dir / "09_shot_videos" / "shot_videos_manifest.json",
            "final_video": run_dir / "10_final" / "final_video.mp4",
        }
        return mapping[stage]

    @staticmethod
    def _read_json_if_exists(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        payload = read_json(path)
        return payload if isinstance(payload, dict) else {}

    @staticmethod
    def _sample_names(items: list[dict[str, Any]], *, limit: int = 3) -> str:
        names = [str(item.get("name", "")).strip() for item in items if str(item.get("name", "")).strip()]
        if not names:
            return ""
        return " / ".join(names[:limit])

    def build_stage_preview(self, run_dir: Path, stage: str, *, fallback_message: str = "") -> dict[str, Any]:
        preview_headline = ""
        preview_text = ""

        if stage == "upstream":
            source_context = self._read_json_if_exists(run_dir / "00_source" / "source_context.json")
            intake_router = self._read_json_if_exists(run_dir / "00_source" / "intake_router.json")
            script_clean_path = run_dir / "01_input" / "script_clean.txt"
            source_kind = (
                str(intake_router.get("source_form", "")).strip()
                or str(source_context.get("fallback_input_mode", "")).strip()
                or "unknown"
            )
            chosen_path = str(intake_router.get("chosen_path", "")).strip() or "pending"
            reasons = intake_router.get("reasons", []) if isinstance(intake_router.get("reasons"), list) else []
            preview_headline = f"{_humanize_source_kind(source_kind)} · {_humanize_chosen_path(chosen_path)}"
            script_excerpt = ""
            if script_clean_path.exists():
                script_excerpt, _ = _truncate_preview_text(script_clean_path.read_text(encoding="utf-8"), limit=160)
            reason_text = str(reasons[0]).strip() if reasons else ""
            preview_text = " ".join(part for part in [reason_text, script_excerpt] if part).strip()
        elif stage == "asset_extraction":
            payload = self._read_json_if_exists(run_dir / "02_assets" / "asset_registry.json")
            characters = payload.get("characters", []) if isinstance(payload.get("characters"), list) else []
            scenes = payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []
            props = payload.get("props", []) if isinstance(payload.get("props"), list) else []
            preview_headline = f"角色 {len(characters)} / 场景 {len(scenes)} / 道具 {len(props)}"
            sample_names = self._sample_names(characters) or self._sample_names(scenes) or self._sample_names(props)
            if sample_names:
                preview_text = f"已抽取核心资产：{sample_names}"
        elif stage == "style_bible":
            payload = self._read_json_if_exists(run_dir / "03_style" / "style_bible.json")
            preview_headline = "风格基线已建立"
            preview_text = " ".join(
                part
                for part in [
                    str(payload.get("story_tone", "")).strip(),
                    str(payload.get("visual_style", "")).strip(),
                    str(payload.get("consistency_anchors", "")).strip(),
                ]
                if part
            )
        elif stage == "asset_prompts":
            payload = self._read_json_if_exists(run_dir / "04_asset_prompts" / "asset_prompts.json")
            prompt_groups: list[tuple[str, list[dict[str, Any]]]] = []
            for group_name in ("characters", "scenes", "props"):
                items = payload.get(group_name, [])
                if isinstance(items, list) and items:
                    prompt_groups.append((group_name, [item for item in items if isinstance(item, dict)]))
            if prompt_groups:
                group_name, items = prompt_groups[0]
                first_item = items[0] if items else {}
                name = (
                    str(first_item.get("name", "")).strip()
                    or str(first_item.get("id", "")).strip()
                    or _humanize_prompt_group(group_name)
                )
                prompt_text = str(first_item.get("prompt", "")).strip()
                preview_headline = f"{_humanize_prompt_group(group_name)}参考说明 {len(items)} 条"
                preview_text = f"{name}：{prompt_text}".strip("： ")
        elif stage == "asset_images":
            payload = self._read_json_if_exists(run_dir / "05_asset_images" / "asset_images_manifest.json")
            characters = payload.get("characters", []) if isinstance(payload.get("characters"), list) else []
            scenes = payload.get("scenes", []) if isinstance(payload.get("scenes"), list) else []
            props = payload.get("props", []) if isinstance(payload.get("props"), list) else []
            preview_headline = f"人物 {len(characters)} / 场景 {len(scenes)} / 道具 {len(props)}"
            sample_names = self._sample_names(characters) or self._sample_names(scenes) or self._sample_names(props)
            if sample_names:
                preview_text = f"已生成参考资产图：{sample_names}"
        elif stage == "storyboard_seed":
            payload = self._read_json_if_exists(run_dir / "00_source" / "storyboard_seed.json")
            shots = payload.get("shots", []) if isinstance(payload.get("shots"), list) else []
            preview_headline = f"预规划镜头 {len(shots)} 条"
            highlights = []
            for shot in shots[:2]:
                if not isinstance(shot, dict):
                    continue
                shot_id = str(shot.get("id", "")).strip()
                purpose = str(shot.get("shot_purpose", "")).strip()
                if shot_id or purpose:
                    highlights.append(" ".join(part for part in [shot_id, purpose] if part))
            preview_text = " / ".join(highlights)
        elif stage == "storyboard":
            payload = self._read_json_if_exists(run_dir / "06_storyboard" / "storyboard.json")
            shots = payload.get("shots", []) if isinstance(payload.get("shots"), list) else []
            preview_headline = f"正式分镜 {len(shots)} 条"
            highlights = []
            for shot in shots[:2]:
                if not isinstance(shot, dict):
                    continue
                shot_id = str(shot.get("id", "")).strip()
                purpose = str(shot.get("shot_purpose", "")).strip() or str(shot.get("prompt_core", "")).strip()
                if shot_id or purpose:
                    highlights.append(" ".join(part for part in [shot_id, purpose] if part))
            preview_text = " / ".join(highlights)
        elif stage == "shot_reference_boards":
            payload = self._read_json_if_exists(run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json")
            boards = payload.get("boards", []) if isinstance(payload.get("boards"), list) else []
            preview_headline = f"参考板 {len(boards)} 张"
            shot_ids = [str(board.get("shot_id", "")).strip() for board in boards[:3] if isinstance(board, dict)]
            preview_text = " / ".join(shot_id for shot_id in shot_ids if shot_id)
        elif stage == "board_publish":
            payload = self._read_json_if_exists(self.board_publish_result_path(run_dir))
            published_boards = payload.get("published_boards", []) if isinstance(payload.get("published_boards"), list) else []
            preview_headline = f"已发布参考板 {len(published_boards)} 张"
            if published_boards:
                first_item = published_boards[0] if isinstance(published_boards[0], dict) else {}
                preview_text = str(first_item.get("signed_url") or first_item.get("public_url") or "").strip()
        elif stage == "video_jobs":
            payload = self._read_json_if_exists(run_dir / "08_video_jobs" / "video_jobs.json")
            jobs = payload.get("jobs", []) if isinstance(payload.get("jobs"), list) else []
            preview_headline = f"视频任务 {len(jobs)} 条"
            if jobs:
                first_job = jobs[0] if isinstance(jobs[0], dict) else {}
                shot_id = str(first_job.get("shot_id", "")).strip()
                prompt_text = str(first_job.get("prompt", "")).strip()
                preview_text = f"{shot_id}: {prompt_text}".strip(": ")
        elif stage == "shot_videos":
            payload = self._read_json_if_exists(run_dir / "09_shot_videos" / "shot_videos_manifest.json")
            jobs = payload.get("jobs", []) if isinstance(payload.get("jobs"), list) else []
            succeeded = sum(1 for job in jobs if isinstance(job, dict) and str(job.get("status", "")).strip() == "succeeded")
            preview_headline = f"分镜视频 {succeeded}/{len(jobs)}"
            if jobs:
                failed = [str(job.get("shot_id", "")).strip() for job in jobs if isinstance(job, dict) and str(job.get("status", "")).strip() != "succeeded"]
                preview_text = "全部分镜视频已生成。" if not failed else f"未完成镜头：{' / '.join(failed[:3])}"
        elif stage == "final_video":
            payload = self._read_json_if_exists(run_dir / "10_final" / "final_video_manifest.json")
            shot_count = payload.get("shot_count", "")
            concat_mode = str(payload.get("concat_mode", "")).strip()
            preview_headline = "最终成片已生成" if (run_dir / "10_final" / "final_video.mp4").exists() else "最终成片待生成"
            preview_parts = []
            if shot_count:
                preview_parts.append(f"镜头数：{shot_count}")
            if concat_mode:
                preview_parts.append(f"拼接方式：{_humanize_concat_mode(concat_mode)}")
            preview_text = " · ".join(preview_parts)

        if not preview_headline and fallback_message:
            preview_headline, _ = _truncate_preview_text(fallback_message, limit=72)
        if not preview_text and fallback_message and fallback_message != preview_headline:
            preview_text = fallback_message

        truncated_text, preview_truncated = _truncate_preview_text(preview_text, limit=180)
        return {
            "preview_headline": preview_headline,
            "preview_text": truncated_text,
            "preview_truncated": preview_truncated,
        }

    def build_route_decision_summary(self, run_dir: Path) -> dict[str, Any]:
        source_context = self._read_json_if_exists(run_dir / "00_source" / "source_context.json")
        intake_router = self._read_json_if_exists(run_dir / "00_source" / "intake_router.json")
        if not source_context and not intake_router:
            return {"available": False}

        reasons = intake_router.get("reasons", []) if isinstance(intake_router.get("reasons"), list) else []
        risks = intake_router.get("risks", []) if isinstance(intake_router.get("risks"), list) else []
        missing_info = (
            intake_router.get("missing_critical_info", [])
            if isinstance(intake_router.get("missing_critical_info"), list)
            else []
        )
        project_target = intake_router.get("project_target")
        if not isinstance(project_target, dict):
            project_target = source_context.get("project_target", {}) if isinstance(source_context.get("project_target"), dict) else {}
        cleaned_risks = [str(risk).strip() for risk in risks if str(risk).strip()]
        cleaned_missing_info = [str(item).strip() for item in missing_info if str(item).strip()]
        operator_hint = ""
        for candidate in (*cleaned_missing_info, *cleaned_risks):
            if candidate:
                operator_hint = candidate
                break

        return {
            "available": True,
            "requested_input_mode": str(source_context.get("requested_input_mode", "")).strip() or "auto",
            "fallback_input_mode": str(source_context.get("fallback_input_mode", "")).strip() or "unknown",
            "source_kind": str(intake_router.get("source_form", "")).strip() or "unknown",
            "material_state": str(intake_router.get("material_state", "")).strip() or "unknown",
            "chosen_path": str(intake_router.get("chosen_path", "")).strip() or "pending",
            "asset_readiness_estimate": str(intake_router.get("asset_readiness_estimate", "")).strip() or "unknown",
            "recommended_operations": intake_router.get("recommended_operations", [])
            if isinstance(intake_router.get("recommended_operations"), list)
            else [],
            "needs_confirmation": bool(intake_router.get("needs_confirmation", False)),
            "confirmation_points": intake_router.get("confirmation_points", [])
            if isinstance(intake_router.get("confirmation_points"), list)
            else [],
            "reasoning_summary": " / ".join(str(reason).strip() for reason in reasons[:2] if str(reason).strip()),
            "risks": cleaned_risks,
            "missing_critical_info": cleaned_missing_info,
            "operator_hint": operator_hint,
            "project_target": {
                "target_runtime_sec": project_target.get("target_runtime_sec", ""),
                "target_shot_count": project_target.get("target_shot_count", ""),
                "target_script_length_chars": project_target.get("target_script_length_chars", ""),
                "shot_duration_sec": project_target.get("shot_duration_sec", ""),
            },
        }

    @staticmethod
    def _run_git(args: list[str], repo_root: Path) -> str:
        completed = subprocess.run(
            ["git", *args],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        return completed.stdout.strip()

    @classmethod
    def infer_repo_slug(cls, repo_root: Path) -> str:
        remote_url = cls._run_git(["config", "--get", "remote.origin.url"], repo_root)
        if not remote_url:
            raise ValueError(f"Cannot infer GitHub repo slug from target repo: {repo_root}")

        normalized = remote_url.rstrip("/")
        if normalized.endswith(".git"):
            normalized = normalized[:-4]

        if normalized.startswith("git@github.com:"):
            path = normalized.split("git@github.com:", 1)[1]
        elif normalized.startswith("https://github.com/"):
            path = normalized.split("https://github.com/", 1)[1]
        else:
            raise ValueError(f"Unsupported GitHub remote URL format: {remote_url}")

        parts = [part for part in path.split("/") if part]
        if len(parts) != 2:
            raise ValueError(f"Cannot parse owner/repo from remote URL: {remote_url}")
        return f"{parts[0]}/{parts[1]}"

    @classmethod
    def infer_git_ref(cls, repo_root: Path) -> str:
        branch = cls._run_git(["branch", "--show-current"], repo_root)
        if branch:
            return branch
        raise ValueError(f"Cannot infer current branch for target repo: {repo_root}")

    @staticmethod
    def build_object_key(key_prefix: str, source_run: str, filename: str) -> str:
        parts = [part for part in key_prefix.split("/") if part]
        parts.extend(["runs", source_run, "07_shot_reference_boards", "boards", filename])
        return PurePosixPath(*parts).as_posix()

    @staticmethod
    def load_board_tos_env() -> dict[str, str] | None:
        required = {
            "bucket": os.getenv("BOARD_TOS_BUCKET", "").strip(),
            "endpoint": os.getenv("BOARD_TOS_ENDPOINT", "").strip(),
            "region": os.getenv("BOARD_TOS_REGION", "").strip(),
            "access_key": os.getenv("BOARD_TOS_ACCESS_KEY", "").strip(),
            "secret_key": os.getenv("BOARD_TOS_SECRET_KEY", "").strip(),
        }
        if not all(required.values()):
            return None
        required["key_prefix"] = os.getenv("BOARD_TOS_KEY_PREFIX", "ai-studio-boards").strip("/") or "ai-studio-boards"
        required["url_expiry_seconds"] = os.getenv("BOARD_TOS_URL_EXPIRES_SECONDS", "86400").strip() or "86400"
        return required

    def load_jsdelivr_env(self) -> dict[str, str]:
        repo_slug = os.getenv("BOARD_JSDELIVR_REPO_SLUG", "").strip() or self.infer_repo_slug(self.target_repo_root)
        ref = os.getenv("BOARD_JSDELIVR_REF", "").strip() or self.infer_git_ref(self.target_repo_root)
        url_prefix = os.getenv("BOARD_JSDELIVR_URL_PREFIX", "static").strip() or "static"
        publish_root_dir = os.getenv("BOARD_JSDELIVR_PUBLISH_ROOT", "").strip()
        resolved_publish_root = Path(publish_root_dir).resolve() if publish_root_dir else self.target_repo_root.resolve()
        return {
            "repo_slug": repo_slug,
            "ref": ref,
            "url_prefix": url_prefix,
            "publish_root_dir": str(resolved_publish_root),
        }

    @staticmethod
    def check_public_url_reachable(url: str) -> tuple[bool, str]:
        try:
            with httpx.Client(follow_redirects=True, timeout=10.0) as client:
                response = client.head(url)
                if response.status_code == 405:
                    response = client.get(url)
                return response.status_code == 200, f"HTTP {response.status_code}"
        except Exception as exc:
            return False, str(exc)

    @staticmethod
    def first_nonempty(values: Iterable[str]) -> str:
        for value in values:
            if value:
                return value
        return ""

    @staticmethod
    def load_source_script_name(run_dir: Path) -> str:
        for candidate in (
            run_dir / "01_input" / "script_clean.json",
            run_dir / "00_source" / "source_context.json",
            run_dir / "00_source" / "generated_script_meta.json",
        ):
            if candidate.exists():
                payload = read_json(candidate)
                if isinstance(payload, dict):
                    source_script_name = str(payload.get("source_script_name", "")).strip()
                    if source_script_name:
                        return source_script_name
        return run_dir.name

    @staticmethod
    def ensure_script_clean_exists(run_dir: Path) -> Path:
        script_clean_path = run_dir / "01_input" / "script_clean.txt"
        if script_clean_path.exists():
            return script_clean_path
        router_path = run_dir / "00_source" / "intake_router.json"
        reason = (
            "Upstream routing did not produce 01_input/script_clean.txt. "
            f"Check the router output under {router_path}."
        )
        raise WorkflowBlockedError("upstream", reason)

    def recover_upstream_for_existing_run(
        self,
        *,
        run_dir: Path,
        input_mode: Literal["auto", "keywords", "brief", "script"],
    ) -> tuple[str, str, bool]:
        script_clean_path = run_dir / "01_input" / "script_clean.txt"
        if script_clean_path.exists():
            return (
                self.load_source_script_name(run_dir),
                "Resumed existing run directory without re-running upstream routing.",
                False,
            )

        source_input_path = run_dir / "00_source" / "source_input.txt"
        source_context_path = run_dir / "00_source" / "source_context.json"
        if not source_input_path.exists():
            raise WorkflowBlockedError(
                "upstream",
                f"Cannot resume {run_dir}: missing both 01_input/script_clean.txt and 00_source/source_input.txt",
            )

        source_text = source_input_path.read_text(encoding="utf-8")
        source_script_name = run_dir.name
        recovery_input_mode = input_mode
        source_path: Path | None = None
        if source_context_path.exists():
            payload = read_json(source_context_path)
            if isinstance(payload, dict):
                source_script_name = str(payload.get("source_script_name", "")).strip() or source_script_name
                if recovery_input_mode == AUTO_INPUT_MODE:
                    recovery_input_mode = str(payload.get("requested_input_mode", "")).strip() or recovery_input_mode
                raw_source_path = str(payload.get("source_path", "")).strip()
                if raw_source_path:
                    candidate = Path(raw_source_path).resolve()
                    if candidate.exists():
                        source_path = candidate

        generate_script_from_intent(
            source_text=source_text,
            source_script_name=source_script_name,
            model_config=self.text_config,
            output_root=self.output_root,
            run_dir=run_dir,
            source_path=source_path,
            input_mode=recovery_input_mode,
            extract_assets=False,
        )
        return source_script_name, "Recovered upstream artifacts for an existing run directory before resuming.", True

    def has_reachable_board_urls(self, manifest_path: Path) -> tuple[bool, str]:
        manifest = ShotReferenceManifest.model_validate(read_json(manifest_path))
        sample_url = self.first_nonempty(board.board_public_url for board in manifest.boards)
        if not sample_url:
            return False, "board_public_url is still empty in shot_reference_manifest.json"
        return self.check_public_url_reachable(sample_url)

    def publish_boards_with_tos(self, manifest_path: Path, tos_env: dict[str, str]) -> Path:
        manifest = ShotReferenceManifest.model_validate(read_json(manifest_path))
        client = TosClientV2(
            ak=tos_env["access_key"],
            sk=tos_env["secret_key"],
            endpoint=tos_env["endpoint"],
            region=tos_env["region"],
        )
        boards_payload: list[dict[str, object]] = []
        published_entries: list[dict[str, str]] = []
        try:
            for board in manifest.boards:
                source_path = Path(board.board_local_path)
                if not source_path.exists():
                    raise FileNotFoundError(f"Shot board image not found: {source_path}")
                object_key = self.build_object_key(tos_env["key_prefix"], manifest.source_run, source_path.name)
                with source_path.open("rb") as file_obj:
                    client.put_object(
                        bucket=tos_env["bucket"],
                        key=object_key,
                        content=file_obj,
                        content_type="image/png",
                        cache_control="public, max-age=31536000, immutable",
                    )
                signed_url = client.pre_signed_url(
                    HttpMethodType.Http_Method_Get,
                    bucket=tos_env["bucket"],
                    key=object_key,
                    expires=max(60, int(tos_env["url_expiry_seconds"])),
                ).signed_url
                payload = board.model_dump(mode="json")
                payload["board_public_url"] = signed_url
                boards_payload.append(payload)
                published_entries.append(
                    {
                        "shot_id": board.shot_id,
                        "source_path": str(source_path),
                        "object_key": object_key,
                        "signed_url": signed_url,
                    }
                )
        finally:
            client.close()

        updated_manifest = ShotReferenceManifest.model_validate(
            {**manifest.model_dump(mode="json"), "boards": boards_payload}
        )
        write_json(manifest_path, updated_manifest.model_dump(mode="json"))
        result_path = manifest_path.parent / "board_publish_tos_result.json"
        write_json(
            result_path,
            {
                "source_run": manifest.source_run,
                "source_script_name": manifest.source_script_name,
                "bucket": tos_env["bucket"],
                "endpoint": tos_env["endpoint"],
                "region": tos_env["region"],
                "key_prefix": tos_env["key_prefix"],
                "published_boards": published_entries,
            },
        )
        return result_path

    def publish_boards_auto(self, manifest_path: Path, publish_strategy: str) -> tuple[str, Path]:
        tos_env = self.load_board_tos_env()
        if publish_strategy in {"auto", "tos"} and tos_env is not None:
            result_path = self.publish_boards_with_tos(manifest_path, tos_env)
            return "tos", result_path

        if publish_strategy == "tos":
            raise WorkflowBlockedError(
                "board_publish",
                "Publish strategy was forced to `tos`, but BOARD_TOS_* variables are not configured.",
            )

        jsdelivr_env = self.load_jsdelivr_env()
        public_base_url = f"https://cdn.jsdelivr.net/gh/{jsdelivr_env['repo_slug']}@{jsdelivr_env['ref']}"
        artifacts = publish_shot_reference_boards(
            manifest_path=manifest_path,
            public_base_url=public_base_url,
            publish_root_dir=Path(jsdelivr_env["publish_root_dir"]),
            url_prefix=jsdelivr_env["url_prefix"],
            output_manifest_path=None,
        )
        reachable, detail = self.has_reachable_board_urls(manifest_path)
        if not reachable:
            static_dir = self.target_repo_root / "static" / "runs" / manifest_path.parent.parent.name
            raise WorkflowBlockedError(
                "board_publish",
                "Published local board files and wrote jsDelivr URLs into the manifest, but the public CDN URL is not "
                f"reachable yet ({detail}). Commit and push {static_dir}, then rerun with --run-dir {manifest_path.parent.parent}.",
            )
        return "jsdelivr", artifacts.result_path

    @staticmethod
    def _parse_json_object(raw_text: str) -> dict[str, Any]:
        text = raw_text.strip()
        if not text:
            raise ValueError("Empty response content")
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            parsed = json.loads(extract_first_json_object(text))
        if not isinstance(parsed, dict):
            raise ValueError("Expected a JSON object")
        return parsed

    def build_storyboard_seed(self, run_dir: Path, source_script_name: str) -> Path:
        source_dir = run_dir / "00_source"
        source_dir.mkdir(parents=True, exist_ok=True)
        script_clean_text = self.ensure_script_clean_exists(run_dir).read_text(encoding="utf-8")
        request_path = source_dir / "storyboard_seed_request.json"
        response_path = source_dir / "storyboard_seed_response.json"
        output_path = source_dir / "storyboard_seed.json"

        request_payload = {
            "model": self.text_config.model_name,
            "base_url": self.text_config.base_url,
            "system_prompt": STORYBOARD_SEED_SYSTEM_PROMPT,
            "user_prompt": (
                f"source_run: {run_dir.name}\n"
                f"source_script_name: {source_script_name}\n"
                f"title: {source_script_name}\n\n"
                f"script_clean_text:\n{script_clean_text}"
            ),
        }
        write_json(request_path, request_payload)

        client = build_text_client(self.text_config)
        response = client.chat.completions.create(
            model=self.text_config.model_name,
            messages=[
                {"role": "system", "content": STORYBOARD_SEED_SYSTEM_PROMPT},
                {"role": "user", "content": request_payload["user_prompt"]},
            ],
            temperature=0.2,
            max_tokens=4096,
            timeout=600.0,
        )
        write_json(response_path, dump_model(response))
        content = extract_text_content(response.choices[0].message.content)
        parsed = self._parse_json_object(content)
        seed = StoryboardSeed.model_validate(
            {
                "schema_version": "1.0",
                "source_run": run_dir.name,
                "source_script_name": source_script_name,
                "title": parsed.get("title") or source_script_name,
                "shots": parsed.get("shots") or [],
            }
        )
        write_json(output_path, seed.model_dump(mode="json"))
        return output_path

    def _result(
        self,
        *,
        status: Literal["ok", "blocked", "failed", "partial", "awaiting_approval"],
        run_dir: Path,
        stage: str,
        message: str = "",
        reason: str = "",
        extra: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "status": status,
            "stage": stage,
            "run_dir": str(run_dir.resolve()),
            "artifacts": self.artifact_snapshot(run_dir),
            "run_state": self.inspect_run(run_dir)["run_state"],
        }
        if message:
            payload["message"] = message
        if reason:
            payload["reason"] = reason
        if extra:
            payload.update(extra)
        return payload

    def _mark_stage_running(self, run_dir: Path, stage: str, source_script_name: str) -> None:
        artifact_path = str(self.canonical_stage_artifact_path(run_dir, stage).resolve())
        update_stage_state(
            run_dir,
            stage=stage,
            status="running",
            message=f"Running {stage}.",
            artifact_path=artifact_path,
            source_script_name=source_script_name,
            run_status="running",
            current_stage=stage,
            last_error="",
        )
        append_run_event(run_dir, event_type="stage_started", stage=stage, message=f"Started {stage}.")

    def _mark_stage_succeeded(
        self,
        run_dir: Path,
        stage: str,
        *,
        source_script_name: str,
        message: str,
        artifact_path: Path | None = None,
        metadata: dict[str, Any] | None = None,
        run_status: Literal["running", "succeeded"] = "running",
    ) -> None:
        resolved_artifact = artifact_path or self.canonical_stage_artifact_path(run_dir, stage)
        update_stage_state(
            run_dir,
            stage=stage,
            status="succeeded",
            message=message,
            artifact_path=str(resolved_artifact.resolve()),
            metadata=metadata,
            source_script_name=source_script_name,
            run_status=run_status,
            current_stage=stage,
            last_error="",
        )
        append_run_event(
            run_dir,
            event_type="stage_succeeded",
            stage=stage,
            message=message,
            data={"artifact_path": str(resolved_artifact.resolve())},
        )

    def _mark_stage_blocked(
        self,
        run_dir: Path,
        stage: str,
        *,
        source_script_name: str,
        reason: str,
        artifact_path: Path | None = None,
    ) -> None:
        resolved_artifact = artifact_path or self.canonical_stage_artifact_path(run_dir, stage)
        update_stage_state(
            run_dir,
            stage=stage,
            status="blocked",
            message=reason,
            artifact_path=str(resolved_artifact.resolve()),
            source_script_name=source_script_name,
            run_status="blocked",
            current_stage=stage,
            last_error=reason,
        )
        append_run_event(run_dir, event_type="stage_blocked", stage=stage, message=reason)

    def _mark_stage_failed(
        self,
        run_dir: Path,
        stage: str,
        *,
        source_script_name: str,
        reason: str,
        artifact_path: Path | None = None,
    ) -> None:
        resolved_artifact = artifact_path or self.canonical_stage_artifact_path(run_dir, stage)
        update_stage_state(
            run_dir,
            stage=stage,
            status="failed",
            message=reason,
            artifact_path=str(resolved_artifact.resolve()),
            source_script_name=source_script_name,
            run_status="failed",
            current_stage=stage,
            last_error=reason,
        )
        append_run_event(run_dir, event_type="stage_failed", stage=stage, message=reason)

    @staticmethod
    def _active_run_status(run_dir: Path) -> Literal["running", "succeeded"]:
        final_video_path = run_dir / "10_final" / "final_video.mp4"
        return "succeeded" if final_video_path.exists() else "running"

    def _mark_stage_awaiting_approval(
        self,
        run_dir: Path,
        stage: str,
        *,
        source_script_name: str,
        reason: str,
        artifact_path: Path | None = None,
    ) -> None:
        resolved_artifact = artifact_path or self.canonical_stage_artifact_path(run_dir, stage)
        update_stage_state(
            run_dir,
            stage=stage,
            status="awaiting_approval",
            message=reason,
            artifact_path=str(resolved_artifact.resolve()),
            source_script_name=source_script_name,
            run_status="awaiting_approval",
            current_stage=stage,
            last_error=reason,
            awaiting_approval_stage=stage,
        )
        append_run_event(run_dir, event_type="approval_required", stage=stage, message=reason)

    def _set_checkpoint_review_pending(
        self,
        run_dir: Path,
        *,
        review_stage: ReviewStage,
        source_script_name: str,
        reset_reason: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        update_review(
            run_dir,
            stage=review_stage,
            status="pending",
            reviewer="",
            notes="",
            metadata=metadata,
        )
        checkpoint_stage = REVIEW_CHECKPOINT_STAGE[review_stage]
        self._mark_stage_awaiting_approval(
            run_dir,
            checkpoint_stage,
            source_script_name=source_script_name,
            reason=reset_reason,
            artifact_path=self.canonical_stage_artifact_path(run_dir, checkpoint_stage),
        )
        append_run_event(
            run_dir,
            event_type="review_reset",
            stage=checkpoint_stage,
            message=reset_reason,
            data={"review_stage": review_stage, "metadata": metadata or {}},
        )

    def _review_gate_result(
        self,
        run_dir: Path,
        *,
        review_stage: ReviewStage,
        source_script_name: str,
        target_stage: WorkflowStage,
        status: Literal["awaiting_approval", "blocked"],
        reason: str,
    ) -> dict[str, Any]:
        checkpoint_stage = REVIEW_CHECKPOINT_STAGE[review_stage]
        artifact_path = self.canonical_stage_artifact_path(run_dir, checkpoint_stage)
        if status == "awaiting_approval":
            self._mark_stage_awaiting_approval(
                run_dir,
                checkpoint_stage,
                source_script_name=source_script_name,
                reason=reason,
                artifact_path=artifact_path,
            )
        else:
            self._mark_stage_blocked(
                run_dir,
                checkpoint_stage,
                source_script_name=source_script_name,
                reason=reason,
                artifact_path=artifact_path,
            )
        return self._result(
            status=status,
            run_dir=run_dir,
            stage=checkpoint_stage,
            reason=reason,
            extra={"review_stage": review_stage, "target_stage": target_stage},
        )

    def _enforce_prerequisite_reviews(
        self,
        run_dir: Path,
        *,
        target_stage: WorkflowStage,
        source_script_name: str,
    ) -> dict[str, Any] | None:
        reviews = ensure_reviews(run_dir)
        for review_stage in PREREQUISITE_REVIEWS_BY_STAGE[target_stage]:
            review = reviews.reviews.get(review_stage)
            review_status = review.status if review is not None else "pending"
            if review_status == "approved":
                continue
            if review_status == "rejected":
                detail = f" Notes: {review.notes.strip()}" if review is not None and review.notes.strip() else ""
                reason = (
                    f"Review `{review_stage}` is rejected. Update artifacts or change the review before "
                    f"running `{target_stage}`.{detail}"
                )
                return self._review_gate_result(
                    run_dir,
                    review_stage=review_stage,
                    source_script_name=source_script_name,
                    target_stage=target_stage,
                    status="blocked",
                    reason=reason,
                )
            reason = f"Awaiting operator approval for `{review_stage}` before running `{target_stage}`."
            return self._review_gate_result(
                run_dir,
                review_stage=review_stage,
                source_script_name=source_script_name,
                target_stage=target_stage,
                status="awaiting_approval",
                reason=reason,
            )
        return None

    def _review_event_types_by_stage(self, run_dir: Path) -> dict[str, set[str]]:
        event_types_by_stage: dict[str, set[str]] = {}
        for event in self.read_events(run_dir, limit=0):
            if not isinstance(event, dict):
                continue
            stage = str(event.get("stage", "")).strip()
            event_type = str(event.get("event_type", "")).strip()
            if not stage or not event_type:
                continue
            event_types_by_stage.setdefault(stage, set()).add(event_type)
        return event_types_by_stage

    def _bootstrap_legacy_reviews(self, run_dir: Path, *, source_script_name: str) -> bool:
        reviews = ensure_reviews(run_dir)
        event_types_by_stage = self._review_event_types_by_stage(run_dir)
        changed = False

        for review_stage in REVIEW_STAGE_ORDER:
            review = reviews.reviews.get(review_stage)
            if review is None or review.status != "pending":
                continue
            if review.reviewer.strip() or review.notes.strip() or review.metadata:
                continue

            checkpoint_stage = REVIEW_CHECKPOINT_STAGE[review_stage]
            artifact_path = self.canonical_stage_artifact_path(run_dir, checkpoint_stage)
            if not artifact_path.exists():
                continue

            event_types = event_types_by_stage.get(review_stage, set()) | event_types_by_stage.get(checkpoint_stage, set())
            if {"review_reset", "review_updated", "review_auto_approved"} & event_types:
                continue

            metadata = {
                "source": "legacy_review_bootstrap",
                "auto_approved": True,
                "checkpoint_stage": checkpoint_stage,
                "checkpoint_artifact_path": str(artifact_path.resolve()),
            }
            update_review(
                run_dir,
                stage=review_stage,
                status="approved",
                reviewer="system",
                notes="Recovered existing legacy checkpoint artifact during compatibility sync.",
                metadata=metadata,
            )

            state = ensure_run_state(run_dir, source_script_name=source_script_name)
            checkpoint_state = state.stages.get(checkpoint_stage)
            if checkpoint_state is None or checkpoint_state.status != "succeeded" or state.awaiting_approval_stage == checkpoint_stage:
                run_status = state.status
                last_error = state.last_error
                if state.awaiting_approval_stage == checkpoint_stage:
                    run_status = self._active_run_status(run_dir)
                    if "Awaiting operator approval" in last_error and f"`{review_stage}`" in last_error:
                        last_error = ""
                update_stage_state(
                    run_dir,
                    stage=checkpoint_stage,
                    status="succeeded",
                    message=f"Recovered legacy `{review_stage}` approval from existing artifact.",
                    artifact_path=str(artifact_path.resolve()),
                    metadata={"legacy_review_bootstrap": True},
                    source_script_name=source_script_name,
                    run_status=run_status,
                    current_stage=state.current_stage or checkpoint_stage,
                    last_error=last_error,
                )

            append_run_event(
                run_dir,
                event_type="review_auto_approved",
                stage=review_stage,
                message=f"Auto-approved legacy `{review_stage}` review from existing checkpoint artifact.",
                data=metadata,
            )
            event_types_by_stage.setdefault(review_stage, set()).add("review_auto_approved")
            event_types_by_stage.setdefault(checkpoint_stage, set()).add("review_auto_approved")
            changed = True

        return changed

    def sync_run_state(self, run_dir: Path, *, source_script_name: str = "") -> RunState:
        state = ensure_run_state(run_dir, source_script_name=source_script_name)
        reviews = ensure_reviews(run_dir)
        changed = False
        effective_source_name = source_script_name or state.source_script_name or self.load_source_script_name(run_dir)
        if effective_source_name and not state.source_script_name:
            state.source_script_name = effective_source_name
            changed = True

        reviews_changed = False
        repair_timestamp = utc_now_iso()
        for review_stage in REVIEW_STAGE_ORDER:
            checkpoint_stage = REVIEW_CHECKPOINT_STAGE[review_stage]
            artifact_path = self.canonical_stage_artifact_path(run_dir, checkpoint_stage)
            review = reviews.reviews.get(review_stage)
            stage_state = state.stages.get(checkpoint_stage)

            if review is not None and review.status == "approved" and not artifact_path.exists():
                review.status = "pending"
                review.reviewer = ""
                review.notes = ""
                review.updated_at = repair_timestamp
                review.metadata["auto_reset_missing_artifact"] = True
                review.metadata["checkpoint_stage"] = checkpoint_stage
                reviews.updated_at = repair_timestamp
                reviews_changed = True

            if stage_state is None or artifact_path.exists():
                continue
            if stage_state.status != "succeeded":
                continue

            stage_state.status = "pending"
            stage_state.message = ""
            stage_state.artifact_path = ""
            stage_state.finished_at = ""
            stage_state.updated_at = repair_timestamp
            if state.current_stage == checkpoint_stage:
                state.current_stage = ""
            changed = True

        if reviews_changed:
            write_reviews(run_dir, reviews)

        latest_succeeded_stage = ""
        for stage in (*CORE_STAGE_ORDER, *OPTIONAL_STAGE_ORDER):
            artifact_path = self.canonical_stage_artifact_path(run_dir, stage)
            stage_state = state.stages.get(stage)
            if artifact_path.exists() and stage_state is not None and stage_state.status == "pending":
                stage_state.status = "succeeded"
                stage_state.artifact_path = str(artifact_path.resolve())
                stage_state.message = "Detected existing artifact."
                stage_state.updated_at = state.updated_at
                if not stage_state.started_at:
                    stage_state.started_at = state.updated_at
                if not stage_state.finished_at:
                    stage_state.finished_at = state.updated_at
                changed = True
            if artifact_path.exists():
                latest_succeeded_stage = stage

        if (run_dir / "10_final" / "final_video.mp4").exists():
            if state.status != "succeeded":
                state.status = "succeeded"
                state.current_stage = "final_video"
                state.last_error = ""
                changed = True
        elif latest_succeeded_stage and state.status == "pending":
            state.status = "running"
            state.current_stage = latest_succeeded_stage
            changed = True

        if changed:
            write_run_state(run_dir, state)

        if self._bootstrap_legacy_reviews(run_dir, source_script_name=effective_source_name):
            state = ensure_run_state(run_dir, source_script_name=effective_source_name)
        return state

    def inspect_run(self, run_dir: Path | str) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        if not resolved_run_dir.exists():
            raise FileNotFoundError(f"Run directory not found: {resolved_run_dir}")
        state = self.sync_run_state(resolved_run_dir)
        run_state_payload = state.model_dump(mode="json")
        for stage_name, stage_payload in run_state_payload.get("stages", {}).items():
            if not isinstance(stage_payload, dict):
                continue
            stage_payload.update(
                self.build_stage_preview(
                    resolved_run_dir,
                    stage_name,
                    fallback_message=str(stage_payload.get("message", "")).strip(),
                )
            )
        return {
            "status": "ok",
            "run_dir": str(resolved_run_dir),
            "artifacts": self.artifact_snapshot(resolved_run_dir),
            "run_state": run_state_payload,
            "route_decision": self.build_route_decision_summary(resolved_run_dir),
        }

    def list_runs(self, *, limit: int = 50) -> list[dict[str, Any]]:
        run_dirs = [
            path
            for path in self.output_root.iterdir()
            if path.is_dir() and path.name.startswith("run")
        ]
        run_dirs.sort(key=lambda path: path.name, reverse=True)

        summaries: list[dict[str, Any]] = []
        for run_dir in run_dirs[: max(1, limit)]:
            state = self.sync_run_state(run_dir)
            summaries.append(
                {
                    "run_id": run_dir.name,
                    "run_dir": str(run_dir.resolve()),
                    "source_script_name": state.source_script_name or self.load_source_script_name(run_dir),
                    "status": state.status,
                    "current_stage": state.current_stage,
                    "updated_at": state.updated_at,
                    "final_video_path": self.artifact_snapshot(run_dir).get("final_video_path", ""),
                }
            )
        return summaries

    def read_events(self, run_dir: Path | str, *, limit: int = 200) -> list[dict[str, Any]]:
        resolved_run_dir = Path(run_dir).resolve()
        path = resolved_run_dir / "_meta" / "events.jsonl"
        if not path.exists():
            return []

        events: list[dict[str, Any]] = []
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                events.append(parsed)
        if limit <= 0:
            return events
        return events[-limit:]

    @staticmethod
    def _dedupe_preserve_order(values: Iterable[str]) -> list[str]:
        deduped: list[str] = []
        seen: set[str] = set()
        for raw_value in values:
            value = str(raw_value).strip()
            if not value or value in seen:
                continue
            deduped.append(value)
            seen.add(value)
        return deduped

    def _load_asset_review_lookup(self, run_dir: Path) -> dict[str, dict[str, Any]]:
        manifest_path = run_dir / "05_asset_images" / "asset_images_manifest.json"
        if not manifest_path.exists():
            return {}

        manifest = read_json(manifest_path)
        if not isinstance(manifest, dict):
            return {}

        lookup: dict[str, dict[str, Any]] = {}
        asset_type_by_group = {
            "characters": "character",
            "scenes": "scene",
            "props": "prop",
        }
        for group_name, asset_type in asset_type_by_group.items():
            entries = manifest.get(group_name, [])
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                asset_id = str(entry.get("id", "")).strip()
                if not asset_id:
                    continue
                local_path = Path(str(entry.get("local_image_path", "")).strip()) if entry.get("local_image_path") else None
                lookup[asset_id] = {
                    "asset_id": asset_id,
                    "asset_type": asset_type,
                    "group": group_name,
                    "name": entry.get("name", ""),
                    "label_text": entry.get("label_text", ""),
                    "local_image_path": str(local_path) if local_path else "",
                    "preview_url": _preview_url(run_dir, local_path) if local_path and local_path.exists() else "",
                    "raw_response_path": entry.get("raw_response_path", ""),
                }
        return lookup

    def _load_storyboard_board_lookup(self, run_dir: Path) -> dict[str, dict[str, Any]]:
        manifest_path = run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json"
        if not manifest_path.exists():
            return {}

        manifest = read_json(manifest_path)
        boards = manifest.get("boards", []) if isinstance(manifest, dict) else []
        if not isinstance(boards, list):
            return {}

        lookup: dict[str, dict[str, Any]] = {}
        for board in boards:
            if not isinstance(board, dict):
                continue
            shot_id = str(board.get("shot_id", "")).strip()
            if not shot_id:
                continue
            local_path = Path(str(board.get("board_local_path", "")).strip()) if board.get("board_local_path") else None
            lookup[shot_id] = {
                "board_preview_url": _preview_url(run_dir, local_path) if local_path and local_path.exists() else "",
                "board_local_path": str(local_path) if local_path else "",
                "board_public_url": str(board.get("board_public_url", "")).strip(),
                "layout_template": str(board.get("layout_template", "")).strip(),
                "asset_count": board.get("asset_count", ""),
                "blank_cell_count": board.get("blank_cell_count", ""),
            }
        return lookup

    def build_video_payload(self, run_dir: Path | str) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        shot_manifest_path = resolved_run_dir / "09_shot_videos" / "shot_videos_manifest.json"
        final_manifest_path = resolved_run_dir / "10_final" / "final_video_manifest.json"
        final_video_path = resolved_run_dir / "10_final" / "final_video.mp4"

        final_inputs_by_shot: dict[str, dict[str, Any]] = {}
        final_payload: dict[str, Any] = {
            "available": False,
            "preview_url": "",
            "local_path": str(final_video_path.resolve()) if final_video_path.exists() else "",
            "shot_count": 0,
            "trim_leading_seconds": "",
            "blackout_leading_seconds": "",
            "concat_mode": "",
            "title": "",
        }
        if final_manifest_path.exists():
            final_manifest = read_json(final_manifest_path)
            if isinstance(final_manifest, dict):
                manifest_video_path = Path(str(final_manifest.get("final_video_path", "")).strip()) if final_manifest.get("final_video_path") else final_video_path
                if manifest_video_path.exists():
                    final_payload["preview_url"] = _preview_url(resolved_run_dir, manifest_video_path)
                    final_payload["local_path"] = str(manifest_video_path.resolve())
                    final_payload["available"] = True
                concat_spec = final_manifest.get("concat_spec", {})
                if isinstance(concat_spec, dict):
                    final_payload["trim_leading_seconds"] = concat_spec.get("trim_leading_seconds", "")
                    final_payload["blackout_leading_seconds"] = concat_spec.get("blackout_leading_seconds", "")
                    final_payload["concat_mode"] = concat_spec.get("concat_mode", "")
                final_payload["title"] = str(final_manifest.get("title", "")).strip()
                inputs = final_manifest.get("inputs", [])
                if isinstance(inputs, list):
                    final_payload["shot_count"] = len(inputs)
                    for item in inputs:
                        if not isinstance(item, dict):
                            continue
                        shot_id = str(item.get("shot_id", "")).strip()
                        if not shot_id:
                            continue
                        trimmed_path = Path(str(item.get("trimmed_video_path", "")).strip()) if item.get("trimmed_video_path") else None
                        final_inputs_by_shot[shot_id] = {
                            "trimmed_video_path": str(trimmed_path.resolve()) if trimmed_path and trimmed_path.exists() else str(trimmed_path) if trimmed_path else "",
                            "trimmed_preview_url": _preview_url(resolved_run_dir, trimmed_path) if trimmed_path and trimmed_path.exists() else "",
                            "included_in_final": True,
                        }
        elif final_video_path.exists():
            final_payload["available"] = True
            final_payload["preview_url"] = _preview_url(resolved_run_dir, final_video_path)
            final_payload["local_path"] = str(final_video_path.resolve())

        shot_results: list[dict[str, Any]] = []
        status_counts: dict[str, int] = {}
        if shot_manifest_path.exists():
            manifest = read_json(shot_manifest_path)
            results = manifest.get("results", []) if isinstance(manifest, dict) else []
            for item in results if isinstance(results, list) else []:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("status", "")).strip() or "unknown"
                status_counts[status] = status_counts.get(status, 0) + 1
                local_path = Path(str(item.get("video_local_path", "")).strip()) if item.get("video_local_path") else None
                local_preview_url = _preview_url(resolved_run_dir, local_path) if local_path and local_path.exists() else ""
                external_url = str(item.get("video_url", "")).strip() or str(item.get("file_url", "")).strip()
                final_input = final_inputs_by_shot.get(str(item.get("shot_id", "")).strip(), {})
                shot_results.append(
                    {
                        "shot_id": item.get("shot_id", ""),
                        "order": item.get("order", ""),
                        "segment_ids": item.get("segment_ids", []),
                        "status": status,
                        "task_id": item.get("task_id", ""),
                        "video_name": item.get("video_name", ""),
                        "preview_url": local_preview_url or external_url,
                        "local_preview_url": local_preview_url,
                        "local_path": str(local_path.resolve()) if local_path and local_path.exists() else str(local_path) if local_path else "",
                        "external_url": external_url,
                        "error_message": item.get("error_message", ""),
                        "included_in_final": bool(final_input.get("included_in_final", False)),
                        "trimmed_preview_url": final_input.get("trimmed_preview_url", ""),
                        "trimmed_video_path": final_input.get("trimmed_video_path", ""),
                    }
                )

        shot_results.sort(key=lambda item: int(item.get("order") or 0))
        return {
            "run_id": resolved_run_dir.name,
            "summary": {
                "total_shots": len(shot_results),
                "succeeded_shots": status_counts.get("succeeded", 0),
                "failed_shots": sum(count for status, count in status_counts.items() if status not in {"succeeded"}),
                "status_counts": status_counts,
                "has_final_video": final_payload["available"],
            },
            "shot_videos": shot_results,
            "final_video": final_payload,
        }

    def list_reviews(self, run_dir: Path | str) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        reviews = ensure_reviews(resolved_run_dir)
        return reviews.model_dump(mode="json")

    def get_review(self, run_dir: Path | str, stage: ReviewStage) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        reviews = ensure_reviews(resolved_run_dir)
        review = reviews.reviews.get(stage)
        return {
            "run_id": resolved_run_dir.name,
            "stage": stage,
            "review": review.model_dump(mode="json") if review is not None else None,
            "payload": self.build_review_payload(resolved_run_dir, stage),
        }

    def submit_review(
        self,
        run_dir: Path | str,
        *,
        stage: ReviewStage,
        status: Literal["approved", "rejected", "pending"],
        reviewer: str = "",
        notes: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        effective_source_name = self.load_source_script_name(resolved_run_dir)
        checkpoint_stage = REVIEW_CHECKPOINT_STAGE[stage]
        artifact_path = self.canonical_stage_artifact_path(resolved_run_dir, checkpoint_stage)
        if status == "approved" and not artifact_path.exists():
            raise ValueError(
                f"Cannot approve `{stage}` because the checkpoint artifact is missing: {artifact_path}"
            )
        reviews = update_review(
            resolved_run_dir,
            stage=stage,
            status=status,
            reviewer=reviewer,
            notes=notes,
            metadata=metadata,
        )
        append_run_event(
            resolved_run_dir,
            event_type="review_updated",
            stage=stage,
            message=f"Review for `{stage}` set to `{status}`.",
            data={"reviewer": reviewer, "notes": notes, "metadata": metadata or {}},
        )
        if status == "approved":
            self._mark_stage_succeeded(
                resolved_run_dir,
                checkpoint_stage,
                source_script_name=effective_source_name,
                message=f"Operator approved `{stage}` review.",
                artifact_path=artifact_path,
                run_status=self._active_run_status(resolved_run_dir),
            )
        elif status == "rejected":
            reason = f"Operator rejected `{stage}` review."
            if notes.strip():
                reason = f"{reason} {notes.strip()}"
            self._mark_stage_blocked(
                resolved_run_dir,
                checkpoint_stage,
                source_script_name=effective_source_name,
                reason=reason,
                artifact_path=artifact_path,
            )
        else:
            reason = f"Awaiting operator approval for `{stage}`."
            if notes.strip():
                reason = f"{reason} Notes: {notes.strip()}"
            self._mark_stage_awaiting_approval(
                resolved_run_dir,
                checkpoint_stage,
                source_script_name=effective_source_name,
                reason=reason,
                artifact_path=artifact_path,
            )
        return {
            "run_id": resolved_run_dir.name,
            "reviews": reviews.model_dump(mode="json"),
            "payload": self.build_review_payload(resolved_run_dir, stage),
        }

    def build_review_payload(self, run_dir: Path, stage: ReviewStage) -> dict[str, Any]:
        if stage == "upstream":
            payload: dict[str, Any] = {
                "stage": stage,
                "artifacts": {},
                "summary": {},
            }
            for name in (
                "source_context.json",
                "intake_router.json",
                "asset_readiness_report.json",
                "script_quality_report.json",
                "generated_script.txt",
                "script_clean.txt",
            ):
                path = run_dir / ("00_source" if name != "script_clean.txt" else "01_input") / name
                if not path.exists():
                    continue
                if path.suffix == ".json":
                    payload["artifacts"][name] = read_json(path)
                else:
                    payload["artifacts"][name] = path.read_text(encoding="utf-8")
            intake_router = payload["artifacts"].get("intake_router.json")
            if isinstance(intake_router, dict):
                payload["summary"]["chosen_path"] = intake_router.get("chosen_path", "")
                payload["summary"]["recommended_operations"] = intake_router.get("recommended_operations", [])
            readiness = payload["artifacts"].get("asset_readiness_report.json")
            if isinstance(readiness, dict):
                payload["summary"]["ready_for_extraction"] = readiness.get("ready_for_extraction", "")
                payload["summary"]["blocking_issues"] = readiness.get("blocking_issues", [])
            return payload

        if stage == "asset_images":
            manifest_path = run_dir / "05_asset_images" / "asset_images_manifest.json"
            if not manifest_path.exists():
                return {"stage": stage, "summary": {}, "items": []}
            manifest = read_json(manifest_path)
            items: list[dict[str, Any]] = []
            for group_name in ("characters", "scenes", "props"):
                entries = manifest.get(group_name, []) if isinstance(manifest, dict) else []
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    if not isinstance(entry, dict):
                        continue
                    local_path = Path(str(entry.get("local_image_path", "")).strip()) if entry.get("local_image_path") else None
                    items.append(
                        {
                            "group": group_name,
                            "id": entry.get("id", ""),
                            "name": entry.get("name", ""),
                            "label_text": entry.get("label_text", ""),
                            "local_image_path": str(local_path) if local_path else "",
                            "preview_url": _preview_url(run_dir, local_path) if local_path and local_path.exists() else "",
                            "raw_response_path": entry.get("raw_response_path", ""),
                        }
                    )
            return {
                "stage": stage,
                "summary": {
                    "character_count": len(manifest.get("characters", [])) if isinstance(manifest, dict) else 0,
                    "scene_count": len(manifest.get("scenes", [])) if isinstance(manifest, dict) else 0,
                    "prop_count": len(manifest.get("props", [])) if isinstance(manifest, dict) else 0,
                },
                "items": items,
            }

        storyboard_path = run_dir / "06_storyboard" / "storyboard.json"
        if not storyboard_path.exists():
            return {"stage": stage, "summary": {}, "shots": []}
        storyboard = read_json(storyboard_path)
        shots = storyboard.get("shots", []) if isinstance(storyboard, dict) else []
        asset_lookup = self._load_asset_review_lookup(run_dir)
        board_lookup = self._load_storyboard_board_lookup(run_dir)
        shot_summaries: list[dict[str, Any]] = []
        if isinstance(shots, list):
            for shot in shots:
                if not isinstance(shot, dict):
                    continue
                shot_id = shot.get("shot_id") or shot.get("id", "")
                primary_scene_id = str(shot.get("primary_scene_id", "")).strip()
                character_ids = shot.get("character_ids", [])
                prop_ids = shot.get("prop_ids", [])
                reference_assets: list[dict[str, Any]] = []
                for asset_id in self._dedupe_preserve_order(
                    [primary_scene_id, *(character_ids if isinstance(character_ids, list) else []), *(prop_ids if isinstance(prop_ids, list) else [])]
                ):
                    asset_entry = asset_lookup.get(asset_id)
                    if asset_entry is None:
                        asset_entry = {
                            "asset_id": asset_id,
                            "asset_type": "unknown",
                            "group": "",
                            "name": asset_id,
                            "label_text": "",
                            "local_image_path": "",
                            "preview_url": "",
                            "raw_response_path": "",
                        }
                    reference_assets.append(asset_entry)
                board_payload = board_lookup.get(str(shot_id).strip(), {})
                shot_summaries.append(
                    {
                        "shot_id": shot_id,
                        "order": shot.get("order", ""),
                        "duration_sec": shot.get("duration_sec", ""),
                        "shot_type": shot.get("shot_type", ""),
                        "camera_movement": shot.get("camera_movement", ""),
                        "camera_angle": shot.get("camera_angle", ""),
                        "shot_size": shot.get("shot_size", ""),
                        "location": shot.get("location", ""),
                        "summary": shot.get("summary") or shot.get("shot_purpose", ""),
                        "subject_action": shot.get("subject_action", ""),
                        "background_action": shot.get("background_action", ""),
                        "emotion_tone": shot.get("emotion_tone", ""),
                        "continuity_notes": shot.get("continuity_notes", []),
                        "primary_scene_id": primary_scene_id,
                        "prompt": shot.get("shot_prompt") or shot.get("prompt_core", ""),
                        "character_ids": character_ids if isinstance(character_ids, list) else [],
                        "scene_ids": shot.get("scene_ids", []),
                        "prop_ids": prop_ids if isinstance(prop_ids, list) else [],
                        "reference_assets": reference_assets,
                        "board_preview_url": board_payload.get("board_preview_url", ""),
                        "board_local_path": board_payload.get("board_local_path", ""),
                        "board_public_url": board_payload.get("board_public_url", ""),
                        "board_layout_template": board_payload.get("layout_template", ""),
                        "board_asset_count": board_payload.get("asset_count", ""),
                    }
                )
        return {
            "stage": stage,
            "summary": {
                "shot_count": len(shot_summaries),
                "title": storyboard.get("title", "") if isinstance(storyboard, dict) else "",
                "shot_ids": [shot["shot_id"] for shot in shot_summaries],
            },
            "shots": shot_summaries,
        }

    def start_or_resume(
        self,
        *,
        source_text: str = "",
        source_path: str = "",
        source_script_name: str = "",
        input_mode: Literal["auto", "keywords", "brief", "script"] = AUTO_INPUT_MODE,
        run_dir: str = "",
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        try:
            upstream_changed = False
            if run_dir.strip():
                resolved_run_dir = Path(run_dir).resolve()
                if not resolved_run_dir.exists():
                    raise WorkflowBlockedError("upstream", f"run_dir not found: {resolved_run_dir}")
                effective_source_name, resume_message, upstream_changed = self.recover_upstream_for_existing_run(
                    run_dir=resolved_run_dir,
                    input_mode=input_mode,
                )
            else:
                resolved_source_path: Path | None = None
                if source_text.strip():
                    effective_source_text = source_text
                    effective_source_name = source_script_name.strip() or "intent_input"
                else:
                    resolved_source_path = Path(source_path).resolve() if source_path.strip() else DEFAULT_SOURCE_PATH.resolve()
                    if not resolved_source_path.exists():
                        raise WorkflowBlockedError("upstream", f"source file not found: {resolved_source_path}")
                    effective_source_text = resolved_source_path.read_text(encoding="utf-8")
                    effective_source_name = source_script_name.strip() or resolved_source_path.stem

                def emit_progress(payload: dict[str, Any]) -> None:
                    if progress_callback is not None:
                        progress_callback(payload)
                    resolved_progress_run_dir = str(payload.get("run_dir", "")).strip()
                    if not resolved_progress_run_dir:
                        return
                    message = str(payload.get("message", "")).strip()
                    if not message:
                        return
                    progress_data = {key: value for key, value in payload.items() if key != "message"}
                    append_run_event(
                        Path(resolved_progress_run_dir).resolve(),
                        event_type="operator_progress",
                        stage=str(payload.get("stage", "upstream")).strip() or "upstream",
                        message=message,
                        data=progress_data,
                    )

                upstream_artifacts = generate_script_from_intent(
                    source_text=effective_source_text,
                    source_script_name=effective_source_name,
                    model_config=self.text_config,
                    output_root=self.output_root,
                    run_dir=None,
                    source_path=resolved_source_path,
                    input_mode=input_mode,
                    extract_assets=False,
                    progress_callback=emit_progress,
                )
                resolved_run_dir = upstream_artifacts.run_dir.resolve()
                resume_message = "Upstream intake routing finished. Downstream workflow can continue from script_clean.txt."
                upstream_changed = True
            if run_dir.strip() and progress_callback is not None:
                progress_callback(
                    {
                        "message": "正在恢复已有运行目录。",
                        "step": "输入接收",
                        "stage": "upstream",
                        "run_dir": str(resolved_run_dir.resolve()),
                    }
                )

            self.sync_run_state(resolved_run_dir, source_script_name=effective_source_name)
            script_clean_path = resolved_run_dir / "01_input" / "script_clean.txt"
            if not script_clean_path.exists():
                reason = (
                    "Upstream routing did not produce 01_input/script_clean.txt. "
                    f"Check the router output under {resolved_run_dir / '00_source' / 'intake_router.json'}."
                )
                self._mark_stage_blocked(
                    resolved_run_dir,
                    "upstream",
                    source_script_name=effective_source_name,
                    reason=reason,
                    artifact_path=resolved_run_dir / "00_source" / "intake_router.json",
                )
                return self._result(
                    status="blocked",
                    run_dir=resolved_run_dir,
                    stage="upstream",
                    reason=reason,
                    extra={"source_script_name": effective_source_name},
                )

            self._mark_stage_succeeded(
                resolved_run_dir,
                "upstream",
                source_script_name=effective_source_name,
                message=resume_message,
                artifact_path=script_clean_path,
            )
            if upstream_changed:
                self._set_checkpoint_review_pending(
                    resolved_run_dir,
                    review_stage="upstream",
                    source_script_name=effective_source_name,
                    reset_reason="Awaiting operator approval for `upstream` before downstream execution.",
                    metadata={"reset_by_stage": "upstream"},
                )
            return self._result(
                status="ok",
                run_dir=resolved_run_dir,
                stage="upstream",
                message=resume_message,
                extra={"source_script_name": effective_source_name},
            )
        except WorkflowBlockedError as exc:
            run_dir_path = Path(run_dir).resolve() if run_dir.strip() else None
            if run_dir_path is not None and run_dir_path.exists():
                effective_source_name = source_script_name.strip() or self.load_source_script_name(run_dir_path)
                self.sync_run_state(run_dir_path, source_script_name=effective_source_name)
                self._mark_stage_blocked(
                    run_dir_path,
                    "upstream",
                    source_script_name=effective_source_name,
                    reason=exc.message,
                    artifact_path=run_dir_path / "00_source" / "intake_router.json",
                )
                return self._result(status="blocked", run_dir=run_dir_path, stage="upstream", reason=exc.message)
            return {
                "status": "blocked",
                "stage": "upstream",
                "reason": exc.message,
                "run_dir": str(run_dir_path) if run_dir_path else "",
                "artifacts": {},
            }

    def run_stage(
        self,
        stage: WorkflowStage,
        *,
        run_dir: Path | str,
        source_script_name: str = "",
        force: bool = False,
        publish_strategy: Literal["auto", "tos", "jsdelivr"] = "auto",
        selected_shots: set[str] | None = None,
        resolution: str = "720p",
        timeout_seconds: int = 1800,
        poll_interval_seconds: int = 10,
        keep_remote_media: bool = False,
        trim_leading_seconds: float = DEFAULT_TRIM_LEADING_SECONDS,
        blackout_leading_seconds: float = DEFAULT_BLACKOUT_LEADING_SECONDS,
    ) -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        if not resolved_run_dir.exists():
            return {
                "status": "blocked",
                "stage": stage,
                "reason": f"run_dir not found: {resolved_run_dir}",
                "run_dir": str(resolved_run_dir),
                "artifacts": {},
            }

        effective_source_name = source_script_name or self.load_source_script_name(resolved_run_dir)
        self.sync_run_state(resolved_run_dir, source_script_name=effective_source_name)
        artifact_path = self.canonical_stage_artifact_path(resolved_run_dir, stage)

        try:
            if stage == "upstream":
                raise WorkflowBlockedError("upstream", "Use `start_or_resume` for the upstream stage.")

            gate_result = self._enforce_prerequisite_reviews(
                resolved_run_dir,
                target_stage=stage,
                source_script_name=effective_source_name,
            )
            if gate_result is not None:
                return gate_result

            if stage == "board_publish":
                manifest_path = resolved_run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json"
                if not manifest_path.exists():
                    raise WorkflowBlockedError("board_publish", f"shot_reference_manifest.json missing: {manifest_path}")
                reachable, detail = self.has_reachable_board_urls(manifest_path)
                if reachable and not force:
                    message = f"Reused existing public board URLs ({detail})."
                    self._mark_stage_succeeded(
                        resolved_run_dir,
                        stage,
                        source_script_name=effective_source_name,
                        message=message,
                        artifact_path=self.board_publish_result_path(resolved_run_dir),
                        metadata={"reused_existing_artifact": True},
                    )
                    return self._result(status="ok", run_dir=resolved_run_dir, stage=stage, message=message)
            elif artifact_path.exists() and not force:
                message = f"Reused existing {artifact_path.name}."
                self._mark_stage_succeeded(
                    resolved_run_dir,
                    stage,
                    source_script_name=effective_source_name,
                    message=message,
                    artifact_path=artifact_path,
                    metadata={"reused_existing_artifact": True},
                )
                return self._result(status="ok", run_dir=resolved_run_dir, stage=stage, message=message)

            self._mark_stage_running(resolved_run_dir, stage, effective_source_name)

            if stage == "asset_extraction":
                script_clean_path = self.ensure_script_clean_exists(resolved_run_dir)
                extract_asset_registry_from_text(
                    source_script_name=effective_source_name,
                    script_text=script_clean_path.read_text(encoding="utf-8"),
                    model_config=self.text_config,
                    output_root=self.output_root,
                    run_dir=resolved_run_dir,
                    source_path=DEFAULT_SOURCE_PATH if DEFAULT_SOURCE_PATH.exists() else None,
                )
                message = "Generated asset_registry.json."
            elif stage == "style_bible":
                asset_registry_path = resolved_run_dir / "02_assets" / "asset_registry.json"
                if not asset_registry_path.exists():
                    raise WorkflowBlockedError("style_bible", f"asset_registry.json missing: {asset_registry_path}")
                generate_style_bible(asset_registry_path=asset_registry_path, model_config=self.text_config)
                message = "Generated style_bible.json."
            elif stage == "asset_prompts":
                style_bible_path = resolved_run_dir / "03_style" / "style_bible.json"
                if not style_bible_path.exists():
                    raise WorkflowBlockedError("asset_prompts", f"style_bible.json missing: {style_bible_path}")
                generate_asset_prompts(style_bible_path=style_bible_path, model_config=self.text_config)
                message = "Generated asset_prompts.json."
            elif stage == "asset_images":
                asset_prompts_path = resolved_run_dir / "04_asset_prompts" / "asset_prompts.json"
                if not asset_prompts_path.exists():
                    raise WorkflowBlockedError("asset_images", f"asset_prompts.json missing: {asset_prompts_path}")
                generate_asset_images(asset_prompts_path=asset_prompts_path, model_config=self.image_config)
                message = "Generated asset_images_manifest.json."
            elif stage == "storyboard_seed":
                self.build_storyboard_seed(resolved_run_dir, effective_source_name)
                message = "Generated storyboard_seed.json."
            elif stage == "storyboard":
                style_bible_path = resolved_run_dir / "03_style" / "style_bible.json"
                if not style_bible_path.exists():
                    raise WorkflowBlockedError("storyboard", f"style_bible.json missing: {style_bible_path}")
                generate_storyboard(style_bible_path=style_bible_path, model_config=self.text_config)
                message = "Generated storyboard.json."
            elif stage == "shot_reference_boards":
                storyboard_path = resolved_run_dir / "06_storyboard" / "storyboard.json"
                if not storyboard_path.exists():
                    raise WorkflowBlockedError("shot_reference_boards", f"storyboard.json missing: {storyboard_path}")
                generate_shot_reference_boards(storyboard_path=storyboard_path)
                message = "Generated shot_reference_manifest.json."
            elif stage == "board_publish":
                manifest_path = resolved_run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json"
                publish_mode, publish_result_path = self.publish_boards_auto(manifest_path, publish_strategy)
                artifact_path = publish_result_path
                message = f"Published shot reference boards via {publish_mode}."
            elif stage == "video_jobs":
                storyboard_path = resolved_run_dir / "06_storyboard" / "storyboard.json"
                if not storyboard_path.exists():
                    raise WorkflowBlockedError("video_jobs", f"storyboard.json missing: {storyboard_path}")
                generate_video_jobs(storyboard_path=storyboard_path, model_config=self.video_config)
                message = "Generated video_jobs.json."
            elif stage == "shot_videos":
                video_jobs_path = resolved_run_dir / "08_video_jobs" / "video_jobs.json"
                if not video_jobs_path.exists():
                    raise WorkflowBlockedError("shot_videos", f"video_jobs.json missing: {video_jobs_path}")
                generate_shot_videos(
                    video_jobs_path=video_jobs_path,
                    model_config=self.video_config,
                    selected_shots=selected_shots or set(),
                    resolution=resolution,
                    timeout_seconds=timeout_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                    keep_remote_media=keep_remote_media,
                )
                message = "Generated shot_videos_manifest.json."
            elif stage == "final_video":
                shot_videos_manifest_path = resolved_run_dir / "09_shot_videos" / "shot_videos_manifest.json"
                if not shot_videos_manifest_path.exists():
                    raise WorkflowBlockedError("final_video", f"shot_videos_manifest.json missing: {shot_videos_manifest_path}")
                generate_final_video(
                    shot_videos_manifest_path=shot_videos_manifest_path,
                    trim_leading_seconds=trim_leading_seconds,
                    blackout_leading_seconds=blackout_leading_seconds,
                )
                message = "Generated final_video.mp4."
            else:
                raise ValueError(f"Unsupported stage: {stage}")

            final_run_status: Literal["running", "succeeded"] = "succeeded" if stage == "final_video" else "running"
            self._mark_stage_succeeded(
                resolved_run_dir,
                stage,
                source_script_name=effective_source_name,
                message=message,
                artifact_path=artifact_path,
                run_status=final_run_status,
            )
            checkpoint_review = CHECKPOINT_REVIEW_STAGE.get(stage)
            if checkpoint_review is not None:
                self._set_checkpoint_review_pending(
                    resolved_run_dir,
                    review_stage=checkpoint_review,
                    source_script_name=effective_source_name,
                    reset_reason=f"Awaiting operator approval for `{checkpoint_review}` before downstream execution.",
                    metadata={"reset_by_stage": stage},
                )
            return self._result(status="ok", run_dir=resolved_run_dir, stage=stage, message=message)
        except WorkflowBlockedError as exc:
            self._mark_stage_blocked(
                resolved_run_dir,
                stage,
                source_script_name=effective_source_name,
                reason=exc.message,
                artifact_path=artifact_path,
            )
            return self._result(status="blocked", run_dir=resolved_run_dir, stage=stage, reason=exc.message)
        except Exception as exc:
            self._mark_stage_failed(
                resolved_run_dir,
                stage,
                source_script_name=effective_source_name,
                reason=str(exc),
                artifact_path=artifact_path,
            )
            return self._result(status="failed", run_dir=resolved_run_dir, stage=stage, reason=str(exc))

    def run_parallel_planning(self, *, run_dir: Path | str, source_script_name: str = "") -> dict[str, Any]:
        resolved_run_dir = Path(run_dir).resolve()
        if not resolved_run_dir.exists():
            return {
                "status": "blocked",
                "stage": "parallel_planning",
                "reason": f"run_dir not found: {resolved_run_dir}",
                "run_dir": str(resolved_run_dir),
                "artifacts": {},
            }

        effective_source_name = source_script_name or self.load_source_script_name(resolved_run_dir)
        self.sync_run_state(resolved_run_dir, source_script_name=effective_source_name)
        gate_result = self._enforce_prerequisite_reviews(
            resolved_run_dir,
            target_stage="asset_extraction",
            source_script_name=effective_source_name,
        )
        if gate_result is not None:
            return gate_result
        append_run_event(
            resolved_run_dir,
            event_type="parallel_planning_started",
            stage="parallel_planning",
            message="Started asset extraction and storyboard seed in parallel.",
        )

        try:
            script_clean_path = self.ensure_script_clean_exists(resolved_run_dir)
            with ThreadPoolExecutor(max_workers=2) as executor:
                asset_future = executor.submit(
                    extract_asset_registry_from_text,
                    source_script_name=effective_source_name,
                    script_text=script_clean_path.read_text(encoding="utf-8"),
                    model_config=self.text_config,
                    output_root=self.output_root,
                    run_dir=resolved_run_dir,
                    source_path=DEFAULT_SOURCE_PATH if DEFAULT_SOURCE_PATH.exists() else None,
                )
                seed_future = executor.submit(self.build_storyboard_seed, resolved_run_dir, effective_source_name)
                asset_artifacts = asset_future.result()
                seed_path = seed_future.result()

            self._mark_stage_succeeded(
                resolved_run_dir,
                "asset_extraction",
                source_script_name=effective_source_name,
                message="Generated asset_registry.json.",
                artifact_path=asset_artifacts.asset_dir / "asset_registry.json",
            )
            self._mark_stage_succeeded(
                resolved_run_dir,
                "storyboard_seed",
                source_script_name=effective_source_name,
                message="Generated storyboard_seed.json.",
                artifact_path=seed_path,
            )
            append_run_event(
                resolved_run_dir,
                event_type="parallel_planning_succeeded",
                stage="parallel_planning",
                message="Parallel planning completed.",
            )
            return self._result(
                status="ok",
                run_dir=resolved_run_dir,
                stage="parallel_planning",
                message="Asset extraction and storyboard seed completed.",
            )
        except WorkflowBlockedError as exc:
            append_run_event(
                resolved_run_dir,
                event_type="parallel_planning_blocked",
                stage="parallel_planning",
                message=exc.message,
            )
            return self._result(status="blocked", run_dir=resolved_run_dir, stage="parallel_planning", reason=exc.message)
        except Exception as exc:
            append_run_event(
                resolved_run_dir,
                event_type="parallel_planning_failed",
                stage="parallel_planning",
                message=str(exc),
            )
            return self._result(status="failed", run_dir=resolved_run_dir, stage="parallel_planning", reason=str(exc))

    def run_mainline(
        self,
        *,
        source_text: str = "",
        source_path: str = "",
        source_script_name: str = "",
        input_mode: Literal["auto", "keywords", "brief", "script"] = AUTO_INPUT_MODE,
        run_dir: str = "",
        include_storyboard_seed: bool = False,
        parallel_planning: bool = False,
        publish_strategy: Literal["auto", "tos", "jsdelivr"] = "auto",
        selected_shots: set[str] | None = None,
        resolution: str = "720p",
        timeout_seconds: int = 1800,
        poll_interval_seconds: int = 10,
        keep_remote_media: bool = False,
        trim_leading_seconds: float = DEFAULT_TRIM_LEADING_SECONDS,
        blackout_leading_seconds: float = DEFAULT_BLACKOUT_LEADING_SECONDS,
        progress_callback: ProgressCallback | None = None,
    ) -> dict[str, Any]:
        start_result = self.start_or_resume(
            source_text=source_text,
            source_path=source_path,
            source_script_name=source_script_name,
            input_mode=input_mode,
            run_dir=run_dir,
            progress_callback=progress_callback,
        )
        if start_result.get("status") != "ok":
            return start_result

        resolved_run_dir = Path(str(start_result["run_dir"])).resolve()
        effective_source_name = str(start_result.get("source_script_name", "")).strip() or self.load_source_script_name(
            resolved_run_dir
        )

        if parallel_planning:
            parallel_result = self.run_parallel_planning(run_dir=resolved_run_dir, source_script_name=effective_source_name)
            if parallel_result.get("status") != "ok":
                return parallel_result
            remaining_stages = (
                "style_bible",
                "asset_prompts",
                "asset_images",
                "storyboard",
                "shot_reference_boards",
                "board_publish",
                "video_jobs",
                "shot_videos",
                "final_video",
            )
        else:
            remaining_stages = CORE_STAGE_ORDER[1:]

        if include_storyboard_seed and not parallel_planning:
            seed_result = self.run_stage("storyboard_seed", run_dir=resolved_run_dir, source_script_name=effective_source_name)
            if seed_result.get("status") != "ok":
                return seed_result

        for stage in remaining_stages:
            result = self.run_stage(
                stage,  # type: ignore[arg-type]
                run_dir=resolved_run_dir,
                source_script_name=effective_source_name,
                publish_strategy=publish_strategy,
                selected_shots=selected_shots,
                resolution=resolution,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                keep_remote_media=keep_remote_media,
                trim_leading_seconds=trim_leading_seconds,
                blackout_leading_seconds=blackout_leading_seconds,
            )
            result_status = str(result.get("status", "")).strip()
            if result_status == "awaiting_approval":
                return result
            if result_status != "ok":
                return {
                    "status": "partial",
                    "stage": str(result.get("stage", stage)),
                    "run_dir": str(resolved_run_dir),
                    "artifacts": self.artifact_snapshot(resolved_run_dir),
                    "run_state": self.inspect_run(resolved_run_dir)["run_state"],
                    "last_result": result,
                }
            checkpoint_review = CHECKPOINT_REVIEW_STAGE.get(stage)  # type: ignore[arg-type]
            if checkpoint_review is not None:
                review_status = ensure_reviews(resolved_run_dir).reviews[checkpoint_review].status
                if review_status != "approved":
                    return self._result(
                        status="awaiting_approval",
                        run_dir=resolved_run_dir,
                        stage=stage,
                        reason=f"Awaiting operator approval for `{checkpoint_review}` before continuing.",
                        extra={"review_stage": checkpoint_review},
                    )

        return {
            "status": "ok",
            "stage": "mainline_workflow_completed",
            "run_dir": str(resolved_run_dir),
            "artifacts": self.artifact_snapshot(resolved_run_dir),
            "run_state": self.inspect_run(resolved_run_dir)["run_state"],
        }
