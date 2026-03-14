"""Runtime configuration helpers for local workflow nodes."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml
from volcenginesdkarkruntime import Ark


DEFAULT_BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
PLACEHOLDER_PREFIXES = ("your_", "<", "REPLACE_", "TODO")


@dataclass(frozen=True, slots=True)
class TextModelConfig:
    model_name: str
    api_key: str
    base_url: str = DEFAULT_BASE_URL


@dataclass(frozen=True, slots=True)
class ImageModelConfig:
    model_name: str
    api_key: str
    base_url: str = DEFAULT_BASE_URL


@dataclass(frozen=True, slots=True)
class VideoModelConfig:
    model_name: str
    api_key: str
    base_url: str = DEFAULT_BASE_URL


def load_runtime_envs(config_path: Path) -> dict[str, str]:
    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    envs = raw.get("common", {}).get("runtime_envs", {}) or {}
    if not isinstance(envs, dict):
        raise ValueError(f"`common.runtime_envs` is invalid in {config_path}")
    return {str(key): str(value).strip() for key, value in envs.items()}


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
        raise ValueError(f"{key} is missing or still a placeholder in agentkit.local.yaml")
    return value.strip()


def load_text_model_config(config_path: Path) -> TextModelConfig:
    envs = load_runtime_envs(config_path)
    model_name = require_env(envs, "MODEL_AGENT_NAME")
    api_key = require_env(envs, "MODEL_AGENT_API_KEY")
    base_url = envs.get("MODEL_AGENT_API_BASE", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    return TextModelConfig(model_name=model_name, api_key=api_key, base_url=base_url)


def build_text_client(config: TextModelConfig) -> Ark:
    return Ark(api_key=config.api_key, base_url=config.base_url)


def load_image_model_config(config_path: Path) -> ImageModelConfig:
    envs = load_runtime_envs(config_path)
    model_name = require_env(envs, "MODEL_IMAGE_NAME")
    api_key = require_env(envs, "MODEL_IMAGE_API_KEY")
    base_url = envs.get("MODEL_IMAGE_API_BASE", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    return ImageModelConfig(model_name=model_name, api_key=api_key, base_url=base_url)


def build_image_client(config: ImageModelConfig) -> Ark:
    return Ark(api_key=config.api_key, base_url=config.base_url)


def load_video_model_config(config_path: Path) -> VideoModelConfig:
    envs = load_runtime_envs(config_path)
    model_name = require_env(envs, "MODEL_VIDEO_NAME")
    api_key = require_env(envs, "MODEL_VIDEO_API_KEY")
    base_url = envs.get("MODEL_VIDEO_API_BASE", DEFAULT_BASE_URL).strip() or DEFAULT_BASE_URL
    return VideoModelConfig(model_name=model_name, api_key=api_key, base_url=base_url)


def build_video_client(config: VideoModelConfig) -> Ark:
    return Ark(api_key=config.api_key, base_url=config.base_url)
