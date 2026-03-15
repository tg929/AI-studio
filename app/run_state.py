from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field


CORE_STAGE_ORDER = (
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

OPTIONAL_STAGE_ORDER = ("storyboard_seed",)

RunStatus = Literal["pending", "running", "succeeded", "failed", "blocked", "awaiting_approval"]
StageStatus = Literal[
    "pending",
    "running",
    "succeeded",
    "failed",
    "blocked",
    "awaiting_approval",
    "skipped",
]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class StageState(BaseModel):
    name: str
    status: StageStatus = "pending"
    started_at: str = ""
    finished_at: str = ""
    updated_at: str = ""
    message: str = ""
    artifact_path: str = ""
    attempts: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunState(BaseModel):
    schema_version: Literal["1.0"] = "1.0"
    run_id: str
    run_dir: str
    source_script_name: str = ""
    status: RunStatus = "pending"
    current_stage: str = ""
    awaiting_approval_stage: str = ""
    last_error: str = ""
    created_at: str
    updated_at: str
    stage_order: list[str] = Field(default_factory=lambda: list(CORE_STAGE_ORDER))
    stages: dict[str, StageState] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


def meta_dir(run_dir: Path) -> Path:
    path = run_dir / "_meta"
    path.mkdir(parents=True, exist_ok=True)
    return path


def run_state_path(run_dir: Path) -> Path:
    return meta_dir(run_dir) / "run_state.json"


def events_path(run_dir: Path) -> Path:
    return meta_dir(run_dir) / "events.jsonl"


def build_default_run_state(run_dir: Path, *, source_script_name: str = "") -> RunState:
    timestamp = utc_now_iso()
    stages = {
        stage: StageState(name=stage, updated_at=timestamp)
        for stage in (*CORE_STAGE_ORDER, *OPTIONAL_STAGE_ORDER)
    }
    return RunState(
        run_id=run_dir.name,
        run_dir=str(run_dir.resolve()),
        source_script_name=source_script_name,
        created_at=timestamp,
        updated_at=timestamp,
        stages=stages,
    )


def write_run_state(run_dir: Path, state: RunState) -> Path:
    path = run_state_path(run_dir)
    path.write_text(
        json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def load_run_state(run_dir: Path) -> RunState | None:
    path = run_state_path(run_dir)
    if not path.exists():
        return None
    return RunState.model_validate_json(path.read_text(encoding="utf-8"))


def ensure_run_state(run_dir: Path, *, source_script_name: str = "") -> RunState:
    existing = load_run_state(run_dir)
    if existing is not None:
        if source_script_name and not existing.source_script_name:
            existing.source_script_name = source_script_name
            existing.updated_at = utc_now_iso()
            write_run_state(run_dir, existing)
        return existing

    state = build_default_run_state(run_dir, source_script_name=source_script_name)
    write_run_state(run_dir, state)
    return state


def append_run_event(
    run_dir: Path,
    *,
    event_type: str,
    stage: str = "",
    message: str = "",
    data: dict[str, Any] | None = None,
) -> Path:
    entry = {
        "timestamp": utc_now_iso(),
        "event_type": event_type,
        "stage": stage,
        "message": message,
        "data": data or {},
    }
    path = events_path(run_dir)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


def update_stage_state(
    run_dir: Path,
    *,
    stage: str,
    status: StageStatus,
    message: str = "",
    artifact_path: str = "",
    metadata: dict[str, Any] | None = None,
    source_script_name: str = "",
    run_status: RunStatus | None = None,
    current_stage: str | None = None,
    last_error: str | None = None,
    awaiting_approval_stage: str | None = None,
) -> RunState:
    state = ensure_run_state(run_dir, source_script_name=source_script_name)
    now = utc_now_iso()
    stage_state = state.stages.get(stage)
    if stage_state is None:
        stage_state = StageState(name=stage, updated_at=now)
        state.stages[stage] = stage_state
        if stage not in state.stage_order:
            state.stage_order.append(stage)

    if status == "running":
        stage_state.attempts += 1
        if not stage_state.started_at:
            stage_state.started_at = now
        stage_state.finished_at = ""
    elif status != "pending":
        if not stage_state.started_at:
            stage_state.started_at = now
        stage_state.finished_at = now

    stage_state.status = status
    stage_state.updated_at = now
    if message:
        stage_state.message = message
    if artifact_path:
        stage_state.artifact_path = artifact_path
    if metadata:
        stage_state.metadata.update(metadata)

    if source_script_name:
        state.source_script_name = source_script_name
    if run_status is not None:
        state.status = run_status
    if current_stage is not None:
        state.current_stage = current_stage
    else:
        state.current_stage = stage
    if last_error is not None:
        state.last_error = last_error
    if awaiting_approval_stage is not None:
        state.awaiting_approval_stage = awaiting_approval_stage
    elif state.awaiting_approval_stage == stage and status != "awaiting_approval":
        state.awaiting_approval_stage = ""
    state.updated_at = now

    write_run_state(run_dir, state)
    return state
