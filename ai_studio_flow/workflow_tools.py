from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path, PurePosixPath
import subprocess
from typing import Any, Literal

from google.adk.tools import ToolContext
import httpx
from pydantic import BaseModel, Field, model_validator
from tos import TosClientV2
from tos.enum import HttpMethodType

from pipeline.asset_extraction import extract_asset_registry_from_text, extract_first_json_object
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
from pipeline.asset_prompts import generate_asset_prompts
from pipeline.asset_images import generate_asset_images
from pipeline.shot_reference_boards import generate_shot_reference_boards
from pipeline.shot_reference_publish import publish_shot_reference_boards
from pipeline.shot_videos import generate_shot_videos
from pipeline.storyboard import generate_storyboard
from pipeline.style_bible import generate_style_bible
from pipeline.video_jobs import generate_video_jobs
from schemas.shot_reference_manifest import ShotReferenceManifest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOCAL_CONFIG_PATH = PROJECT_ROOT / "agentkit.local.yaml"
DEFAULT_SOURCE_PATH = PROJECT_ROOT / "01-陨落的天才.txt"


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


def _load_text_config():
    return load_text_model_config(LOCAL_CONFIG_PATH)


def _load_image_config():
    return load_image_model_config(LOCAL_CONFIG_PATH)


def _load_video_config():
    return load_video_model_config(LOCAL_CONFIG_PATH)


def _resolve_run_dir(tool_context: ToolContext) -> Path | None:
    run_dir = tool_context.state.get("current_run_dir", "")
    if not run_dir:
        return None
    return Path(str(run_dir)).resolve()


def _set_stage(tool_context: ToolContext, stage: str) -> None:
    history = list(tool_context.state.get("workflow_history", []))
    history.append(stage)
    tool_context.state["workflow_history"] = history
    tool_context.state["current_stage"] = stage


def _artifact_snapshot(run_dir: Path) -> dict[str, str]:
    board_publish_result_path = run_dir / "07_shot_reference_boards" / "board_publish_tos_result.json"
    if not board_publish_result_path.exists():
        board_publish_result_path = run_dir / "07_shot_reference_boards" / "board_publish_result.json"
    paths = {
        "source_input_path": run_dir / "00_source" / "source_input.txt",
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
    }
    return {key: str(path.resolve()) if path.exists() else "" for key, path in paths.items()}


def _blocked(tool_context: ToolContext, stage: str, reason: str) -> dict[str, Any]:
    _set_stage(tool_context, f"blocked:{stage}")
    run_dir = _resolve_run_dir(tool_context)
    return {
        "status": "blocked",
        "stage": stage,
        "reason": reason,
        "run_dir": str(run_dir) if run_dir else "",
        "artifacts": _artifact_snapshot(run_dir) if run_dir else {},
    }


