#!/usr/bin/env python3

import argparse
import base64
import json
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import httpx
import yaml
from volcenginesdkarkruntime import Ark


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_TEXT_PROMPT = "请用两句话介绍一下火山引擎方舟，并明确写出“文本模型调用成功”。"
DEFAULT_IMAGE_PROMPT = (
    "生成一张测试图片：一只橙色小猫坐在蓝色沙发上，光线柔和，构图简洁，插画风格。"
)
DEFAULT_VIDEO_PROMPT = (
    "A 5-second cinematic shot of a small orange cat sitting on a blue sofa, "
    "gentle motion, realistic lighting."
)
PLACEHOLDER_PREFIXES = ("your_", "<", "REPLACE_", "TODO")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Smoke test Volcengine text/image/video models from agentkit.local.yaml."
    )
    parser.add_argument(
        "--config",
        default="agentkit.local.yaml",
        help="Path to AgentKit config file. Default: agentkit.local.yaml",
    )
    parser.add_argument(
        "--only",
        choices=["all", "text", "image", "video"],
        default="all",
        help="Run only one modality, or all.",
    )
    parser.add_argument(
        "--output-dir",
        default="test_outputs",
        help="Directory for saved test results. Default: test_outputs",
    )
    parser.add_argument(
        "--text-prompt",
        default=DEFAULT_TEXT_PROMPT,
        help="Prompt for text-model smoke test.",
    )
    parser.add_argument(
        "--image-prompt",
        default=DEFAULT_IMAGE_PROMPT,
        help="Prompt for image-model smoke test.",
    )
    parser.add_argument(
        "--video-prompt",
        default=DEFAULT_VIDEO_PROMPT,
        help="Prompt for video-model smoke test.",
    )
    parser.add_argument(
        "--video-timeout",
        type=int,
        default=900,
        help="Max seconds to wait for video generation. Default: 900",
    )
    parser.add_argument(
        "--poll-interval",
        type=int,
        default=10,
        help="Seconds between video task polling. Default: 10",
    )
    parser.add_argument(
        "--keep-remote-media",
        action="store_true",
        help="Do not download returned image/video files, only keep URLs and metadata.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate config only, do not send remote requests.",
    )
    return parser.parse_args()


def load_runtime_envs(config_path: Path) -> dict[str, str]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    envs = raw.get("common", {}).get("runtime_envs", {}) or {}
    if not isinstance(envs, dict):
        raise ValueError(f"`common.runtime_envs` is invalid in {config_path}")
    return {str(k): str(v) for k, v in envs.items()}


def is_placeholder(value: str | None) -> bool:
    if value is None:
        return True
    stripped = value.strip()
    if not stripped:
        return True
    return any(stripped.startswith(prefix) for prefix in PLACEHOLDER_PREFIXES)


def require_env(envs: dict[str, str], key: str) -> str:
    value = envs.get(key)
    if is_placeholder(value):
        raise ValueError(
            f"{key} is missing or still a placeholder. Save the real value in agentkit.local.yaml first."
        )
    return value.strip()


def optional_env(envs: dict[str, str], key: str, default: str) -> str:
    value = envs.get(key)
    if is_placeholder(value):
        return default
    return value.strip()


def mask_secret(value: str) -> str:
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}...{value[-4:]}"


def ensure_output_dir(base_dir: Path) -> Path:
    run_dir = base_dir / time.strftime("%Y%m%d-%H%M%S")
    run_dir.mkdir(parents=True, exist_ok=True)
    return run_dir


def write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part.strip())
    return str(content)


def infer_suffix_from_url(url: str, default: str) -> str:
    path = urlparse(url).path
    suffix = Path(path).suffix
    return suffix or default


