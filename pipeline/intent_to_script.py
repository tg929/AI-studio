"""Intent-to-script generation node."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pipeline.asset_extraction import (
    AssetExtractionArtifacts,
    create_script_clean_payload,
    extract_asset_registry_from_text,
    normalize_script_text,
    resolve_next_run_dir,
)
from pipeline.io import dump_model, extract_text_content, write_json
from pipeline.runtime import TextModelConfig, build_text_client
from prompts.intent_understanding import (
    INTENT_UNDERSTANDING_SYSTEM_PROMPT,
    build_intent_understanding_user_prompt,
)
from prompts.script_generation import SCRIPT_GENERATION_SYSTEM_PROMPT, build_script_generation_user_prompt
from prompts.script_quality import SCRIPT_QUALITY_SYSTEM_PROMPT, build_script_quality_user_prompt
from prompts.story_blueprint import STORY_BLUEPRINT_SYSTEM_PROMPT, build_story_blueprint_user_prompt
from schemas.intent_packet import IntentPacket
from schemas.script_quality import ScriptQualityReport
from schemas.story_blueprint import StoryBlueprint


AUTO_INPUT_MODE = "auto"


@dataclass(frozen=True, slots=True)
class IntentToScriptArtifacts:
    run_dir: Path
    source_dir: Path
    input_dir: Path
    asset_dir: Path | None = None


def build_intent_artifacts(output_root: Path, run_dir: Path | None) -> IntentToScriptArtifacts:
    resolved_run_dir = run_dir or resolve_next_run_dir(output_root)
    source_dir = resolved_run_dir / "00_source"
    input_dir = resolved_run_dir / "01_input"
    source_dir.mkdir(parents=True, exist_ok=True)
    input_dir.mkdir(parents=True, exist_ok=True)
    return IntentToScriptArtifacts(run_dir=resolved_run_dir, source_dir=source_dir, input_dir=input_dir)


def detect_input_mode(source_text: str) -> str:
    paragraphs = [block for block in source_text.split("\n\n") if block.strip()]
    char_count = len(source_text)
    if char_count >= 1200 or len(paragraphs) >= 6:
        return "script"
    if char_count >= 80 or len(paragraphs) >= 2 or any(mark in source_text for mark in "。！？；\n"):
        return "brief"
    return "keywords"


def normalize_source_text(raw_text: str) -> str:
    return normalize_script_text(raw_text)


def split_string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return []
        normalized = (
            text.replace("\r\n", "\n")
            .replace("\r", "\n")
            .replace("；", "，")
            .replace("、", "，")
            .replace(",", "，")
            .replace("\n", "，")
        )
        return [part.strip() for part in normalized.split("，") if part.strip()]
    return []


def unique_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def normalize_choice(value: Any, mapping: dict[str, str], default: str) -> str:
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in mapping:
            return mapping[normalized]
    return default


def normalize_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, float)):
        return max(minimum, min(maximum, int(value)))
    if isinstance(value, str) and value.strip():
        try:
            return max(minimum, min(maximum, int(float(value.strip()))))
        except ValueError:
            return default
    return default


def normalize_inline_string(value: Any) -> str:
    if isinstance(value, str):
        text = value.strip()
        if text.startswith("[") and text.endswith("]"):
            inner = text[1:-1].strip()
            if inner:
                inner = inner.replace("'", "").replace('"', "")
                parts = [part.strip() for part in inner.replace("，", ",").split(",") if part.strip()]
                return " / ".join(parts)
            return ""
        return text
    if isinstance(value, list):
        parts = [str(item).strip() for item in value if str(item).strip()]
        return " / ".join(parts)
    return str(value).strip()


def normalize_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "y", "是", "通过", "ok"}:
            return True
        if normalized in {"false", "0", "no", "n", "否", "不通过"}:
            return False
    return False


def default_target_spec(*, input_mode: str, source_text: str) -> dict[str, Any]:
    target_length = 2800
    dialogue_density = "medium"
    if input_mode == "keywords":
        target_length = 2600
        dialogue_density = "low"
    elif input_mode == "script":
        target_length = max(1800, min(3500, len(source_text)))
    return {
        "target_runtime_sec": 60,
        "target_shot_count": 6,
        "target_script_length_chars": target_length,
        "dialogue_density": dialogue_density,
        "ending_shape": "hook_next",
    }


def build_source_context(
    *,
    source_script_name: str,
    source_text: str,
    requested_input_mode: str,
    resolved_input_mode: str,
    source_path: Path | None,
) -> dict[str, Any]:
    paragraphs = [block for block in source_text.split("\n\n") if block.strip()]
    lines = [line for line in source_text.splitlines() if line.strip()]
    return {
        "source_script_name": source_script_name,
        "requested_input_mode": requested_input_mode,
        "resolved_input_mode": resolved_input_mode,
        "source_path": str(source_path.resolve()) if source_path is not None else "",
        "character_count": len(source_text),
        "line_count": len(lines),
        "paragraph_count": len(paragraphs),
        "default_target_spec": default_target_spec(input_mode=resolved_input_mode, source_text=source_text),
    }


def read_json_string(value: str) -> dict[str, Any]:
    text = value.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Model output must be a JSON object")
    return parsed


def normalize_intent_packet_payload(
    payload: dict[str, Any],
    *,
    source_script_name: str,
    source_text: str,
    resolved_input_mode: str,
) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "sourceScriptName": "source_script_name",
        "inputMode": "input_mode",
        "rawInput": "raw_input",
        "informationDensity": "information_density",
        "expansionBudget": "expansion_budget",
        "intentSummary": "intent_summary",
        "worldSetting": "world_setting",
        "coreConflict": "core_conflict",
        "protagonistSeed": "protagonist_seed",
        "mustHaveElements": "must_have_elements",
        "forbiddenElements": "forbidden_elements",
        "targetSpec": "target_spec",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    if normalized.get("schema_version") == "1.0.0":
        normalized["schema_version"] = "1.0"

    default_spec = default_target_spec(input_mode=resolved_input_mode, source_text=source_text)
    target_spec = normalized.get("target_spec")
    if not isinstance(target_spec, dict):
        target_spec = {}
    else:
        target_spec = dict(target_spec)
    target_aliases = {
        "targetRuntimeSec": "target_runtime_sec",
        "targetShotCount": "target_shot_count",
        "targetScriptLengthChars": "target_script_length_chars",
        "dialogueDensity": "dialogue_density",
        "endingShape": "ending_shape",
    }
    for alias, target in target_aliases.items():
        if target not in target_spec and alias in target_spec:
            target_spec[target] = target_spec.pop(alias)
    target_spec["target_runtime_sec"] = normalize_int(
        target_spec.get("target_runtime_sec"),
        default=default_spec["target_runtime_sec"],
        minimum=30,
        maximum=180,
    )
    target_spec["target_shot_count"] = normalize_int(
        target_spec.get("target_shot_count"),
        default=default_spec["target_shot_count"],
        minimum=3,
        maximum=12,
    )
    target_spec["target_script_length_chars"] = normalize_int(
        target_spec.get("target_script_length_chars"),
        default=default_spec["target_script_length_chars"],
        minimum=800,
        maximum=6000,
    )
    target_spec["dialogue_density"] = normalize_choice(
        target_spec.get("dialogue_density"),
        {
            "low": "low",
            "medium": "medium",
            "high": "high",
            "低": "low",
            "中": "medium",
            "中等": "medium",
            "高": "high",
        },
        default_spec["dialogue_density"],
    )
    target_spec["ending_shape"] = normalize_choice(
        target_spec.get("ending_shape"),
        {
            "closed": "closed",
            "open": "open",
            "hook_next": "hook_next",
            "hook": "hook_next",
            "cliffhanger": "hook_next",
            "封闭": "closed",
            "开放": "open",
            "留钩子": "hook_next",
        },
        default_spec["ending_shape"],
    )

    genre = normalized.get("genre")
    if isinstance(genre, list):
        normalized["genre"] = " / ".join(str(item).strip() for item in genre if str(item).strip())

    normalized["schema_version"] = "1.0"
    normalized["source_script_name"] = source_script_name
    normalized["input_mode"] = resolved_input_mode
    normalized["raw_input"] = source_text
    normalized["language"] = "zh-CN"
    normalized["information_density"] = normalize_choice(
        normalized.get("information_density"),
        {
            "sparse": "sparse",
            "medium": "medium",
            "rich": "rich",
            "low": "sparse",
            "high": "rich",
            "稀疏": "sparse",
            "简短": "sparse",
            "中": "medium",
            "中等": "medium",
            "详细": "rich",
            "丰富": "rich",
        },
        {"keywords": "sparse", "brief": "medium", "script": "rich"}[resolved_input_mode],
    )
    normalized["expansion_budget"] = normalize_choice(
        normalized.get("expansion_budget"),
        {
            "low": "low",
            "medium": "medium",
            "high": "high",
            "低": "low",
            "中": "medium",
            "中等": "medium",
            "高": "high",
        },
        {"keywords": "high", "brief": "medium", "script": "low"}[resolved_input_mode],
    )
    normalized["intent_summary"] = normalize_inline_string(normalized.get("intent_summary")) or source_text[:120].strip()
    normalized["tone"] = normalize_inline_string(normalized.get("tone"))
    normalized["era"] = normalize_inline_string(normalized.get("era"))
    normalized["world_setting"] = normalize_inline_string(normalized.get("world_setting"))
    normalized["core_conflict"] = normalize_inline_string(normalized.get("core_conflict"))
    normalized["protagonist_seed"] = normalize_inline_string(normalized.get("protagonist_seed"))
    normalized["must_have_elements"] = split_string_list(normalized.get("must_have_elements"))
    normalized["forbidden_elements"] = split_string_list(normalized.get("forbidden_elements"))
    normalized["assumptions"] = split_string_list(normalized.get("assumptions"))
    normalized["ambiguities"] = split_string_list(normalized.get("ambiguities"))
    normalized["target_spec"] = target_spec
    return normalized


def normalize_story_blueprint_payload(payload: dict[str, Any], *, source_script_name: str) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "sourceScriptName": "source_script_name",
        "logLine": "logline",
        "narrativeArc": "narrative_arc",
        "characterPlan": "character_plan",
        "scenePlan": "scene_plan",
        "propPlan": "prop_plan",
        "beatSheet": "beat_sheet",
        "endingNote": "ending_note",
        "consistencyNotes": "consistency_notes",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    if normalized.get("schema_version") == "1.0.0":
        normalized["schema_version"] = "1.0"

    character_plan = []
    for item in normalized.get("character_plan", []):
        if not isinstance(item, dict):
            continue
        record = dict(item)
        if "dramatic_function" not in record and "dramaticFunction" in record:
            record["dramatic_function"] = record.pop("dramaticFunction")
        if "visual_seed" not in record and "visualSeed" in record:
            record["visual_seed"] = record.pop("visualSeed")
        record["role"] = normalize_choice(
            record.get("role"),
            {
                "protagonist": "protagonist",
                "support": "support",
                "antagonistic_force": "antagonistic_force",
                "antagonist": "antagonistic_force",
                "minor": "minor",
                "主角": "protagonist",
                "配角": "support",
                "反派势力": "antagonistic_force",
                "对抗力量": "antagonistic_force",
                "次要": "minor",
            },
            "minor",
        )
        character_plan.append(record)
    normalized["character_plan"] = character_plan[:4]

    scene_plan = []
    for item in normalized.get("scene_plan", []):
        if not isinstance(item, dict):
            continue
        record = dict(item)
        if "dramatic_use" not in record and "dramaticUse" in record:
            record["dramatic_use"] = record.pop("dramaticUse")
        if "visual_anchors" not in record and "visualAnchors" in record:
            record["visual_anchors"] = record.pop("visualAnchors")
        record["visual_anchors"] = unique_preserve_order(split_string_list(record.get("visual_anchors")))[:5]
        scene_plan.append(record)
    normalized["scene_plan"] = scene_plan[:3]

    prop_plan = []
    for item in normalized.get("prop_plan", []):
        if not isinstance(item, dict):
            continue
        record = dict(item)
        if "visual_seed" not in record and "visualSeed" in record:
            record["visual_seed"] = record.pop("visualSeed")
        prop_plan.append(record)
    normalized["prop_plan"] = prop_plan[:3]

    beat_sheet = []
    for item in normalized.get("beat_sheet", []):
        if not isinstance(item, dict):
            continue
        record = dict(item)
        field_aliases = {
            "beatId": "beat_id",
            "sceneName": "scene_name",
            "characterFocus": "character_focus",
            "propFocus": "prop_focus",
            "visualAnchors": "visual_anchors",
        }
        for alias, target in field_aliases.items():
            if target not in record and alias in record:
                record[target] = record.pop(alias)
        record["purpose"] = normalize_choice(
            record.get("purpose"),
            {
                "setup": "setup",
                "pressure": "pressure",
                "turn": "turn",
                "climax": "climax",
                "release": "release",
                "建立": "setup",
                "开场": "setup",
                "施压": "pressure",
                "升级": "pressure",
                "冲突": "pressure",
                "转折": "turn",
                "反转": "turn",
                "高潮": "climax",
                "收束": "release",
                "尾声": "release",
                "余韵": "release",
            },
            "pressure",
        )
        record["character_focus"] = unique_preserve_order(split_string_list(record.get("character_focus")))
        record["prop_focus"] = unique_preserve_order(split_string_list(record.get("prop_focus")))
        record["visual_anchors"] = unique_preserve_order(split_string_list(record.get("visual_anchors")))
        beat_sheet.append(record)
    normalized["beat_sheet"] = beat_sheet[:8]

    known_character_names = {
        str(item.get("name", "")).strip()
        for item in normalized["character_plan"]
        if str(item.get("name", "")).strip()
    }
    known_scene_names = {
        str(item.get("name", "")).strip()
        for item in normalized["scene_plan"]
        if str(item.get("name", "")).strip()
    }
    known_prop_names = {
        str(item.get("name", "")).strip()
        for item in normalized["prop_plan"]
        if str(item.get("name", "")).strip()
    }
    filtered_beats = []
    for record in normalized["beat_sheet"]:
        record = dict(record)
        record["character_focus"] = [item for item in record["character_focus"] if item in known_character_names]
        record["prop_focus"] = [item for item in record["prop_focus"] if item in known_prop_names]
        scene_name = str(record.get("scene_name", "")).strip()
        if scene_name not in known_scene_names and normalized["scene_plan"]:
            record["scene_name"] = normalized["scene_plan"][0]["name"]
        filtered_beats.append(record)
    normalized["beat_sheet"] = filtered_beats

    normalized["schema_version"] = "1.0"
    normalized["source_script_name"] = source_script_name
    normalized["title"] = str(normalized.get("title", "")).strip()
    normalized["logline"] = str(normalized.get("logline", "")).strip()
    normalized["theme"] = str(normalized.get("theme", "")).strip()
    normalized["narrative_arc"] = str(normalized.get("narrative_arc", "")).strip() or "setup-pressure-turn"
    normalized["ending_note"] = str(normalized.get("ending_note", "")).strip()
    normalized["consistency_notes"] = split_string_list(normalized.get("consistency_notes"))
    return normalized


def normalize_script_quality_payload(
    payload: dict[str, Any],
    *,
    source_script_name: str,
    title: str,
) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "sourceScriptName": "source_script_name",
        "passesHardChecks": "passes_hard_checks",
        "hardChecks": "hard_checks",
        "qualityScores": "quality_scores",
        "recommendedRepairs": "recommended_repairs",
        "repairNeeded": "repair_needed",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    if normalized.get("schema_version") == "1.0.0":
        normalized["schema_version"] = "1.0"

    hard_checks = normalized.get("hard_checks")
    if not isinstance(hard_checks, dict):
        hard_checks = {}
    else:
        hard_checks = dict(hard_checks)
    hard_aliases = {
        "lengthRangeOk": "length_range_ok",
        "paragraphCountOk": "paragraph_count_ok",
        "namedCharacterCountOk": "named_character_count_ok",
        "sceneCountOk": "scene_count_ok",
        "narrativeArcOk": "narrative_arc_ok",
        "visualAnchorDensityOk": "visual_anchor_density_ok",
    }
    for alias, target in hard_aliases.items():
        if target not in hard_checks and alias in hard_checks:
            hard_checks[target] = hard_checks.pop(alias)
    hard_checks = {
        "length_range_ok": normalize_bool(hard_checks.get("length_range_ok")),
        "paragraph_count_ok": normalize_bool(hard_checks.get("paragraph_count_ok")),
        "named_character_count_ok": normalize_bool(hard_checks.get("named_character_count_ok")),
        "scene_count_ok": normalize_bool(hard_checks.get("scene_count_ok")),
        "narrative_arc_ok": normalize_bool(hard_checks.get("narrative_arc_ok")),
        "visual_anchor_density_ok": normalize_bool(hard_checks.get("visual_anchor_density_ok")),
    }

    quality_scores = normalized.get("quality_scores")
    if not isinstance(quality_scores, dict):
        quality_scores = {}
    else:
        quality_scores = dict(quality_scores)
    score_aliases = {
        "assetExtractionReadiness": "asset_extraction_readiness",
        "storyboardReadiness": "storyboard_readiness",
        "visualSpecificity": "visual_specificity",
        "characterClarity": "character_clarity",
        "sceneClarity": "scene_clarity",
        "propSupport": "prop_support",
    }
    for alias, target in score_aliases.items():
        if target not in quality_scores and alias in quality_scores:
            quality_scores[target] = quality_scores.pop(alias)
    quality_scores = {
        "asset_extraction_readiness": normalize_int(
            quality_scores.get("asset_extraction_readiness"),
            default=7,
            minimum=1,
            maximum=10,
        ),
        "storyboard_readiness": normalize_int(
            quality_scores.get("storyboard_readiness"),
            default=7,
            minimum=1,
            maximum=10,
        ),
        "visual_specificity": normalize_int(
            quality_scores.get("visual_specificity"),
            default=7,
            minimum=1,
            maximum=10,
        ),
        "character_clarity": normalize_int(
            quality_scores.get("character_clarity"),
            default=7,
            minimum=1,
            maximum=10,
        ),
        "scene_clarity": normalize_int(
            quality_scores.get("scene_clarity"),
            default=7,
            minimum=1,
            maximum=10,
        ),
        "prop_support": normalize_int(
            quality_scores.get("prop_support"),
            default=7,
            minimum=1,
            maximum=10,
        ),
    }

    passes_hard_checks = all(hard_checks.values())
    repair_needed = normalize_bool(normalized.get("repair_needed")) or not passes_hard_checks

    normalized["schema_version"] = "1.0"
    normalized["source_script_name"] = source_script_name
    normalized["title"] = str(normalized.get("title", "")).strip() or title
    normalized["passes_hard_checks"] = passes_hard_checks
    normalized["hard_checks"] = hard_checks
    normalized["quality_scores"] = quality_scores
    normalized["strengths"] = split_string_list(normalized.get("strengths"))
    normalized["risks"] = split_string_list(normalized.get("risks"))
    normalized["recommended_repairs"] = split_string_list(normalized.get("recommended_repairs"))
    normalized["repair_needed"] = repair_needed
    normalized["summary"] = str(normalized.get("summary", "")).strip()
    return normalized


def clean_generated_script_text(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    prefixes = ("generated_script.txt", "剧本正文：", "正文：", "剧本：")
    for prefix in prefixes:
        if text.startswith(prefix):
            text = text[len(prefix) :].lstrip("：: \n")
            break
    return normalize_script_text(text)


def run_text_stage(
    *,
    client: Any,
    model_config: TextModelConfig,
    system_prompt: str,
    user_prompt: str,
    request_path: Path,
    response_path: Path,
    request_metadata: dict[str, Any],
    temperature: float,
    max_tokens: int,
) -> str:
    request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        **request_metadata,
    }
    write_json(request_path, request_payload)

    response = client.chat.completions.create(
        model=model_config.model_name,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=600.0,
    )
    write_json(response_path, dump_model(response))
    return extract_text_content(response.choices[0].message.content)


def generate_script_from_intent(
    *,
    source_text: str,
    source_script_name: str,
    model_config: TextModelConfig,
    output_root: Path,
    run_dir: Path | None = None,
    source_path: Path | None = None,
    input_mode: str = AUTO_INPUT_MODE,
    dry_run: bool = False,
    extract_assets: bool = False,
) -> IntentToScriptArtifacts:
    normalized_source_text = normalize_source_text(source_text)
    if not normalized_source_text:
        raise ValueError("Source input is empty after normalization")

    requested_input_mode = input_mode
    resolved_input_mode = input_mode if input_mode != AUTO_INPUT_MODE else detect_input_mode(normalized_source_text)
    artifacts = build_intent_artifacts(output_root, run_dir)

    source_input_path = artifacts.source_dir / "source_input.txt"
    source_input_path.write_text(normalized_source_text, encoding="utf-8")

    source_context = build_source_context(
        source_script_name=source_script_name,
        source_text=normalized_source_text,
        requested_input_mode=requested_input_mode,
        resolved_input_mode=resolved_input_mode,
        source_path=source_path,
    )
    source_context_path = artifacts.source_dir / "source_context.json"
    write_json(source_context_path, source_context)

    intent_request_path = artifacts.source_dir / "intent_packet_request.json"
    intent_response_path = artifacts.source_dir / "intent_packet_response.json"
    intent_user_prompt = build_intent_understanding_user_prompt(source_context, normalized_source_text)
    intent_request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": INTENT_UNDERSTANDING_SYSTEM_PROMPT,
        "user_prompt": intent_user_prompt,
        "source_script_name": source_script_name,
        "resolved_input_mode": resolved_input_mode,
    }
    write_json(intent_request_path, intent_request_payload)
    if dry_run:
        return artifacts

    client = build_text_client(model_config)

    intent_content = run_text_stage(
        client=client,
        model_config=model_config,
        system_prompt=INTENT_UNDERSTANDING_SYSTEM_PROMPT,
        user_prompt=intent_user_prompt,
        request_path=intent_request_path,
        response_path=intent_response_path,
        request_metadata={
            "source_script_name": source_script_name,
            "resolved_input_mode": resolved_input_mode,
        },
        temperature=0.1,
        max_tokens=4096,
    )
    intent_packet = IntentPacket.model_validate(
        normalize_intent_packet_payload(
            read_json_string(intent_content),
            source_script_name=source_script_name,
            source_text=normalized_source_text,
            resolved_input_mode=resolved_input_mode,
        )
    )
    intent_packet_path = artifacts.source_dir / "intent_packet.json"
    write_json(intent_packet_path, intent_packet.model_dump(mode="json"))

    blueprint_request_path = artifacts.source_dir / "story_blueprint_request.json"
    blueprint_response_path = artifacts.source_dir / "story_blueprint_response.json"
    blueprint_user_prompt = build_story_blueprint_user_prompt(intent_packet.model_dump(mode="json"))
    blueprint_content = run_text_stage(
        client=client,
        model_config=model_config,
        system_prompt=STORY_BLUEPRINT_SYSTEM_PROMPT,
        user_prompt=blueprint_user_prompt,
        request_path=blueprint_request_path,
        response_path=blueprint_response_path,
        request_metadata={
            "source_script_name": source_script_name,
            "stage": "story_blueprint",
        },
        temperature=0.2,
        max_tokens=4096,
    )
    story_blueprint = StoryBlueprint.model_validate(
        normalize_story_blueprint_payload(
            read_json_string(blueprint_content),
            source_script_name=source_script_name,
        )
    )
    story_blueprint_path = artifacts.source_dir / "story_blueprint.json"
    write_json(story_blueprint_path, story_blueprint.model_dump(mode="json"))

    script_generation_request_path = artifacts.source_dir / "script_generation_request.json"
    script_generation_response_path = artifacts.source_dir / "script_generation_response.json"
    if resolved_input_mode == "script":
        write_json(
            script_generation_request_path,
            {
                "source_script_name": source_script_name,
                "skipped": True,
                "reason": "resolved_input_mode=script, reuse normalized source input as generated script",
            },
        )
        write_json(
            script_generation_response_path,
            {
                "source_script_name": source_script_name,
                "reused_source_script": True,
            },
        )
        generated_script_text = normalized_source_text
        generation_mode = "reused_source_script"
    else:
        script_generation_user_prompt = build_script_generation_user_prompt(
            intent_packet.model_dump(mode="json"),
            story_blueprint.model_dump(mode="json"),
        )
        script_generation_content = run_text_stage(
            client=client,
            model_config=model_config,
            system_prompt=SCRIPT_GENERATION_SYSTEM_PROMPT,
            user_prompt=script_generation_user_prompt,
            request_path=script_generation_request_path,
            response_path=script_generation_response_path,
            request_metadata={
                "source_script_name": source_script_name,
                "title": story_blueprint.title,
                "stage": "script_generation",
            },
            temperature=0.5,
            max_tokens=8192,
        )
        generated_script_text = clean_generated_script_text(script_generation_content)
        generation_mode = "expanded_from_intent"

    if not generated_script_text:
        raise ValueError("Generated script text is empty after normalization")

    generated_script_path = artifacts.source_dir / "generated_script.txt"
    generated_script_path.write_text(generated_script_text, encoding="utf-8")
    generated_script_meta = create_script_clean_payload(
        source_script_name=source_script_name,
        normalized_text=generated_script_text,
        source_path=generated_script_path,
    )
    generated_script_meta["title"] = story_blueprint.title
    generated_script_meta["generation_mode"] = generation_mode
    write_json(artifacts.source_dir / "generated_script_meta.json", generated_script_meta)

    script_clean_payload = create_script_clean_payload(
        source_script_name=source_script_name,
        normalized_text=generated_script_text,
        source_path=generated_script_path,
    )
    script_clean_text_path = artifacts.input_dir / "script_clean.txt"
    script_clean_json_path = artifacts.input_dir / "script_clean.json"
    script_clean_text_path.write_text(generated_script_text, encoding="utf-8")
    write_json(script_clean_json_path, script_clean_payload)

    quality_request_path = artifacts.source_dir / "script_quality_request.json"
    quality_response_path = artifacts.source_dir / "script_quality_response.json"
    quality_user_prompt = build_script_quality_user_prompt(
        intent_packet.model_dump(mode="json"),
        story_blueprint.model_dump(mode="json"),
        generated_script_text,
    )
    quality_content = run_text_stage(
        client=client,
        model_config=model_config,
        system_prompt=SCRIPT_QUALITY_SYSTEM_PROMPT,
        user_prompt=quality_user_prompt,
        request_path=quality_request_path,
        response_path=quality_response_path,
        request_metadata={
            "source_script_name": source_script_name,
            "title": story_blueprint.title,
            "stage": "script_quality",
        },
        temperature=0.0,
        max_tokens=4096,
    )
    quality_report = ScriptQualityReport.model_validate(
        normalize_script_quality_payload(
            read_json_string(quality_content),
            source_script_name=source_script_name,
            title=story_blueprint.title,
        )
    )
    quality_report_path = artifacts.source_dir / "script_quality_report.json"
    write_json(quality_report_path, quality_report.model_dump(mode="json"))

    asset_dir: Path | None = None
    if extract_assets:
        extraction_artifacts: AssetExtractionArtifacts = extract_asset_registry_from_text(
            source_script_name=source_script_name,
            script_text=generated_script_text,
            model_config=model_config,
            output_root=output_root,
            run_dir=artifacts.run_dir,
            dry_run=False,
            source_path=generated_script_path,
        )
        asset_dir = extraction_artifacts.asset_dir

    return IntentToScriptArtifacts(
        run_dir=artifacts.run_dir,
        source_dir=artifacts.source_dir,
        input_dir=artifacts.input_dir,
        asset_dir=asset_dir,
    )
