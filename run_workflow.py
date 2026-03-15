#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path, PurePosixPath
from typing import Iterable

import httpx
from tos import TosClientV2
from tos.enum import HttpMethodType

from app.workflow_service import WorkflowService
from pipeline.asset_extraction import extract_asset_registry_from_text
from pipeline.asset_images import generate_asset_images
from pipeline.asset_prompts import generate_asset_prompts
from pipeline.final_video import (
    DEFAULT_BLACKOUT_LEADING_SECONDS,
    DEFAULT_TRIM_LEADING_SECONDS,
    generate_final_video,
)
from pipeline.intent_to_script import AUTO_INPUT_MODE, generate_script_from_intent
from pipeline.io import read_json, write_json
from pipeline.runtime import (
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


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "agentkit.local.yaml"
DEFAULT_ENV_PATH = PROJECT_ROOT / "ai_studio_flow" / ".env"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "runs"
STAGE_ORDER = (
    "upstream",
    "asset_extraction",
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


class WorkflowBlockedError(RuntimeError):
    def __init__(self, stage: str, message: str):
        super().__init__(message)
        self.stage = stage
        self.message = message


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the local script-to-video workflow from a fresh input or resume an existing run directory."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--input", help="Path to a text file containing keywords, a brief, or a full script.")
    source_group.add_argument("--text", help="Inline keywords, brief, or full script text.")
    source_group.add_argument("--run-dir", help="Resume an existing run directory instead of creating a new runN.")
    parser.add_argument(
        "--input-mode",
        choices=("auto", "keywords", "brief", "script"),
        default=AUTO_INPUT_MODE,
        help="How to interpret the source input. Defaults to auto detection.",
    )
    parser.add_argument(
        "--source-name",
        default="",
        help="Optional logical source script name. Defaults to the input file stem or `intent_input`.",
    )
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_PATH),
        help="Path to the local AgentKit config file.",
    )
    parser.add_argument(
        "--env-file",
        default=str(DEFAULT_ENV_PATH),
        help="Optional .env file to load before board publishing. Default: ai_studio_flow/.env",
    )
    parser.add_argument(
        "--output-root",
        default=str(DEFAULT_OUTPUT_ROOT),
        help="Directory for generated run artifacts when starting a new workflow.",
    )
    parser.add_argument(
        "--publish-strategy",
        choices=("auto", "tos", "jsdelivr"),
        default="auto",
        help="How to publish shot reference boards. `auto` tries TOS first, then GitHub + jsDelivr.",
    )
    parser.add_argument(
        "--target-repo-root",
        default="",
        help="Local checkout root for jsDelivr publishing. Defaults to the current project root.",
    )
    parser.add_argument(
        "--stop-after",
        choices=STAGE_ORDER,
        default="",
        help="Optionally stop after the named stage.",
    )
    parser.add_argument(
        "--shots",
        default="",
        help="Optional comma-separated shot IDs for the shot-video stage, for example: shot_001,shot_002",
    )
    parser.add_argument(
        "--resolution",
        default="720p",
        help="Video resolution for shot generation. Default: 720p",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=int,
        default=1800,
        help="Max seconds to wait for each shot video task. Default: 1800",
    )
    parser.add_argument(
        "--poll-interval-seconds",
        type=int,
        default=10,
        help="Seconds between video task polling. Default: 10",
    )
    parser.add_argument(
        "--keep-remote-media",
        action="store_true",
        help="Do not download remote video files locally in the shot-video stage.",
    )
    parser.add_argument(
        "--trim-leading-seconds",
        type=float,
        default=DEFAULT_TRIM_LEADING_SECONDS,
        help=f"Seconds to trim from the start of every shot before concat. Default: {DEFAULT_TRIM_LEADING_SECONDS}",
    )
    parser.add_argument(
        "--blackout-leading-seconds",
        type=float,
        default=DEFAULT_BLACKOUT_LEADING_SECONDS,
        help=(
            "Seconds to force to pure black at the start of every trimmed shot before concat. "
            f"Default: {DEFAULT_BLACKOUT_LEADING_SECONDS}"
        ),
    )
    return parser.parse_args()


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