def download_file(url: str, dest: Path) -> None:
    with httpx.Client(timeout=300.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()
        dest.write_bytes(response.content)


def build_client(api_key: str, base_url: str) -> Ark:
    return Ark(api_key=api_key, base_url=base_url)


def test_text(envs: dict[str, str], run_dir: Path, prompt: str) -> dict[str, Any]:
    model = require_env(envs, "MODEL_AGENT_NAME")
    api_key = require_env(envs, "MODEL_AGENT_API_KEY")
    base_url = optional_env(envs, "MODEL_AGENT_API_BASE", DEFAULT_BASE_URL)

    client = build_client(api_key=api_key, base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a concise assistant."},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=256,
    )

    content = extract_text_content(response.choices[0].message.content)
    if not content.strip():
        raise RuntimeError("Text model returned empty content.")

    text_path = run_dir / "text_result.txt"
    raw_path = run_dir / "text_response.json"
    text_path.write_text(content, encoding="utf-8")
    write_json(raw_path, dump_model(response))

    print(f"[text] success | model={model} | output={text_path}")
    return {
        "status": "success",
        "model": model,
        "base_url": base_url,
        "output_text_file": str(text_path),
        "raw_response_file": str(raw_path),
    }


def test_image(
    envs: dict[str, str],
    run_dir: Path,
    prompt: str,
    keep_remote_media: bool,
) -> dict[str, Any]:
    model = require_env(envs, "MODEL_IMAGE_NAME")
    api_key = require_env(envs, "MODEL_IMAGE_API_KEY")
    base_url = optional_env(envs, "MODEL_IMAGE_API_BASE", DEFAULT_BASE_URL)

    client = build_client(api_key=api_key, base_url=base_url)
    try:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            response_format="b64_json",
            size="1024x1024",
            output_format="png",
            watermark=False,
            timeout=300.0,
        )
    except Exception:
        response = client.images.generate(
            model=model,
            prompt=prompt,
            response_format="url",
            size="1024x1024",
            watermark=False,
            timeout=300.0,
        )

    if not response.data:
        raise RuntimeError("Image model returned no image data.")

    image_item = response.data[0]
    image_path: Path | None = None
    image_url = getattr(image_item, "url", None)
    image_b64 = getattr(image_item, "b64_json", None)

    if image_b64:
        image_path = run_dir / "image_result.png"
        image_path.write_bytes(base64.b64decode(image_b64))
    elif image_url and not keep_remote_media:
        image_path = run_dir / f"image_result{infer_suffix_from_url(image_url, '.png')}"
        download_file(image_url, image_path)

    raw_path = run_dir / "image_response.json"
    write_json(raw_path, dump_model(response))

    print(
        f"[image] success | model={model} | saved={image_path if image_path else 'remote-url-only'}"
    )
    return {
        "status": "success",
        "model": model,
        "base_url": base_url,
        "image_file": str(image_path) if image_path else None,
        "image_url": image_url,
        "raw_response_file": str(raw_path),
    }


