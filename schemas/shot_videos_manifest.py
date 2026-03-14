"""Pydantic schema for shot_videos_manifest.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import SegmentId, StrictModel
from schemas.storyboard import ShotId


ShotVideoStatus = Literal[
    "succeeded",
    "failed",
    "timed_out",
    "skipped_not_selected",
    "skipped_job_not_ready",
]


def _validate_sequential_ids(ids: list[str], prefix: str) -> None:
    expected = [f"{prefix}_{index:03d}" for index in range(1, len(ids) + 1)]
    if ids != expected:
        raise ValueError(f"{prefix} IDs must be sequential: expected {expected}, got {ids}")


class ShotVideoExecutionSpec(StrictModel):
    resolution: str
    timeout_seconds: int = Field(gt=0)
    poll_interval_seconds: int = Field(gt=0)
    keep_remote_media: bool


class ShotVideoResult(StrictModel):
    shot_id: ShotId
    order: int = Field(ge=1)
    segment_ids: list[SegmentId] = Field(min_length=1)
    video_name: str
    status: ShotVideoStatus
    task_id: str
    request_path: str
    created_response_path: str
    result_response_path: str
    video_local_path: str
    video_url: str
    file_url: str
    error_message: str

    @model_validator(mode="after")
    def validate_result(self) -> "ShotVideoResult":
        if self.status == "succeeded" and not self.task_id:
            raise ValueError("succeeded shot video result must include task_id")
        return self


class ShotVideosManifest(StrictModel):
    schema_version: Literal["1.0"]
    source_run: str
    source_script_name: str
    title: str
    video_model: str
    execution_spec: ShotVideoExecutionSpec
    results: list[ShotVideoResult] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> "ShotVideosManifest":
        shot_ids = [item.shot_id for item in self.results]
        orders = [item.order for item in self.results]

        _validate_sequential_ids(shot_ids, "shot")

        expected_orders = list(range(1, len(orders) + 1))
        if orders != expected_orders:
            raise ValueError(f"results.order must be sequential: expected {expected_orders}, got {orders}")

        return self
