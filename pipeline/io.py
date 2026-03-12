"""Shared IO helpers for workflow pipeline nodes."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


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


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))
