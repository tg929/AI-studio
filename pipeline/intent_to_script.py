"""Intent-to-script generation node."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from pipeline.asset_extraction import (
    AssetExtractionArtifacts,
    create_script_clean_payload,
    extract_asset_registry_from_text,
    normalize_script_text,
    resolve_next_run_dir,
)
from pipeline.io import dump_model, extract_text_content, write_json
from pipeline.runtime import TextModelConfig, build_text_client
from prompts.asset_readiness import ASSET_READINESS_SYSTEM_PROMPT, build_asset_readiness_user_prompt
from prompts.intake_router import INTAKE_ROUTER_SYSTEM_PROMPT, build_intake_router_user_prompt
from prompts.intent_understanding import (
    INTENT_UNDERSTANDING_SYSTEM_PROMPT,
    build_intent_understanding_user_prompt,
)
from prompts.script_generation import SCRIPT_GENERATION_SYSTEM_PROMPT, build_script_generation_user_prompt
from prompts.script_quality import SCRIPT_QUALITY_SYSTEM_PROMPT, build_script_quality_user_prompt
from prompts.story_blueprint import STORY_BLUEPRINT_SYSTEM_PROMPT, build_story_blueprint_user_prompt
from schemas.asset_readiness import AssetReadinessReport
from schemas.intake_router import IntakeRouter
from schemas.intent_packet import IntentPacket
from schemas.script_quality import ScriptQualityReport
from schemas.story_blueprint import StoryBlueprint


AUTO_INPUT_MODE = "auto"
ProgressCallback = Callable[[dict[str, Any]], None]


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


def default_project_target(*, input_mode: str, source_text: str) -> dict[str, Any]:
    target_spec = default_target_spec(input_mode=input_mode, source_text=source_text)
    return {
        "target_runtime_sec": target_spec["target_runtime_sec"],
        "target_shot_count": target_spec["target_shot_count"],
        "target_script_length_chars": target_spec["target_script_length_chars"],
        "shot_duration_sec": 10,
    }


def build_source_context(
    *,
    source_script_name: str,
    source_text: str,
    requested_input_mode: str,
    fallback_input_mode: str,
    source_path: Path | None,
) -> dict[str, Any]:
    paragraphs = [block for block in source_text.split("\n\n") if block.strip()]
    lines = [line for line in source_text.splitlines() if line.strip()]
    return {
        "source_script_name": source_script_name,
        "requested_input_mode": requested_input_mode,
        "fallback_input_mode": fallback_input_mode,
        "source_path": str(source_path.resolve()) if source_path is not None else "",
        "character_count": len(source_text),
        "line_count": len(lines),
        "paragraph_count": len(paragraphs),
        "default_target_spec": default_target_spec(input_mode=fallback_input_mode, source_text=source_text),
        "project_target": default_project_target(input_mode=fallback_input_mode, source_text=source_text),
    }


def resolve_intent_input_mode(
    *,
    requested_input_mode: str,
    fallback_input_mode: str,
    source_form: str,
) -> str:
    if requested_input_mode != AUTO_INPUT_MODE:
        return requested_input_mode
    source_form_mapping = {
        "keywords": "keywords",
        "brief": "brief",
        "partial_script": "brief",
        "full_script": "script",
        "mixed": fallback_input_mode,
    }
    return source_form_mapping.get(source_form, fallback_input_mode)


def generation_mode_from_path(chosen_path: str) -> str:
    return {
        "expand_then_extract": "expanded_from_input",
        "compress_then_extract": "compressed_from_input",
        "rewrite_then_extract": "rewritten_for_asset_clarity",
        "direct_extract": "direct_extract_reuse_source",
    }.get(chosen_path, "unknown")


def evaluated_text_kind_from_path(chosen_path: str) -> str:
    if chosen_path == "direct_extract":
        return "raw_input"
    return "transformed_script"


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


def normalize_intake_router_payload(
    payload: dict[str, Any],
    *,
    source_script_name: str,
    source_context: dict[str, Any],
) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "sourceScriptName": "source_script_name",
        "userGoal": "user_goal",
        "sourceForm": "source_form",
        "materialState": "material_state",
        "projectTarget": "project_target",
        "assetReadinessEstimate": "asset_readiness_estimate",
        "chosenPath": "chosen_path",
        "recommendedOperations": "recommended_operations",
        "missingCriticalInfo": "missing_critical_info",
        "needsConfirmation": "needs_confirmation",
        "confirmationPoints": "confirmation_points",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    project_target = normalized.get("project_target")
    if not isinstance(project_target, dict):
        project_target = {}
    else:
        project_target = dict(project_target)
    project_aliases = {
        "targetRuntimeSec": "target_runtime_sec",
        "targetShotCount": "target_shot_count",
        "targetScriptLengthChars": "target_script_length_chars",
        "shotDurationSec": "shot_duration_sec",
    }
    for alias, target in project_aliases.items():
        if target not in project_target and alias in project_target:
            project_target[target] = project_target.pop(alias)

    default_project = dict(source_context.get("project_target", {}))
    project_target["target_runtime_sec"] = normalize_int(
        project_target.get("target_runtime_sec"),
        default=int(default_project.get("target_runtime_sec", 60)),
        minimum=30,
        maximum=180,
    )
    project_target["target_shot_count"] = normalize_int(
        project_target.get("target_shot_count"),
        default=int(default_project.get("target_shot_count", 6)),
        minimum=3,
        maximum=12,
    )
    project_target["target_script_length_chars"] = normalize_int(
        project_target.get("target_script_length_chars"),
        default=int(default_project.get("target_script_length_chars", 2600)),
        minimum=800,
        maximum=6000,
    )
    project_target["shot_duration_sec"] = normalize_int(
        project_target.get("shot_duration_sec"),
        default=int(default_project.get("shot_duration_sec", 10)),
        minimum=1,
        maximum=30,
    )

    fallback_input_mode = str(source_context.get("fallback_input_mode", "brief")).strip() or "brief"
    default_source_form = {
        "keywords": "keywords",
        "brief": "brief",
        "script": "full_script",
    }.get(fallback_input_mode, "brief")
    default_material_state = {
        "keywords": "idea_only",
        "brief": "synopsis_like",
        "full_script": "script_like",
    }[default_source_form]
    default_path = {
        "keywords": "expand_then_extract",
        "brief": "expand_then_extract",
        "full_script": "direct_extract",
    }[default_source_form]
    default_readiness = {
        "keywords": "low",
        "brief": "medium",
        "full_script": "medium",
    }[default_source_form]

    normalized["schema_version"] = "1.0"
    normalized["source_script_name"] = source_script_name
    normalized["user_goal"] = normalize_choice(
        normalized.get("user_goal"),
        {
            "auto": "auto",
            "create_story": "create_story",
            "expand_input": "expand_input",
            "compress_input": "compress_input",
            "rewrite_for_visuals": "rewrite_for_visuals",
            "extract_assets": "extract_assets",
            "创作故事": "create_story",
            "扩写": "expand_input",
            "缩写": "compress_input",
            "压缩": "compress_input",
            "重写": "rewrite_for_visuals",
            "抽资产": "extract_assets",
        },
        "auto",
    )
    normalized["source_form"] = normalize_choice(
        normalized.get("source_form"),
        {
            "keywords": "keywords",
            "brief": "brief",
            "partial_script": "partial_script",
            "full_script": "full_script",
            "script": "full_script",
            "mixed": "mixed",
            "关键词": "keywords",
            "简述": "brief",
            "概要": "brief",
            "半成品剧本": "partial_script",
            "完整剧本": "full_script",
            "混合": "mixed",
        },
        default_source_form,
    )
    normalized["material_state"] = normalize_choice(
        normalized.get("material_state"),
        {
            "idea_only": "idea_only",
            "synopsis_like": "synopsis_like",
            "outline_like": "outline_like",
            "script_like": "script_like",
            "asset_ready_script": "asset_ready_script",
            "想法": "idea_only",
            "概要": "synopsis_like",
            "大纲": "outline_like",
            "剧本": "script_like",
            "可直接抽资产": "asset_ready_script",
        },
        default_material_state,
    )
    normalized["asset_readiness_estimate"] = normalize_choice(
        normalized.get("asset_readiness_estimate"),
        {
            "low": "low",
            "medium": "medium",
            "high": "high",
            "低": "low",
            "中": "medium",
            "中等": "medium",
            "高": "high",
        },
        default_readiness,
    )
    normalized["chosen_path"] = normalize_choice(
        normalized.get("chosen_path"),
        {
            "expand_then_extract": "expand_then_extract",
            "compress_then_extract": "compress_then_extract",
            "rewrite_then_extract": "rewrite_then_extract",
            "direct_extract": "direct_extract",
            "confirm_then_continue": "confirm_then_continue",
            "expand": "expand_then_extract",
            "compress": "compress_then_extract",
            "rewrite": "rewrite_then_extract",
            "reuse_script": "direct_extract",
            "confirm": "confirm_then_continue",
            "直接抽取": "direct_extract",
            "扩写后抽取": "expand_then_extract",
            "压缩后抽取": "compress_then_extract",
            "重写后抽取": "rewrite_then_extract",
            "先确认再继续": "confirm_then_continue",
        },
        default_path,
    )

    operation_map = {
        "expand": "expand",
        "compress": "compress",
        "rewrite_for_asset_clarity": "rewrite_for_asset_clarity",
        "rewrite": "rewrite_for_asset_clarity",
        "扩写": "expand",
        "压缩": "compress",
        "缩写": "compress",
        "重写": "rewrite_for_asset_clarity",
        "资产清晰化重写": "rewrite_for_asset_clarity",
    }
    path_to_primary_operation = {
        "expand_then_extract": "expand",
        "compress_then_extract": "compress",
        "rewrite_then_extract": "rewrite_for_asset_clarity",
        "direct_extract": "",
        "confirm_then_continue": "",
    }
    primary_operation_to_path = {
        "expand": "expand_then_extract",
        "compress": "compress_then_extract",
        "rewrite_for_asset_clarity": "rewrite_then_extract",
    }

    operations = []
    for item in split_string_list(normalized.get("recommended_operations")):
        mapped = operation_map.get(item.strip().lower()) or operation_map.get(item.strip())
        if mapped:
            operations.append(mapped)
    operations = unique_preserve_order(operations)
    chosen_path = normalized["chosen_path"]
    expected_primary = path_to_primary_operation[chosen_path]
    if chosen_path in {"direct_extract", "confirm_then_continue"}:
        operations = []
    elif not operations:
        operations = [expected_primary]
    elif expected_primary and expected_primary in operations:
        operations = [expected_primary, *[item for item in operations if item != expected_primary]]
    else:
        inferred_path = primary_operation_to_path.get(operations[0])
        if inferred_path:
            normalized["chosen_path"] = inferred_path
            chosen_path = inferred_path
            expected_primary = path_to_primary_operation[chosen_path]
            operations = [expected_primary, *[item for item in operations if item != expected_primary]]
    normalized["recommended_operations"] = operations[:2]
    normalized["reasons"] = split_string_list(normalized.get("reasons"))
    normalized["risks"] = split_string_list(normalized.get("risks"))
    normalized["missing_critical_info"] = split_string_list(normalized.get("missing_critical_info"))

    raw_confirmation_points = split_string_list(normalized.get("confirmation_points"))
    if normalized["chosen_path"] == "confirm_then_continue":
        normalized["needs_confirmation"] = True
        normalized["confirmation_points"] = (
            raw_confirmation_points
            or normalized["missing_critical_info"]
            or normalized["risks"][:1]
            or ["Confirm the upstream routing decision before continuing."]
        )
    else:
        # Some model outputs keep stale confirmation flags even when a concrete path is chosen.
        normalized["needs_confirmation"] = False
        normalized["confirmation_points"] = []
    normalized["project_target"] = project_target
    return normalized


def normalize_asset_readiness_payload(
    payload: dict[str, Any],
    *,
    source_script_name: str,
    evaluated_text_kind: str,
) -> dict[str, Any]:
    normalized = dict(payload)

    alias_map = {
        "sourceScriptName": "source_script_name",
        "evaluatedTextKind": "evaluated_text_kind",
        "overallStatus": "overall_status",
        "safeToExtract": "safe_to_extract",
        "dimensionScores": "dimension_scores",
        "blockingIssues": "blocking_issues",
        "suggestedNextAction": "suggested_next_action",
        "repairFocus": "repair_focus",
    }
    for alias, target in alias_map.items():
        if target not in normalized and alias in normalized:
            normalized[target] = normalized.pop(alias)

    dimension_scores = normalized.get("dimension_scores")
    if not isinstance(dimension_scores, dict):
        dimension_scores = {}
    else:
        dimension_scores = dict(dimension_scores)
    score_aliases = {
        "characterClarity": "character_clarity",
        "sceneClarity": "scene_clarity",
        "propClarity": "prop_clarity",
        "visualAnchorDensity": "visual_anchor_density",
        "eventChainCoherence": "event_chain_coherence",
        "specFitFor60s6shots": "spec_fit_for_60s_6shots",
        "ambiguityRisk": "ambiguity_risk",
        "extractionStability": "extraction_stability",
    }
    for alias, target in score_aliases.items():
        if target not in dimension_scores and alias in dimension_scores:
            dimension_scores[target] = dimension_scores.pop(alias)

    strength_map = {
        "weak": "weak",
        "usable": "usable",
        "strong": "strong",
        "弱": "weak",
        "可用": "usable",
        "强": "strong",
    }
    ambiguity_map = {
        "high": "high",
        "medium": "medium",
        "low": "low",
        "高": "high",
        "中": "medium",
        "中等": "medium",
        "低": "low",
    }
    dimension_scores = {
        "character_clarity": normalize_choice(dimension_scores.get("character_clarity"), strength_map, "usable"),
        "scene_clarity": normalize_choice(dimension_scores.get("scene_clarity"), strength_map, "usable"),
        "prop_clarity": normalize_choice(dimension_scores.get("prop_clarity"), strength_map, "usable"),
        "visual_anchor_density": normalize_choice(
            dimension_scores.get("visual_anchor_density"),
            strength_map,
            "usable",
        ),
        "event_chain_coherence": normalize_choice(
            dimension_scores.get("event_chain_coherence"),
            strength_map,
            "usable",
        ),
        "spec_fit_for_60s_6shots": normalize_choice(
            dimension_scores.get("spec_fit_for_60s_6shots"),
            strength_map,
            "usable",
        ),
        "ambiguity_risk": normalize_choice(dimension_scores.get("ambiguity_risk"), ambiguity_map, "medium"),
        "extraction_stability": normalize_choice(
            dimension_scores.get("extraction_stability"),
            strength_map,
            "usable",
        ),
    }

    normalized["schema_version"] = "1.0"
    normalized["source_script_name"] = source_script_name
    normalized["evaluated_text_kind"] = normalize_choice(
        normalized.get("evaluated_text_kind"),
        {
            "raw_input": "raw_input",
            "transformed_script": "transformed_script",
            "原始输入": "raw_input",
            "改写后文本": "transformed_script",
        },
        evaluated_text_kind,
    )
    normalized["overall_status"] = normalize_choice(
        normalized.get("overall_status"),
        {
            "ready": "ready",
            "borderline": "borderline",
            "not_ready": "not_ready",
            "可直接提取": "ready",
            "临界": "borderline",
            "不可提取": "not_ready",
        },
        "borderline",
    )
    normalized["safe_to_extract"] = normalize_bool(normalized.get("safe_to_extract"))
    if normalized["overall_status"] == "ready":
        normalized["safe_to_extract"] = True
    if normalized["overall_status"] == "not_ready":
        normalized["safe_to_extract"] = False
    normalized["dimension_scores"] = dimension_scores
    normalized["blocking_issues"] = split_string_list(normalized.get("blocking_issues"))
    normalized["suggested_next_action"] = normalize_choice(
        normalized.get("suggested_next_action"),
        {
            "extract": "extract",
            "expand": "expand",
            "compress": "compress",
            "rewrite_for_asset_clarity": "rewrite_for_asset_clarity",
            "rewrite": "rewrite_for_asset_clarity",
            "confirm": "confirm",
            "提取": "extract",
            "扩写": "expand",
            "压缩": "compress",
            "重写": "rewrite_for_asset_clarity",
            "确认": "confirm",
        },
        "extract" if normalized["safe_to_extract"] else "rewrite_for_asset_clarity",
    )
    normalized["repair_focus"] = split_string_list(normalized.get("repair_focus"))
    normalized["summary"] = str(normalized.get("summary", "")).strip() or "资产提取可用性评估已生成。"
    return normalized


def ensure_min_scene_visual_anchors(
    scene_plan: list[dict[str, Any]],
    beat_sheet: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    beat_anchor_map: dict[str, list[str]] = {}
    for beat in beat_sheet:
        if not isinstance(beat, dict):
            continue
        scene_name = str(beat.get("scene_name", "")).strip()
        if not scene_name:
            continue
        beat_anchor_map.setdefault(scene_name, []).extend(split_string_list(beat.get("visual_anchors")))

    normalized_scene_plan: list[dict[str, Any]] = []
    for item in scene_plan:
        record = dict(item)
        scene_name = str(record.get("name", "")).strip()
        anchors = unique_preserve_order(split_string_list(record.get("visual_anchors")))[:5]
        fallback_candidates: list[str] = []
        fallback_candidates.extend(beat_anchor_map.get(scene_name, []))
        fallback_candidates.extend(split_string_list(scene_name))
        fallback_candidates.extend(split_string_list(record.get("dramatic_use")))
        if scene_name:
            fallback_candidates.extend([f"{scene_name}环境氛围", f"{scene_name}空间边界"])
        for candidate in fallback_candidates:
            candidate = str(candidate).strip()
            if not candidate or candidate in anchors:
                continue
            anchors.append(candidate)
            if len(anchors) >= 3:
                break
        record["visual_anchors"] = anchors[:5]
        normalized_scene_plan.append(record)
    return normalized_scene_plan


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
    normalized["scene_plan"] = ensure_min_scene_visual_anchors(normalized["scene_plan"], normalized["beat_sheet"])

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


def write_stage_skip(path: Path, *, source_script_name: str, reason: str, extra: dict[str, Any] | None = None) -> None:
    payload = {
        "source_script_name": source_script_name,
        "skipped": True,
        "reason": reason,
    }
    if extra:
        payload.update(extra)
    write_json(path, payload)


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
    progress_callback: ProgressCallback | None = None,
) -> IntentToScriptArtifacts:
    def emit_progress(
        message: str,
        *,
        step: str,
        stage: str = "upstream",
        run_dir: Path | None = None,
        artifact_path: Path | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if progress_callback is None:
            return
        payload: dict[str, Any] = {
            "message": message,
            "step": step,
            "stage": stage,
            "run_dir": str((run_dir or artifacts.run_dir).resolve()),
        }
        if artifact_path is not None:
            payload["artifact_path"] = str(artifact_path.resolve())
        if extra:
            payload.update(extra)
        progress_callback(payload)

    normalized_source_text = normalize_source_text(source_text)
    if not normalized_source_text:
        raise ValueError("Source input is empty after normalization")

    requested_input_mode = input_mode
    fallback_input_mode = input_mode if input_mode != AUTO_INPUT_MODE else detect_input_mode(normalized_source_text)
    artifacts = build_intent_artifacts(output_root, run_dir)
    emit_progress("任务已提交，正在创建工作空间。", step="输入接收")

    source_input_path = artifacts.source_dir / "source_input.txt"
    source_input_path.write_text(normalized_source_text, encoding="utf-8")

    source_context = build_source_context(
        source_script_name=source_script_name,
        source_text=normalized_source_text,
        requested_input_mode=requested_input_mode,
        fallback_input_mode=fallback_input_mode,
        source_path=source_path,
    )
    source_context_path = artifacts.source_dir / "source_context.json"
    write_json(source_context_path, source_context)
    emit_progress(
        "正在接收并保存原始输入。",
        step="输入接收",
        artifact_path=source_context_path,
        extra={"fallback_input_mode": fallback_input_mode},
    )

    intake_router_request_path = artifacts.source_dir / "intake_router_request.json"
    intake_router_response_path = artifacts.source_dir / "intake_router_response.json"
    intake_router_path = artifacts.source_dir / "intake_router.json"
    intake_router_user_prompt = build_intake_router_user_prompt(source_context, normalized_source_text)
    intake_router_request_payload = {
        "model": model_config.model_name,
        "base_url": model_config.base_url,
        "system_prompt": INTAKE_ROUTER_SYSTEM_PROMPT,
        "user_prompt": intake_router_user_prompt,
        "source_script_name": source_script_name,
        "fallback_input_mode": fallback_input_mode,
    }
    write_json(intake_router_request_path, intake_router_request_payload)
    if dry_run:
        return artifacts

    client = build_text_client(model_config)
    emit_progress(
        "正在分析输入并选择执行路径。",
        step="系统判断",
        artifact_path=intake_router_request_path,
    )

    intake_router_content = run_text_stage(
        client=client,
        model_config=model_config,
        system_prompt=INTAKE_ROUTER_SYSTEM_PROMPT,
        user_prompt=intake_router_user_prompt,
        request_path=intake_router_request_path,
        response_path=intake_router_response_path,
        request_metadata={
            "source_script_name": source_script_name,
            "fallback_input_mode": fallback_input_mode,
            "stage": "intake_router",
        },
        temperature=0.1,
        max_tokens=2048,
    )
    intake_router = IntakeRouter.model_validate(
        normalize_intake_router_payload(
            read_json_string(intake_router_content),
            source_script_name=source_script_name,
            source_context=source_context,
        )
    )
    intake_router_payload = intake_router.model_dump(mode="json")
    write_json(intake_router_path, intake_router_payload)
    emit_progress(
        "系统判断已生成，正在整理后续路径。",
        step="系统判断",
        artifact_path=intake_router_path,
        extra={
            "chosen_path": intake_router.chosen_path,
            "source_kind": intake_router.source_form,
        },
    )

    intent_request_path = artifacts.source_dir / "intent_packet_request.json"
    intent_response_path = artifacts.source_dir / "intent_packet_response.json"
    blueprint_request_path = artifacts.source_dir / "story_blueprint_request.json"
    blueprint_response_path = artifacts.source_dir / "story_blueprint_response.json"
    script_generation_request_path = artifacts.source_dir / "script_generation_request.json"
    script_generation_response_path = artifacts.source_dir / "script_generation_response.json"
    quality_request_path = artifacts.source_dir / "script_quality_request.json"
    quality_response_path = artifacts.source_dir / "script_quality_response.json"
    asset_readiness_request_path = artifacts.source_dir / "asset_readiness_request.json"
    asset_readiness_response_path = artifacts.source_dir / "asset_readiness_response.json"

    if intake_router.chosen_path == "confirm_then_continue":
        skip_reason = "chosen_path=confirm_then_continue, waiting for explicit user confirmation"
        for path in (
            intent_request_path,
            intent_response_path,
            blueprint_request_path,
            blueprint_response_path,
            script_generation_request_path,
            script_generation_response_path,
            quality_request_path,
            quality_response_path,
            asset_readiness_request_path,
            asset_readiness_response_path,
        ):
            write_stage_skip(path, source_script_name=source_script_name, reason=skip_reason)
        emit_progress(
            "系统判断已生成，请确认后继续。",
            step="系统判断",
            artifact_path=intake_router_path,
            extra={"chosen_path": intake_router.chosen_path},
        )
        return artifacts

    intent_packet: IntentPacket | None = None
    story_blueprint: StoryBlueprint | None = None
    title_for_meta = source_script_name
    resolved_input_mode = resolve_intent_input_mode(
        requested_input_mode=requested_input_mode,
        fallback_input_mode=fallback_input_mode,
        source_form=intake_router.source_form,
    )

    if intake_router.chosen_path == "direct_extract":
        emit_progress(
            "识别为可直接提取的剧本输入，正在整理标准剧本输入。",
            step="剧本准备",
            artifact_path=intake_router_path,
            extra={"chosen_path": intake_router.chosen_path},
        )
        skip_reason = "chosen_path=direct_extract, reuse normalized source input without upstream rewrite"
        for path in (
            intent_request_path,
            intent_response_path,
            blueprint_request_path,
            blueprint_response_path,
            script_generation_request_path,
            script_generation_response_path,
            quality_request_path,
            quality_response_path,
        ):
            write_stage_skip(path, source_script_name=source_script_name, reason=skip_reason)
        generated_script_text = normalized_source_text
        generation_mode = generation_mode_from_path(intake_router.chosen_path)
    else:
        emit_progress(
            "正在生成梗概骨架并整理完整剧本。",
            step="剧本准备",
            artifact_path=intake_router_path,
            extra={"chosen_path": intake_router.chosen_path},
        )
        intent_user_prompt = build_intent_understanding_user_prompt(
            source_context,
            intake_router_payload,
            normalized_source_text,
            resolved_input_mode,
        )
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
                "stage": "intent_packet",
                "chosen_path": intake_router.chosen_path,
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
        emit_progress(
            "正在生成梗概骨架。",
            step="剧本准备",
            artifact_path=intent_packet_path,
        )

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
                "chosen_path": intake_router.chosen_path,
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
        write_json(artifacts.source_dir / "story_blueprint.json", story_blueprint.model_dump(mode="json"))
        emit_progress(
            "梗概骨架已生成，正在整理完整剧本。",
            step="剧本准备",
            artifact_path=artifacts.source_dir / "story_blueprint.json",
        )

        script_generation_user_prompt = build_script_generation_user_prompt(
            intent_packet.model_dump(mode="json"),
            story_blueprint.model_dump(mode="json"),
            intake_router_payload,
            normalized_source_text,
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
                "chosen_path": intake_router.chosen_path,
            },
            temperature=0.5,
            max_tokens=8192,
        )
        generated_script_text = clean_generated_script_text(script_generation_content)
        generation_mode = generation_mode_from_path(intake_router.chosen_path)
        title_for_meta = story_blueprint.title

    if not generated_script_text:
        raise ValueError("Generated script text is empty after normalization")

    generated_script_path = artifacts.source_dir / "generated_script.txt"
    generated_script_path.write_text(generated_script_text, encoding="utf-8")
    generated_script_meta = create_script_clean_payload(
        source_script_name=source_script_name,
        normalized_text=generated_script_text,
        source_path=generated_script_path,
    )
    generated_script_meta["title"] = title_for_meta
    generated_script_meta["generation_mode"] = generation_mode
    generated_script_meta["chosen_path"] = intake_router.chosen_path
    generated_script_meta["recommended_operations"] = intake_router.recommended_operations
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
    emit_progress(
        "标准剧本输入已整理完成。",
        step="剧本准备",
        artifact_path=script_clean_text_path,
    )

    if intent_packet is not None and story_blueprint is not None:
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
        write_json(artifacts.source_dir / "script_quality_report.json", quality_report.model_dump(mode="json"))

    evaluated_text_kind = evaluated_text_kind_from_path(intake_router.chosen_path)
    asset_readiness_user_prompt = build_asset_readiness_user_prompt(
        source_script_name,
        evaluated_text_kind,
        intake_router_payload,
        generated_script_text,
    )
    emit_progress(
        "正在检查当前剧本是否适合进入资产流程。",
        step="剧本准备",
        artifact_path=asset_readiness_request_path,
    )
    asset_readiness_content = run_text_stage(
        client=client,
        model_config=model_config,
        system_prompt=ASSET_READINESS_SYSTEM_PROMPT,
        user_prompt=asset_readiness_user_prompt,
        request_path=asset_readiness_request_path,
        response_path=asset_readiness_response_path,
        request_metadata={
            "source_script_name": source_script_name,
            "stage": "asset_readiness",
            "evaluated_text_kind": evaluated_text_kind,
            "chosen_path": intake_router.chosen_path,
        },
        temperature=0.0,
        max_tokens=4096,
    )
    asset_readiness_report = AssetReadinessReport.model_validate(
        normalize_asset_readiness_payload(
            read_json_string(asset_readiness_content),
            source_script_name=source_script_name,
            evaluated_text_kind=evaluated_text_kind,
        )
    )
    write_json(
        artifacts.source_dir / "asset_readiness_report.json",
        asset_readiness_report.model_dump(mode="json"),
    )
    emit_progress(
        "上游剧本已准备完成。",
        step="剧本准备",
        artifact_path=artifacts.source_dir / "asset_readiness_report.json",
        extra={"safe_to_extract": asset_readiness_report.safe_to_extract},
    )

    asset_dir: Path | None = None
    if extract_assets:
        if not asset_readiness_report.safe_to_extract:
            raise ValueError(
                "Asset extraction blocked by asset_readiness_report.json because safe_to_extract=false"
            )
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