def _completed(tool_context: ToolContext, stage: str, run_dir: Path, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    _set_stage(tool_context, stage)
    payload = {
        "status": "ok",
        "stage": stage,
        "run_dir": str(run_dir),
        "artifacts": _artifact_snapshot(run_dir),
    }
    if extra:
        payload.update(extra)
    return payload


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


def _require_script_clean(run_dir: Path) -> Path:
    script_clean_path = run_dir / "01_input" / "script_clean.txt"
    if not script_clean_path.exists():
        raise FileNotFoundError(f"script_clean.txt not found: {script_clean_path}")
    return script_clean_path


def _require_state_run_dir(tool_context: ToolContext, stage: str) -> Path | None:
    run_dir = _resolve_run_dir(tool_context)
    if run_dir is None:
        return None
    return run_dir


def _build_storyboard_seed(run_dir: Path, source_script_name: str) -> Path:
    source_dir = run_dir / "00_source"
    source_dir.mkdir(parents=True, exist_ok=True)
    script_clean_text = _require_script_clean(run_dir).read_text(encoding="utf-8")
    model_config = _load_text_config()
    request_path = source_dir / "storyboard_seed_request.json"
    response_path = source_dir / "storyboard_seed_response.json"
    output_path = source_dir / "storyboard_seed.json"

    request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": STORYBOARD_SEED_SYSTEM_PROMPT,
        "user_prompt": (
            f"source_run: {run_dir.name}\n"
            f"source_script_name: {source_script_name}\n"
            f"title: {source_script_name}\n\n"
            f"script_clean_text:\n{script_clean_text}"
        ),
    }
    write_json(request_path, request_payload)

    client = build_text_client(model_config)
    response = client.chat.completions.create(
        model=model_config.model_name,
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
    parsed = _parse_json_object(content)
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


def _load_board_publish_env() -> dict[str, str] | None:
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


def _build_object_key(key_prefix: str, source_run: str, filename: str) -> str:
    parts = [part for part in key_prefix.split("/") if part]
    parts.extend(["runs", source_run, "07_shot_reference_boards", "boards", filename])
    return PurePosixPath(*parts).as_posix()


def _run_git(args: list[str], repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _infer_github_repo_slug(repo_root: Path) -> str:
    remote_url = _run_git(["config", "--get", "remote.origin.url"], repo_root)
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


def _infer_git_ref(repo_root: Path) -> str:
    branch = _run_git(["branch", "--show-current"], repo_root)
    if branch:
        return branch
    raise ValueError(f"Cannot infer current branch for target repo: {repo_root}")


def _load_jsdelivr_publish_env(repo_root: Path) -> dict[str, str]:
    repo_slug = os.getenv("BOARD_JSDELIVR_REPO_SLUG", "").strip()
    ref = os.getenv("BOARD_JSDELIVR_REF", "").strip()
    url_prefix = os.getenv("BOARD_JSDELIVR_URL_PREFIX", "static").strip() or "static"
    publish_root_dir = os.getenv("BOARD_JSDELIVR_PUBLISH_ROOT", "").strip()

    resolved_publish_root = Path(publish_root_dir).resolve() if publish_root_dir else repo_root.resolve()
    return {
        "repo_slug": repo_slug or _infer_github_repo_slug(repo_root),
        "ref": ref or _infer_git_ref(repo_root),
        "url_prefix": url_prefix,
        "publish_root_dir": str(resolved_publish_root),
    }


def _check_public_url_reachable(url: str) -> tuple[bool, str]:
    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.head(url)
            if response.status_code == 405:
                response = client.get(url)
            return response.status_code == 200, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


def start_or_resume_workflow(
    source_text: str = "",
    source_path: str = "",
    source_script_name: str = "",
    input_mode: Literal["auto", "keywords", "brief", "script"] = AUTO_INPUT_MODE,
    run_dir: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Start the full workflow from user input, or resume an existing run directory."""

    assert tool_context is not None

    if run_dir.strip():
        resumed_run_dir = Path(run_dir).resolve()
        if not resumed_run_dir.exists():
            return _blocked(tool_context, "start_or_resume_workflow", f"run_dir not found: {resumed_run_dir}")
        tool_context.state["current_run_dir"] = str(resumed_run_dir)
        tool_context.state["source_script_name"] = source_script_name.strip() or resumed_run_dir.name
        return _completed(
            tool_context,
            "workflow_resumed",
            resumed_run_dir,
            {"message": "Resumed existing run directory without re-running upstream routing."},
        )

    resolved_source_path: Path | None = None
    if source_text.strip():
        effective_source_text = source_text
        effective_source_name = source_script_name.strip() or "intent_input"
    else:
        resolved_source_path = Path(source_path).resolve() if source_path.strip() else DEFAULT_SOURCE_PATH.resolve()
        if not resolved_source_path.exists():
            return _blocked(tool_context, "start_or_resume_workflow", f"source file not found: {resolved_source_path}")
        effective_source_text = resolved_source_path.read_text(encoding="utf-8")
        effective_source_name = source_script_name.strip() or resolved_source_path.stem

    artifacts = generate_script_from_intent(
        source_text=effective_source_text,
        source_script_name=effective_source_name,
        model_config=_load_text_config(),
        output_root=(PROJECT_ROOT / "runs").resolve(),
        run_dir=None,
        source_path=resolved_source_path,
        input_mode=input_mode,
        extract_assets=False,
    )
    run_dir_path = artifacts.run_dir.resolve()
    tool_context.state["current_run_dir"] = str(run_dir_path)
    tool_context.state["source_script_name"] = effective_source_name
    return _completed(
        tool_context,
        "input_routed",
        run_dir_path,
        {
            "message": "Upstream intake routing finished. Downstream workflow can continue from script_clean.txt.",
            "source_script_name": effective_source_name,
        },
    )


def run_asset_extraction_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Run the asset extraction stage for the current workflow run."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "asset_extraction")
    if run_dir is None:
        return _blocked(tool_context, "asset_extraction", "No current_run_dir in workflow state.")

    script_clean_path = run_dir / "01_input" / "script_clean.txt"
    if not script_clean_path.exists():
        return _blocked(tool_context, "asset_extraction", f"script_clean.txt missing: {script_clean_path}")

    source_script_name = str(tool_context.state.get("source_script_name", "")) or script_clean_path.stem
    artifacts = extract_asset_registry_from_text(
        source_script_name=source_script_name,
        script_text=script_clean_path.read_text(encoding="utf-8"),
        model_config=_load_text_config(),
        output_root=(PROJECT_ROOT / "runs").resolve(),
        run_dir=run_dir,
        source_path=DEFAULT_SOURCE_PATH if DEFAULT_SOURCE_PATH.exists() else None,
    )
    tool_context.state["asset_registry_path"] = str((artifacts.asset_dir / "asset_registry.json").resolve())
    return _completed(tool_context, "asset_extraction", run_dir)


def run_storyboard_seed_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Generate an early storyboard prompt seed in parallel with asset extraction."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "storyboard_seed")
    if run_dir is None:
        return _blocked(tool_context, "storyboard_seed", "No current_run_dir in workflow state.")
    script_clean_path = run_dir / "01_input" / "script_clean.txt"
    if not script_clean_path.exists():
        return _blocked(tool_context, "storyboard_seed", f"script_clean.txt missing: {script_clean_path}")

    source_script_name = str(tool_context.state.get("source_script_name", "")) or script_clean_path.stem
    output_path = _build_storyboard_seed(run_dir, source_script_name)
    tool_context.state["storyboard_seed_path"] = str(output_path.resolve())
    return _completed(tool_context, "storyboard_seed", run_dir)


def run_style_bible_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Generate the style bible for the current workflow run."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "style_bible")
    if run_dir is None:
        return _blocked(tool_context, "style_bible", "No current_run_dir in workflow state.")
    asset_registry_path = run_dir / "02_assets" / "asset_registry.json"
    if not asset_registry_path.exists():
        return _blocked(tool_context, "style_bible", f"asset_registry.json missing: {asset_registry_path}")

    artifacts = generate_style_bible(
        asset_registry_path=asset_registry_path,
        model_config=_load_text_config(),
    )
    tool_context.state["style_bible_path"] = str((artifacts.style_dir / "style_bible.json").resolve())
    return _completed(tool_context, "style_bible", run_dir)


def run_asset_prompt_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Generate asset image prompts for the current workflow run."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "asset_prompts")
    if run_dir is None:
        return _blocked(tool_context, "asset_prompts", "No current_run_dir in workflow state.")
    style_bible_path = run_dir / "03_style" / "style_bible.json"
    if not style_bible_path.exists():
        return _blocked(tool_context, "asset_prompts", f"style_bible.json missing: {style_bible_path}")

    artifacts = generate_asset_prompts(
        style_bible_path=style_bible_path,
        model_config=_load_text_config(),
    )
    tool_context.state["asset_prompts_path"] = str((artifacts.prompt_dir / "asset_prompts.json").resolve())
    return _completed(tool_context, "asset_prompts", run_dir)


def run_asset_image_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Generate labeled asset reference images for the current workflow run."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "asset_images")
    if run_dir is None:
        return _blocked(tool_context, "asset_images", "No current_run_dir in workflow state.")
    asset_prompts_path = run_dir / "04_asset_prompts" / "asset_prompts.json"
    if not asset_prompts_path.exists():
        return _blocked(tool_context, "asset_images", f"asset_prompts.json missing: {asset_prompts_path}")

    artifacts = generate_asset_images(
        asset_prompts_path=asset_prompts_path,
        model_config=_load_image_config(),
    )
    tool_context.state["asset_images_manifest_path"] = str((artifacts.image_dir / "asset_images_manifest.json").resolve())
    return _completed(tool_context, "asset_images", run_dir)


def run_storyboard_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Generate the grounded storyboard that drives the video workflow."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "storyboard")
    if run_dir is None:
        return _blocked(tool_context, "storyboard", "No current_run_dir in workflow state.")
    style_bible_path = run_dir / "03_style" / "style_bible.json"
    if not style_bible_path.exists():
        return _blocked(tool_context, "storyboard", f"style_bible.json missing: {style_bible_path}")

    artifacts = generate_storyboard(
        style_bible_path=style_bible_path,
        model_config=_load_text_config(),
    )
    tool_context.state["storyboard_path"] = str((artifacts.storyboard_dir / "storyboard.json").resolve())
    return _completed(tool_context, "storyboard", run_dir)


def run_shot_reference_board_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Render stitched shot reference boards from storyboard and asset images."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "shot_reference_boards")
    if run_dir is None:
        return _blocked(tool_context, "shot_reference_boards", "No current_run_dir in workflow state.")
    storyboard_path = run_dir / "06_storyboard" / "storyboard.json"
    if not storyboard_path.exists():
        return _blocked(tool_context, "shot_reference_boards", f"storyboard.json missing: {storyboard_path}")

    artifacts = generate_shot_reference_boards(storyboard_path=storyboard_path)
    tool_context.state["shot_reference_manifest_path"] = str((artifacts.board_dir / "shot_reference_manifest.json").resolve())
    return _completed(tool_context, "shot_reference_boards", run_dir)


def run_board_publish_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Publish stitched shot boards to TOS so they can be used as first_frame URLs."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "board_publish")
    if run_dir is None:
        return _blocked(tool_context, "board_publish", "No current_run_dir in workflow state.")
    manifest_path = run_dir / "07_shot_reference_boards" / "shot_reference_manifest.json"
    if not manifest_path.exists():
        return _blocked(tool_context, "board_publish", f"shot_reference_manifest.json missing: {manifest_path}")

    tos_env = _load_board_publish_env()
    if tos_env is not None:
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
                    return _blocked(tool_context, "board_publish", f"board image missing: {source_path}")
                object_key = _build_object_key(tos_env["key_prefix"], manifest.source_run, source_path.name)
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
        result_path = run_dir / "07_shot_reference_boards" / "board_publish_tos_result.json"
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
        tool_context.state["board_publish_result_path"] = str(result_path.resolve())
        return _completed(
            tool_context,
            "board_publish",
            run_dir,
            {
                "publish_strategy": "tos",
                "message": "Published shot reference boards through TOS.",
            },
        )

    try:
        jsdelivr_env = _load_jsdelivr_publish_env(PROJECT_ROOT)
    except Exception as exc:
        return _blocked(
            tool_context,
            "board_publish",
            "No BOARD_TOS_* envs found, and jsDelivr fallback could not infer a usable GitHub repo configuration. "
            f"Details: {exc}",
        )

    public_base_url = f"https://cdn.jsdelivr.net/gh/{jsdelivr_env['repo_slug']}@{jsdelivr_env['ref']}"
    publish_artifacts = publish_shot_reference_boards(
        manifest_path=manifest_path,
        public_base_url=public_base_url,
        publish_root_dir=Path(jsdelivr_env["publish_root_dir"]),
        url_prefix=jsdelivr_env["url_prefix"],
        output_manifest_path=None,
    )
    tool_context.state["board_publish_result_path"] = str(publish_artifacts.result_path.resolve())

    updated_manifest = ShotReferenceManifest.model_validate(read_json(manifest_path))
    sample_url = next((board.board_public_url for board in updated_manifest.boards if board.board_public_url), "")
    reachable, detail = _check_public_url_reachable(sample_url) if sample_url else (False, "No sample board_public_url found")
    if not reachable:
        return _blocked(
            tool_context,
            "board_publish",
            "Published shot boards into the local `static/` tree and wrote jsDelivr URLs into the manifest, "
            "but the public CDN URL is not reachable yet. Commit and push the generated `static/runs/...` files, "
            f"then resume the workflow. Sample URL check: {sample_url or 'N/A'} ({detail}).",
        )

    return _completed(
        tool_context,
        "board_publish",
        run_dir,
        {
            "publish_strategy": "jsdelivr",
            "public_base_url": public_base_url,
            "message": "Published shot reference boards through the GitHub + jsDelivr fallback path.",
        },
    )


def run_video_job_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Assemble shot video jobs after board publishing is available."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "video_jobs")
    if run_dir is None:
        return _blocked(tool_context, "video_jobs", "No current_run_dir in workflow state.")
    storyboard_path = run_dir / "06_storyboard" / "storyboard.json"
    if not storyboard_path.exists():
        return _blocked(tool_context, "video_jobs", f"storyboard.json missing: {storyboard_path}")

    artifacts = generate_video_jobs(
        storyboard_path=storyboard_path,
        model_config=_load_video_config(),
    )
    tool_context.state["video_jobs_path"] = str((artifacts.jobs_dir / "video_jobs.json").resolve())
    return _completed(tool_context, "video_jobs", run_dir)


def run_shot_video_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Generate shot videos from assembled video jobs."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "shot_videos")
    if run_dir is None:
        return _blocked(tool_context, "shot_videos", "No current_run_dir in workflow state.")
    video_jobs_path = run_dir / "08_video_jobs" / "video_jobs.json"
    if not video_jobs_path.exists():
        return _blocked(tool_context, "shot_videos", f"video_jobs.json missing: {video_jobs_path}")

    artifacts = generate_shot_videos(
        video_jobs_path=video_jobs_path,
        model_config=_load_video_config(),
        selected_shots=set(),
        resolution="720p",
        timeout_seconds=1800,
        poll_interval_seconds=10,
        keep_remote_media=False,
    )
    tool_context.state["shot_videos_manifest_path"] = str((artifacts.output_dir / "shot_videos_manifest.json").resolve())
    return _completed(tool_context, "shot_videos", run_dir)


def run_final_video_stage(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Concatenate succeeded shot videos into the final video."""

    assert tool_context is not None
    run_dir = _require_state_run_dir(tool_context, "final_video")
    if run_dir is None:
        return _blocked(tool_context, "final_video", "No current_run_dir in workflow state.")
    shot_videos_manifest_path = run_dir / "09_shot_videos" / "shot_videos_manifest.json"
    if not shot_videos_manifest_path.exists():
        return _blocked(tool_context, "final_video", f"shot_videos_manifest.json missing: {shot_videos_manifest_path}")

    artifacts = generate_final_video(
        shot_videos_manifest_path=shot_videos_manifest_path,
        trim_leading_seconds=DEFAULT_TRIM_LEADING_SECONDS,
        blackout_leading_seconds=DEFAULT_BLACKOUT_LEADING_SECONDS,
    )
    tool_context.state["final_video_path"] = str(artifacts.final_video_path)
    return _completed(tool_context, "final_video", run_dir)


def run_mainline_workflow(
    source_text: str = "",
    source_path: str = "",
    source_script_name: str = "",
    input_mode: Literal["auto", "keywords", "brief", "script"] = AUTO_INPUT_MODE,
    run_dir: str = "",
    tool_context: ToolContext | None = None,
) -> dict[str, Any]:
    """Run the project's mainline workflow end to end inside VeADK web."""

    assert tool_context is not None

    start_result = start_or_resume_workflow(
        source_text=source_text,
        source_path=source_path,
        source_script_name=source_script_name,
        input_mode=input_mode,
        run_dir=run_dir,
        tool_context=tool_context,
    )
    if start_result.get("status") != "ok":
        return start_result

    current_run_dir = _resolve_run_dir(tool_context)
    if current_run_dir is None:
        return _blocked(tool_context, "run_mainline_workflow", "Workflow state lost current_run_dir after startup.")

    script_clean_path = current_run_dir / "01_input" / "script_clean.txt"
    if not script_clean_path.exists():
        return _blocked(
            tool_context,
            "run_mainline_workflow",
            "Upstream routing did not produce script_clean.txt. Check whether the router stopped for confirmation.",
        )

    effective_source_script_name = str(tool_context.state.get("source_script_name", "")) or script_clean_path.stem

    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            asset_future = executor.submit(
                extract_asset_registry_from_text,
                source_script_name=effective_source_script_name,
                script_text=script_clean_path.read_text(encoding="utf-8"),
                model_config=_load_text_config(),
                output_root=(PROJECT_ROOT / "runs").resolve(),
                run_dir=current_run_dir,
                source_path=DEFAULT_SOURCE_PATH if DEFAULT_SOURCE_PATH.exists() else None,
            )
            storyboard_seed_future = executor.submit(
                _build_storyboard_seed,
                current_run_dir,
                effective_source_script_name,
            )

            asset_artifacts = asset_future.result()
            storyboard_seed_path = storyboard_seed_future.result()

        tool_context.state["asset_registry_path"] = str((asset_artifacts.asset_dir / "asset_registry.json").resolve())
        tool_context.state["storyboard_seed_path"] = str(storyboard_seed_path.resolve())
        _set_stage(tool_context, "parallel_planning_done")
    except Exception as exc:
        return _blocked(tool_context, "parallel_planning", str(exc))

    for stage_func in (
        run_style_bible_stage,
        run_asset_prompt_stage,
        run_asset_image_stage,
        run_storyboard_stage,
        run_shot_reference_board_stage,
        run_board_publish_stage,
        run_video_job_stage,
        run_shot_video_stage,
        run_final_video_stage,
    ):
        result = stage_func(tool_context=tool_context)
        if result.get("status") != "ok":
            return {
                "status": "partial",
                "completed_through": tool_context.state.get("current_stage", ""),
                "last_result": result,
                "run_dir": str(current_run_dir),
                "artifacts": _artifact_snapshot(current_run_dir),
            }

    return {
        "status": "ok",
        "stage": "mainline_workflow_completed",
        "run_dir": str(current_run_dir),
        "artifacts": _artifact_snapshot(current_run_dir),
        "workflow_history": list(tool_context.state.get("workflow_history", [])),
    }


def inspect_current_run(tool_context: ToolContext | None = None) -> dict[str, Any]:
    """Inspect the current workflow run state and artifact paths."""

    assert tool_context is not None
    run_dir = _resolve_run_dir(tool_context)
    if run_dir is None:
        return {"status": "idle", "message": "No workflow run has been started in this session yet."}
    return {
        "status": "ok",
        "current_stage": tool_context.state.get("current_stage", ""),
        "workflow_history": list(tool_context.state.get("workflow_history", [])),
        "run_dir": str(run_dir),
        "artifacts": _artifact_snapshot(run_dir),
    }
