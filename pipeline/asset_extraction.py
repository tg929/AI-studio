"""Script preprocessing and asset extraction node."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from volcenginesdkarkruntime._exceptions import ArkBadRequestError

from prompts.asset_extraction import (
    ASSET_EXTRACTION_SYSTEM_PROMPT,
    build_asset_extraction_user_prompt,
)
from schemas.asset_registry import AssetRegistry
from pipeline.io import dump_model, extract_text_content, write_json
from pipeline.runtime import TextModelConfig, build_text_client


@dataclass(frozen=True, slots=True)
class AssetExtractionArtifacts:
    run_dir: Path
    input_dir: Path
    asset_dir: Path


def normalize_script_text(raw_text: str) -> str:
    unified = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    paragraphs = []
    for block in unified.split("\n\n"):
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if lines:
            paragraphs.append("\n".join(lines))
    return "\n\n".join(paragraphs).strip()


def resolve_next_run_dir(output_root: Path) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    existing_indexes = []
    for child in output_root.iterdir():
        if not child.is_dir():
            continue
        name = child.name
        if not name.startswith("run"):
            continue
        suffix = name[3:]
        if suffix.isdigit():
            existing_indexes.append(int(suffix))
    next_index = max(existing_indexes, default=-1) + 1
    return output_root / f"run{next_index}"


def build_run_artifacts(output_root: Path) -> AssetExtractionArtifacts:
    run_dir = resolve_next_run_dir(output_root)
    input_dir = run_dir / "01_input"
    asset_dir = run_dir / "02_assets"
    input_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    return AssetExtractionArtifacts(run_dir=run_dir, input_dir=input_dir, asset_dir=asset_dir)


def build_existing_run_artifacts(run_dir: Path) -> AssetExtractionArtifacts:
    input_dir = run_dir / "01_input"
    asset_dir = run_dir / "02_assets"
    input_dir.mkdir(parents=True, exist_ok=True)
    asset_dir.mkdir(parents=True, exist_ok=True)
    return AssetExtractionArtifacts(run_dir=run_dir, input_dir=input_dir, asset_dir=asset_dir)


def normalize_asset_registry_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    if normalized.get("schema_version") == "1.0.0":
        normalized["schema_version"] = "1.0"

    genre = normalized.get("genre")
    if isinstance(genre, list):
        normalized["genre"] = " / ".join(str(item).strip() for item in genre if str(item).strip())

    story_meta = normalized.get("story_meta")
    if isinstance(story_meta, dict) and "era" not in story_meta and "era_background" in story_meta:
        story_meta = dict(story_meta)
        story_meta["era"] = story_meta.pop("era_background")
        normalized["story_meta"] = story_meta

    for character in normalized.get("characters", []):
        age = character.get("age")
        if isinstance(age, int | float):
            character["age"] = str(age)
        identity_markers = character.get("identity_markers")
        if isinstance(identity_markers, str):
            marker = identity_markers.strip()
            character["identity_markers"] = [marker] if marker else []
        relationships = character.get("relationship_targets")
        if not isinstance(relationships, list):
            relationships = []
            character["relationship_targets"] = relationships
        for relationship in relationships:
            if "character_id" not in relationship and "target_id" in relationship:
                relationship["character_id"] = relationship.pop("target_id")
            if "description" not in relationship:
                relationship["description"] = relationship.get("relation", "")

        visual_profile = character.get("visual_profile")
        if not isinstance(visual_profile, dict):
            visual_profile = {}
            character["visual_profile"] = visual_profile
        silhouette_keywords = visual_profile.get("silhouette_keywords")
        if isinstance(silhouette_keywords, str):
            keyword = silhouette_keywords.strip()
            visual_profile["silhouette_keywords"] = [keyword] if keyword else []

        costume_profile = character.get("costume_profile")
        if not isinstance(costume_profile, dict):
            costume_profile = {}
            character["costume_profile"] = costume_profile
        for list_key in ("secondary_colors", "trim_details", "accessories"):
            value = costume_profile.get(list_key)
            if isinstance(value, str):
                item = value.strip()
                costume_profile[list_key] = [item] if item else []

        visual_identity_lock = character.get("visual_identity_lock")
        if not isinstance(visual_identity_lock, dict):
            visual_identity_lock = {}
            character["visual_identity_lock"] = visual_identity_lock
        for list_key in ("required_features", "forbidden_drifts"):
            value = visual_identity_lock.get(list_key)
            if isinstance(value, str):
                item = value.strip()
                visual_identity_lock[list_key] = [item] if item else []

    return normalized


def extract_first_json_object(raw_text: str) -> str:
    text = raw_text.strip()
    if not text:
        raise ValueError("Empty response content")

    start = text.find("{")
    if start < 0:
        raise ValueError("Response does not contain a JSON object")

    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    raise ValueError("Response JSON object is truncated")


def parse_asset_registry_response(raw_text: str) -> dict[str, Any]:
    text = raw_text.strip()
    if not text:
        raise ValueError("Empty response content")
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return json.loads(extract_first_json_object(text))


def is_unsupported_json_response_format_error(error: Exception) -> bool:
    if not isinstance(error, ArkBadRequestError):
        return False
    body = getattr(error, "body", None)
    if isinstance(body, dict):
        error_payload = body.get("error", {})
        if isinstance(error_payload, dict):
            param = str(error_payload.get("param", ""))
            message = str(error_payload.get("message", ""))
            if param == "response_format.type" and "json_object" in message and "not supported" in message:
                return True
    message = str(error)
    return "response_format.type" in message and "json_object" in message and "not supported" in message


def create_script_clean_payload(
    *,
    source_script_name: str,
    normalized_text: str,
    source_path: Path | None = None,
) -> dict[str, Any]:
    paragraphs = normalized_text.split("\n\n") if normalized_text else []
    return {
        "source_path": str(source_path.resolve()) if source_path is not None else "",
        "source_script_name": source_script_name,
        "character_count": len(normalized_text),
        "paragraph_count": len(paragraphs),
        "text": normalized_text,
    }


def extract_asset_registry_from_text(
    *,
    source_script_name: str,
    script_text: str,
    model_config: TextModelConfig,
    output_root: Path,
    run_dir: Path | None = None,
    dry_run: bool = False,
    source_path: Path | None = None,
) -> AssetExtractionArtifacts:
    normalized_text = normalize_script_text(script_text)
    if not normalized_text:
        raise ValueError("Script text is empty after normalization")

    artifacts = build_existing_run_artifacts(run_dir) if run_dir is not None else build_run_artifacts(output_root)
    script_clean_payload = create_script_clean_payload(
        source_script_name=source_script_name,
        normalized_text=normalized_text,
        source_path=source_path,
    )
    script_clean_text_path = artifacts.input_dir / "script_clean.txt"
    script_clean_json_path = artifacts.input_dir / "script_clean.json"
    script_clean_text_path.write_text(normalized_text, encoding="utf-8")
    write_json(script_clean_json_path, script_clean_payload)

    user_prompt = build_asset_extraction_user_prompt(source_script_name, normalized_text)
    request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": ASSET_EXTRACTION_SYSTEM_PROMPT,
        "user_prompt": user_prompt,
        "source_script_name": source_script_name,
    }
    request_path = artifacts.asset_dir / "asset_extraction_request.json"
    write_json(request_path, request_payload)

    if dry_run:
        return artifacts

    client = build_text_client(model_config)
    response_path = artifacts.asset_dir / "asset_extraction_response.json"
    retry_request_path = artifacts.asset_dir / "asset_extraction_retry_request.json"
    retry_response_path = artifacts.asset_dir / "asset_extraction_retry_response.json"

    messages = [
        {"role": "system", "content": ASSET_EXTRACTION_SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    def run_completion(request_messages: list[dict[str, str]], *, max_tokens: int):
        try:
            return client.chat.completions.create(
                model=model_config.model_name,
                messages=request_messages,
                temperature=0.0,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                timeout=600.0,
            )
        except TypeError:
            return client.chat.completions.create(
                model=model_config.model_name,
                messages=request_messages,
                temperature=0.0,
                max_tokens=max_tokens,
                timeout=600.0,
            )
        except Exception as error:
            if not is_unsupported_json_response_format_error(error):
                raise
            return client.chat.completions.create(
                model=model_config.model_name,
                messages=request_messages,
                temperature=0.0,
                max_tokens=max_tokens,
                timeout=600.0,
            )

    response = run_completion(messages, max_tokens=16384)
    write_json(response_path, dump_model(response))

    finish_reason = getattr(response.choices[0], "finish_reason", "")
    content = extract_text_content(response.choices[0].message.content)

    try:
        parsed = normalize_asset_registry_payload(parse_asset_registry_response(content))
        registry = AssetRegistry.model_validate(parsed)
    except Exception as first_error:
        retry_user_prompt = (
            user_prompt
            + "\n\nIMPORTANT RETRY CONSTRAINTS:\n"
            + "- Return a shorter but still complete asset_registry.json.\n"
            + "- Output valid JSON only.\n"
            + "- Do not include any notes, planning text, or explanations.\n"
            + "- Keep every string concise.\n"
            + "- Do not repeat schema instructions.\n"
            + f"- The previous response was invalid or truncated (finish_reason={finish_reason or 'unknown'}).\n"
        )
        write_json(
            retry_request_path,
            {
                "model": model_config.model_name,
                "base_url": model_config.base_url,
                "system_prompt": ASSET_EXTRACTION_SYSTEM_PROMPT,
                "user_prompt": retry_user_prompt,
                "source_script_name": source_script_name,
                "retry_reason": str(first_error),
                "previous_finish_reason": finish_reason,
            },
        )
        retry_messages = [
            {"role": "system", "content": ASSET_EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": retry_user_prompt},
        ]
        retry_response = run_completion(retry_messages, max_tokens=16384)
        write_json(retry_response_path, dump_model(retry_response))
        retry_content = extract_text_content(retry_response.choices[0].message.content)
        parsed = normalize_asset_registry_payload(parse_asset_registry_response(retry_content))
        registry = AssetRegistry.model_validate(parsed)

    registry_path = artifacts.asset_dir / "asset_registry.json"
    write_json(registry_path, registry.model_dump(mode="json"))

    return artifacts


def extract_asset_registry(
    *,
    script_path: Path,
    model_config: TextModelConfig,
    output_root: Path,
    run_dir: Path | None = None,
    dry_run: bool = False,
) -> AssetExtractionArtifacts:
    raw_text = script_path.read_text(encoding="utf-8")
    return extract_asset_registry_from_text(
        source_script_name=script_path.stem,
        script_text=raw_text,
        model_config=model_config,
        output_root=output_root,
        run_dir=run_dir,
        dry_run=dry_run,
        source_path=script_path,
    )
