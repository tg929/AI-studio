"""Pydantic schema for final_video_manifest.json."""

from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from schemas.asset_registry import StrictModel
from schemas.storyboard import ShotId


class FinalConcatSpec(StrictModel):
    concat_mode: Literal["ffmpeg_concat_demuxer_reencode"]
    trim_leading_seconds: float = Field(ge=0)
    video_codec: str
    audio_codec: str
    pixel_format: str
    faststart: bool


class FinalVideoInput(StrictModel):
    shot_id: ShotId
    order: int = Field(ge=1)
    source_video_path: str
    trimmed_video_path: str


class FinalVideoManifest(StrictModel):
    schema_version: Literal["1.0"]
    source_run: str
    source_script_name: str
    title: str
    concat_spec: FinalConcatSpec
    concat_list_path: str
    final_video_path: str
    inputs: list[FinalVideoInput] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_manifest(self) -> "FinalVideoManifest":
        expected_orders = list(range(1, len(self.inputs) + 1))
        actual_orders = [item.order for item in self.inputs]
        if actual_orders != expected_orders:
            raise ValueError(f"inputs.order must be sequential: expected {expected_orders}, got {actual_orders}")
        expected_ids = [f"shot_{index:03d}" for index in range(1, len(self.inputs) + 1)]
        actual_ids = [item.shot_id for item in self.inputs]
        if actual_ids != expected_ids:
            raise ValueError(f"inputs.shot_id must be sequential: expected {expected_ids}, got {actual_ids}")
        return self