def run_git(args: list[str], repo_root: Path) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def infer_repo_slug(repo_root: Path) -> str:
    remote_url = run_git(["config", "--get", "remote.origin.url"], repo_root)
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


def infer_git_ref(repo_root: Path) -> str:
    branch = run_git(["branch", "--show-current"], repo_root)
    if branch:
        return branch
    raise ValueError(f"Cannot infer current branch for target repo: {repo_root}")


def build_object_key(key_prefix: str, source_run: str, filename: str) -> str:
    parts = [part for part in key_prefix.split("/") if part]
    parts.extend(["runs", source_run, "07_shot_reference_boards", "boards", filename])
    return PurePosixPath(*parts).as_posix()


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


def load_jsdelivr_env(target_repo_root: Path) -> dict[str, str]:
    repo_slug = os.getenv("BOARD_JSDELIVR_REPO_SLUG", "").strip() or infer_repo_slug(target_repo_root)
    ref = os.getenv("BOARD_JSDELIVR_REF", "").strip() or infer_git_ref(target_repo_root)
    url_prefix = os.getenv("BOARD_JSDELIVR_URL_PREFIX", "static").strip() or "static"
    publish_root_dir = os.getenv("BOARD_JSDELIVR_PUBLISH_ROOT", "").strip()
    resolved_publish_root = Path(publish_root_dir).resolve() if publish_root_dir else target_repo_root.resolve()
    return {
        "repo_slug": repo_slug,
        "ref": ref,
        "url_prefix": url_prefix,
        "publish_root_dir": str(resolved_publish_root),
    }


def check_public_url_reachable(url: str) -> tuple[bool, str]:
    try:
        with httpx.Client(follow_redirects=True, timeout=10.0) as client:
            response = client.head(url)
            if response.status_code == 405:
                response = client.get(url)
            return response.status_code == 200, f"HTTP {response.status_code}"
    except Exception as exc:
        return False, str(exc)


def first_nonempty(values: Iterable[str]) -> str:
    for value in values:
        if value:
            return value
    return ""


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


def ensure_stop(stage: str, stop_after: str, run_dir: Path) -> None:
    if stop_after == stage:
        print(f"[stop] Stage `{stage}` completed for {run_dir}")
        raise SystemExit(0)


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
    *,
    run_dir: Path,
    text_config,
    output_root: Path,
    input_mode: str,
) -> str:
    script_clean_path = run_dir / "01_input" / "script_clean.txt"
    if script_clean_path.exists():
        return load_source_script_name(run_dir)

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
        model_config=text_config,
        output_root=output_root,
        run_dir=run_dir,
        source_path=source_path,
        input_mode=recovery_input_mode,
        extract_assets=False,
    )
    return source_script_name


def has_reachable_board_urls(manifest_path: Path) -> tuple[bool, str]:
    manifest = ShotReferenceManifest.model_validate(read_json(manifest_path))
    sample_url = first_nonempty(board.board_public_url for board in manifest.boards)
    if not sample_url:
        return False, "board_public_url is still empty in shot_reference_manifest.json"
    return check_public_url_reachable(sample_url)


def publish_boards_with_tos(manifest_path: Path, tos_env: dict[str, str]) -> Path:
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
            object_key = build_object_key(tos_env["key_prefix"], manifest.source_run, source_path.name)
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


def publish_boards_auto(manifest_path: Path, publish_strategy: str, target_repo_root: Path) -> tuple[str, Path]:
    tos_env = load_board_tos_env()
    if publish_strategy in {"auto", "tos"} and tos_env is not None:
        result_path = publish_boards_with_tos(manifest_path, tos_env)
        return "tos", result_path

    if publish_strategy == "tos":
        raise WorkflowBlockedError(
            "board_publish",
            "Publish strategy was forced to `tos`, but BOARD_TOS_* variables are not configured.",
        )

    jsdelivr_env = load_jsdelivr_env(target_repo_root)
    public_base_url = f"https://cdn.jsdelivr.net/gh/{jsdelivr_env['repo_slug']}@{jsdelivr_env['ref']}"
    artifacts = publish_shot_reference_boards(
        manifest_path=manifest_path,
        public_base_url=public_base_url,
        publish_root_dir=Path(jsdelivr_env["publish_root_dir"]),
        url_prefix=jsdelivr_env["url_prefix"],
        output_manifest_path=None,
    )
    reachable, detail = has_reachable_board_urls(manifest_path)
    if not reachable:
        static_dir = target_repo_root / "static" / "runs" / manifest_path.parent.parent.name
        raise WorkflowBlockedError(
            "board_publish",
            "Published local board files and wrote jsDelivr URLs into the manifest, but the public CDN URL is not "
            f"reachable yet ({detail}). Commit and push {static_dir}, then rerun with --run-dir {manifest_path.parent.parent}.",
        )
    return "jsdelivr", artifacts.result_path


