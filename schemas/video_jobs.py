"""Pydantic schema for video_jobs.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import SegmentId, StrictModel
from schemas.storyboard import ShotId


VideoJobStatus = Literal["ready", "blocked_missing_first_frame_url", "blocked_prompt_validation_failed"]
VideoInputMode = Literal["first_frame_only"]
FirstFrameTransition = Literal["fast_transform_into_cinematic_scene"]


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


class VideoJobDefaults(StrictModel):
    input_mode: VideoInputMode
    shot_duration_sec: Literal[10]
    aspect_ratio: Literal["16:9"]
    watermark: Literal[False]
    prompt_language: Literal["zh-CN"]
    first_frame_transition: FirstFrameTransition


class PromptBlocks(StrictModel):
    transition_block: str
    single_take_block: str
    content_block: str
    anchor_block: str
    negative_block: str


class VideoJob(StrictModel):
    shot_id: ShotId
    order: int = Field(ge=1)
    segment_ids: list[SegmentId] = Field(min_length=1)
    video_name: str
    first_frame_local_path: str
    first_frame_url: str
    input_mode: VideoInputMode
    duration_sec: Literal[10]
    aspect_ratio: Literal["16:9"]
    watermark: Literal[False]
    prompt: str
    prompt_blocks: PromptBlocks
    status: VideoJobStatus

    @model_validator(mode="after")
    def validate_job(self) -> "VideoJob":
        if self.status == "ready" and not self.first_frame_url:
            raise ValueError("ready video job must include first_frame_url")
        if self.status == "blocked_missing_first_frame_url" and self.first_frame_url:
            raise ValueError("blocked_missing_first_frame_url jobs must not include first_frame_url")
        if not self.prompt:
            raise ValueError("prompt must not be empty")
        return self


class VideoJobsManifest(StrictModel):
    schema_version: Literal["1.0"]
    source_run: str
    source_script_name: str
    title: str
    video_model: str
    job_defaults: VideoJobDefaults
    jobs: list[VideoJob] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> "VideoJobsManifest":
        shot_ids = [item.shot_id for item in self.jobs]
        orders = [item.order for item in self.jobs]

        _validate_sequential_ids(shot_ids, "shot")

        expected_orders = list(range(1, len(orders) + 1))
        if orders != expected_orders:
            raise ValueError(f"jobs.order must be sequential: expected {expected_orders}, got {orders}")

        return self