def test_video(
    envs: dict[str, str],
    run_dir: Path,
    prompt: str,
    timeout_seconds: int,
    poll_interval: int,
    keep_remote_media: bool,
) -> dict[str, Any]:
    model = require_env(envs, "MODEL_VIDEO_NAME")
    api_key = require_env(envs, "MODEL_VIDEO_API_KEY")
    base_url = optional_env(envs, "MODEL_VIDEO_API_BASE", DEFAULT_BASE_URL)

    client = build_client(api_key=api_key, base_url=base_url)
    created = client.content_generation.tasks.create(
        model=model,
        content=[{"type": "text", "text": prompt}],
        duration=5,
        resolution="720p",
        ratio="16:9",
        watermark=False,
        timeout=300.0,
    )
    task_id = created.id
    created_path = run_dir / "video_task_created.json"
    write_json(created_path, dump_model(created))
    print(f"[video] task submitted | model={model} | task_id={task_id}")

    deadline = time.time() + timeout_seconds
    latest = None
    while time.time() < deadline:
        latest = client.content_generation.tasks.get(task_id=task_id, timeout=300.0)
        status = getattr(latest, "status", "unknown")
        print(f"[video] polling | task_id={task_id} | status={status}")

        if status == "succeeded":
            break
        if status in {"failed", "cancelled"}:
            error = getattr(latest, "error", None)
            error_payload = dump_model(error) if error else None
            raise RuntimeError(
                f"Video task {task_id} ended with status={status}, error={error_payload}"
            )
        time.sleep(poll_interval)

    if latest is None:
        raise RuntimeError("Video task polling did not start.")

    if getattr(latest, "status", None) != "succeeded":
        raw_path = run_dir / "video_task_timeout.json"
        write_json(raw_path, dump_model(latest))
        raise TimeoutError(
            f"Video task {task_id} did not finish within {timeout_seconds}s. "
            f"Latest status: {getattr(latest, 'status', 'unknown')}. "
            f"See {raw_path}."
        )

    content = getattr(latest, "content", None)
    video_url = getattr(content, "video_url", None) if content else None
    file_url = getattr(content, "file_url", None) if content else None
    target_url = video_url or file_url

    video_path: Path | None = None
    if target_url and not keep_remote_media:
        video_path = run_dir / f"video_result{infer_suffix_from_url(target_url, '.mp4')}"
        download_file(target_url, video_path)

    raw_path = run_dir / "video_task_result.json"
    write_json(raw_path, dump_model(latest))

    print(
        f"[video] success | model={model} | task_id={task_id} | saved={video_path if video_path else 'remote-url-only'}"
    )
    return {
        "status": "success",
        "model": model,
        "base_url": base_url,
        "task_id": task_id,
        "video_file": str(video_path) if video_path else None,
        "video_url": video_url,
        "file_url": file_url,
        "raw_response_file": str(raw_path),
    }


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).resolve()
    if not config_path.exists():
        print(f"Config file not found: {config_path}", file=sys.stderr)
        return 2

    envs = load_runtime_envs(config_path)
    output_root = ensure_output_dir(Path(args.output_dir).resolve())

    print(f"Config: {config_path}")
    print(f"Output: {output_root}")
    print(
        "Loaded keys: "
        f"text={mask_secret(envs.get('MODEL_AGENT_API_KEY', ''))} "
        f"image={mask_secret(envs.get('MODEL_IMAGE_API_KEY', ''))} "
        f"video={mask_secret(envs.get('MODEL_VIDEO_API_KEY', ''))}"
    )

    if args.dry_run:
        try:
            require_env(envs, "MODEL_AGENT_NAME")
            require_env(envs, "MODEL_AGENT_API_KEY")
            require_env(envs, "MODEL_IMAGE_NAME")
            require_env(envs, "MODEL_IMAGE_API_KEY")
            require_env(envs, "MODEL_VIDEO_NAME")
            require_env(envs, "MODEL_VIDEO_API_KEY")
        except Exception as exc:
            print(f"Dry-run validation failed: {exc}", file=sys.stderr)
            return 1
        print("Dry-run validation passed.")
        return 0

    results: dict[str, Any] = {"config": str(config_path), "output_dir": str(output_root)}
    failures: list[tuple[str, str]] = []

    tests = ["text", "image", "video"] if args.only == "all" else [args.only]
    for test_name in tests:
        try:
            if test_name == "text":
                results["text"] = test_text(envs, output_root, args.text_prompt)
            elif test_name == "image":
                results["image"] = test_image(
                    envs, output_root, args.image_prompt, args.keep_remote_media
                )
            elif test_name == "video":
                results["video"] = test_video(
                    envs,
                    output_root,
                    args.video_prompt,
                    args.video_timeout,
                    args.poll_interval,
                    args.keep_remote_media,
                )
        except Exception as exc:
            failures.append((test_name, str(exc)))
            results[test_name] = {"status": "failed", "error": str(exc)}
            print(f"[{test_name}] failed | {exc}", file=sys.stderr)

    summary_path = output_root / "summary.json"
    write_json(summary_path, results)
    print(f"Summary: {summary_path}")

    if failures:
        for name, reason in failures:
            print(f"FAILED: {name}: {reason}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