def main() -> int:
    args = parse_args()
    service = WorkflowService(
        config_path=Path(args.config).resolve(),
        output_root=Path(args.output_root).resolve(),
        target_repo_root=Path(args.target_repo_root).resolve() if args.target_repo_root else PROJECT_ROOT.resolve(),
        env_file=Path(args.env_file).resolve(),
    )

    start_result = service.start_or_resume(
        source_text=args.text or "",
        source_path=args.input or "",
        source_script_name=args.source_name.strip(),
        input_mode=args.input_mode,
        run_dir=args.run_dir or "",
    )
    start_status = str(start_result.get("status", ""))
    if start_status != "ok":
        message = str(start_result.get("reason") or start_result.get("message") or "unknown workflow error")
        prefix = "blocked" if start_status == "blocked" else "failed"
        print(f"[{prefix}] upstream: {message}", file=sys.stderr)
        return 2 if start_status == "blocked" else 1

    run_dir = Path(str(start_result["run_dir"])).resolve()
    source_script_name = str(start_result.get("source_script_name", "")).strip() or service.load_source_script_name(run_dir)
    if args.run_dir:
        print(f"[resume] {run_dir}")
    print(f"[ok] upstream -> {run_dir}")
    ensure_stop("upstream", args.stop_after, run_dir)

    artifact_keys = {
        "asset_extraction": "asset_registry_path",
        "style_bible": "style_bible_path",
        "asset_prompts": "asset_prompts_path",
        "asset_images": "asset_images_manifest_path",
        "storyboard": "storyboard_path",
        "shot_reference_boards": "shot_reference_manifest_path",
        "board_publish": "board_publish_result_path",
        "video_jobs": "video_jobs_path",
        "shot_videos": "shot_videos_manifest_path",
        "final_video": "final_video_path",
    }

    selected_shots = set(filter(None, (part.strip() for part in args.shots.split(","))))
    for stage in STAGE_ORDER[1:]:
        result = service.run_stage(
            stage,  # type: ignore[arg-type]
            run_dir=run_dir,
            source_script_name=source_script_name,
            publish_strategy=args.publish_strategy,
            selected_shots=selected_shots,
            resolution=args.resolution,
            timeout_seconds=args.timeout_seconds,
            poll_interval_seconds=args.poll_interval_seconds,
            keep_remote_media=args.keep_remote_media,
            trim_leading_seconds=args.trim_leading_seconds,
            blackout_leading_seconds=args.blackout_leading_seconds,
        )
        status = str(result.get("status", ""))
        if status != "ok":
            message = str(result.get("reason") or result.get("message") or "unknown workflow error")
            prefix = "blocked" if status == "blocked" else "failed"
            print(f"[{prefix}] {stage}: {message}", file=sys.stderr)
            return 2 if status == "blocked" else 1

        artifact_path = str(result.get("artifacts", {}).get(artifact_keys[stage], "")).strip()
        message = str(result.get("message", "")).strip()
        log_prefix = "[skip]" if message.startswith("Reused existing") or message.startswith("Reused existing public") else "[ok]"
        if artifact_path:
            print(f"{log_prefix} {stage} -> {artifact_path}")
        else:
            print(f"{log_prefix} {stage} -> {message or 'completed'}")
        ensure_stop(stage, args.stop_after, run_dir)

    print(f"[done] workflow completed for {run_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
